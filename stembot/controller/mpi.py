#!/usr/bin/python3
import cherrypy
import traceback
from typing import List, Optional

from Crypto.Cipher import AES
from random import random
from threading import Thread
from base64 import b64encode, b64decode
from time import time

from stembot.adapter.agent import NetworkMessageClient
from stembot.audit import logging
from stembot.executor.ticket import read_ticket, service_ticket
from stembot.dao import Collection
from stembot.model import kvstore
from stembot.model.messages import pop_network_messages, push_network_message
from stembot.model.peer import touch_peer
from stembot.model.peer import process_route_advertisement
from stembot.model.peer import age_routes
from stembot.model.peer import create_route_advertisement
from stembot.model.peer import create_peer, delete_peer, delete_peers, get_peers, get_routes
from stembot.executor.cascade import process_cascade_request
from stembot.executor.cascade import service_cascade_request
from stembot.executor.counters import increment as ctr_increment
from stembot.executor.counters import decrement as ctr_decrement
from stembot.executor.counters import get as ctr_get_name
from stembot.executor.counters import set as ctr_set_name
from stembot.executor.timers import register_timer
from stembot.types.control import ControlForm, ControlFormType, CreatePeer, DeletePeers, DiscoverPeer, GetPeers, GetRoutes, ControlFormTicket
from stembot.types.network import Acknowledgement, Advertisement, NetworkCascade, NetworkMessage, NetworkMessageType, NetworkMessages, NetworkMessagesRequest, NetworkTicket
from stembot.types.network import Ping, Route
from stembot.types.routing import Peer

START_TIME = time()

class Control(object):
    @cherrypy.expose
    def default(self):
        try:
            cl = cherrypy.request.headers['Content-Length']
            cipher_b64 = cherrypy.request.body.read(int(cl))
            cipher_text = b64decode(cipher_b64)

            nonce = b64decode(cherrypy.request.headers['Nonce'].encode())
            tag = b64decode(cherrypy.request.headers['Tag'].encode())
            key = b64decode(cherrypy.config.get('server.secret_digest'))[:16]
            request_cipher = AES.new(key, AES.MODE_EAX, nonce=nonce)
        except:
            logging.exception('Failed to initialize request cipher!')
            logging.debug(f"{cherrypy.request.headers}\n{cipher_b64}")
            raise

        try:
            raw_message = request_cipher.decrypt(cipher_text)
            request_cipher.verify(tag)
        except:
            logging.exception('Failed to decode control form request!')
            logging.debug(f"{cherrypy.request.headers}\n{cipher_b64}")
            raise

        try:
            form = ControlForm.model_validate_json(raw_message.decode())
        except:
            logging.exception('Failed to validate control form!')
            logging.debug(raw_message.decode())
            raise

        try:
            form = process_control_form(form)
        except: # pylint: disable=bare-except
            form.error = traceback.format_exc()
            logging.exception(form.type)

        raw_message = form.model_dump_json().encode()

        response_cipher = AES.new(key, AES.MODE_EAX)

        cipher_text, tag = response_cipher.encrypt_and_digest(raw_message)

        cipher_b64 = b64encode(cipher_text)

        cherrypy.response.headers['Nonce'] = b64encode(response_cipher.nonce).decode()
        cherrypy.response.headers['Tag'] = b64encode(tag).decode()

        return cipher_b64

    default.exposed = True


def process_control_form(form: ControlForm) -> ControlForm:
    match ControlFormType(form.type):
        case ControlFormType.DISCOVER_PEER:
            form = DiscoverPeer.model_validate(form.model_extra)
            client = NetworkMessageClient(
                url=form.url,
                secret_digest=cherrypy.config.get('server.secret_digest')
            )
            acknowledgement = client.send_network_message(Ping())
            form.agtuuid = acknowledgement.dest
            create_peer(agtuuid=form.agtuuid, url=form.url, ttl=form.ttl, polling=form.polling)
        case ControlFormType.CREATE_PEER:
            form = CreatePeer.model_validate(form.model_extra)
            create_peer(agtuuid=form.agtuuid, url=form.url, ttl=form.ttl, polling=form.polling)
        case ControlFormType.DELETE_PEERS:
            form = DeletePeers.model_validate(form.model_extra)
            if form.agtuuids:
                for agtuuid in form.agtuuids:
                    delete_peer(agtuuid)
            else:
                delete_peers()
        case ControlFormType.GET_PEERS:
            form = GetPeers.model_validate(form.model_extra)
            form.peers = get_peers()
        case ControlFormType.GET_ROUTES:
            form = GetRoutes.model_validate(form.model_extra)
            form.routes = get_routes()
        case ControlFormType.CREATE_TICKET:
            form = create_form_ticket(ControlFormTicket.model_validate(form.model_extra))
        case ControlFormType.READ_TICKET:
            form = read_ticket(ControlFormTicket.model_validate(form.model_extra))

    logging.debug(form)

    return form


class MPI(object):
    @cherrypy.expose
    def default(self):
        try:
            cl = cherrypy.request.headers['Content-Length']
            cipher_b64 = cherrypy.request.body.read(int(cl))
            cipher_text = b64decode(cipher_b64)

            nonce = b64decode(cherrypy.request.headers['Nonce'].encode())
            tag = b64decode(cherrypy.request.headers['Tag'].encode())
            key = b64decode(cherrypy.config.get('server.secret_digest'))[:16]
            request_cipher = AES.new(key, AES.MODE_EAX, nonce=nonce)
        except:
            logging.exception('Failed to initialize request cipher!')
            logging.debug(f"{cherrypy.request.headers}\n{cipher_b64}")
            raise

        try:
            raw_message = request_cipher.decrypt(cipher_text)
            request_cipher.verify(tag)
        except:
            logging.exception('Failed to decode network message request!')
            logging.debug(f"{cherrypy.request.headers}\n{cipher_b64}")
            raise

        try:
            message = NetworkMessage.model_validate_json(raw_message.decode())
        except:
            logging.exception('Failed to validate network message!')
            logging.debug(raw_message.decode())
            raise

        if isrc := message.isrc:
            touch_peer(isrc)

        if message.dest is None:
            message.dest = cherrypy.config.get('agtuuid')

        raw_message = route_network_message(message).model_dump_json().encode()

        response_cipher = AES.new(key, AES.MODE_EAX)

        cipher_text, tag = response_cipher.encrypt_and_digest(raw_message)

        cipher_b64 = b64encode(cipher_text)

        cherrypy.response.headers['Nonce'] = b64encode(response_cipher.nonce).decode()
        cherrypy.response.headers['Tag'] = b64encode(tag).decode()

        return cipher_b64

    default.exposed = True


def create_form_ticket(control_form_ticket: ControlFormTicket):
    logging.debug(f'{control_form_ticket.form.type} -> {control_form_ticket.dst}')

    network_ticket = NetworkTicket(
        form=control_form_ticket.form,
        dest=control_form_ticket.dst,
        tckuuid=control_form_ticket.tckuuid,
        type=NetworkMessageType.TICKET_REQUEST,
        create_time=control_form_ticket.create_time
    )

    tickets = Collection('tickets', in_memory=True, model=ControlFormTicket)
    ticket = tickets.upsert_object(control_form_ticket)

    route_network_message(network_ticket)

    return ticket.object


def route_network_message(message_in: NetworkMessage) -> NetworkMessage:
    # logging.debug(message_in)
    if message_in.dest == cherrypy.config.get('agtuuid'):
        try:
            if message_out := process_network_message(message_in):
                return message_out
            else:
                return Acknowledgement(
                    ack_type=message_in.type,
                    src=message_in.src,
                    dest=message_in.dest
                )
        except: # pylint: disable=bare-except
            return Acknowledgement(
                ack_type=message_in.type,
                src=message_in.src,
                dest=message_in.dest,
                error=traceback.format_exc()
            )

    Thread(target=forward_network_message, args=(message_in,)).start()

    return Acknowledgement(
        src=message_in.src,
        ack_type=message_in.type,
        dest=message_in.dest
    )


def process_network_message(message: NetworkMessage) -> Optional[NetworkMessage]:
    logging.debug(f'{message.src} -> {message.type} -> {message.dest}')

    match message.type:
        case NetworkMessageType.PING:
            return None
        case NetworkMessageType.ADVERTISEMENT:
            process_route_advertisement(Advertisement.model_validate(message.model_extra))
            return None
        case NetworkMessageType.TICKET_REQUEST:
            logging.debug(message)
            ticket = NetworkTicket.model_validate(message)
            logging.debug(ticket)
            try:
                ticket.form = process_control_form(ticket.form)
            except: # pylint: disable=bare-except
                ticket.form.error = traceback.format_exc()
                logging.exception(f'Encountered exception with ticket {ticket.tckuuid}')
            ticket.src = message.dest
            ticket.dest = message.src
            ticket.type = NetworkMessageType.TICKET_RESPONSE
            logging.debug(ticket)
            route_network_message(ticket)
            return None
        case NetworkMessageType.TICKET_RESPONSE:
            logging.debug(message)
            ticket = NetworkTicket.model_validate(message)
            logging.debug(ticket)
            service_ticket(ticket)
            return None
        case NetworkMessageType.CASCADE_REQUEST:
            process_cascade_request(NetworkCascade.model_validate(message.model_extra))
            return None
        case NetworkMessageType.CASCADE_RESPONSE:
            service_cascade_request(NetworkCascade.model_validate(message.model_extra))
            return None
        case NetworkMessageType.MESSAGE_REQUEST:
            return NetworkMessages(
                messages=pull_network_messages(message.isrc),
                type=NetworkMessageType.MESSAGE_RESPONSE
            )

    logging.warning(message)


def pull_network_messages(agtuuid: str) -> List[NetworkMessage]:
    # Find the best gateway for each destination
    gateway_map = {}
    for route in Collection('routes', in_memory=True, model=Route).find():
        if route.object.agtuuid in gateway_map:
            if gateway_map[route.object.agtuuid]['weight'] > route.object.weight:
                gateway_map[route.object.agtuuid] = {
                    'weight': route.object.weight,
                    'gtwuuid': route.object.gtwuuid
                }
        else:
            gateway_map[route.object.agtuuid] = {
                'weight': route.object.weight,
                'gtwuuid': route.object.gtwuuid
            }

    agtuuids = [
        agtuuid for agtuuid, v in gateway_map.items()
        if v['gtwuuid'] == agtuuid
    ] + [agtuuid]

    network_messages = []
    for network_messages_chunk in [pop_network_messages(dest=agtuuid) for agtuuid in agtuuids]:
        for network_message in network_messages_chunk:
            network_messages.append(network_message)

    return network_messages


def forward_network_message(message: NetworkMessage):
    peers = Collection('peers', in_memory=True, model=Peer)
    routes = Collection('routes', in_memory=True, model=Route)

    for peer in peers.find(agtuuid=message.dest):
        try:
            if peer.object.url is not None:
                client = NetworkMessageClient(
                    url=peer.object.url,
                    secret_digest=cherrypy.config.get('server.secret_digest')
                )
                acknowledgement = Acknowledgement.model_validate(
                    client.send_network_message(message).model_extra)
                if acknowledgement.error:
                    logging.error(acknowledgement.error)
            else:
                push_network_message(message)
        except: # pylint: disable=bare-except
            logging.exception(f'Failed to send network message to {peer.object.url}')
            push_network_message(message)
        return

    weight = None
    best_gtwuuid = None
    for route in routes.find(agtuuid=message.dest):
        if weight is None or float(route.object.weight) < float(weight):
            weight = route.object.weight
            best_gtwuuid = route.object.gtwuuid

    for peer in peers.find(agtuuid=best_gtwuuid):
        try:
            if peer.object.url is not None:
                client = NetworkMessageClient(
                    url=peer.object.url,
                    secret_digest=cherrypy.config.get('server.secret_digest')
                )
                acknowledgement = Acknowledgement.model_validate(
                    client.send_network_message(message).model_extra)
                if acknowledgement.error:
                    logging.error(acknowledgement.error)
            else:
                push_network_message(message)
        except: # pylint: disable=bare-except
            logging.exception(f'Failed to send network message to {peer.object.url}')
            push_network_message(message)
        return

    logging.warning(f'Dropped message: {message}')


def anon_worker():
    register_timer(
        name='anon_worker',
        target=anon_worker,
        timeout=0.5
    ).start()

    for message in pop_network_messages(type='cascade response'):
        Thread(target=process_network_message, args=(message,)).start()

    for message in pop_network_messages(type='cascade request'):
        Thread(target=process_network_message, args=(message,)).start()


def poll(peer: Peer):
    try:
        client = NetworkMessageClient(
            url=peer.url,
            secret_digest=cherrypy.config.get('server.secret_digest')
        )

        network_message = client.send_network_message(NetworkMessagesRequest())

        match network_message.type:
            case NetworkMessageType.MESSAGE_RESPONSE:
                network_messages = NetworkMessages.model_validate(network_message.model_extra)
                for network_message in network_messages.messages:
                    Thread(target=route_network_message, args=(network_message,)).start()
            case NetworkMessageType.ACKNOWLEDGEMENT:
                acknowledment = Acknowledgement.model_validate(network_message.model_extra)
                if acknowledment.error:
                    logging.error(acknowledment.error)
    finally:
        ctr_decrement('threads (polling-{0})'.format(peer.agtuuid))


def poll_worker():
    register_timer(
        name='poll_worker',
        target=poll_worker,
        timeout=0.5
    ).start()

    ctr_set_name('uptime', int(time() - START_TIME))

    for peer in Collection('peers', in_memory=True, model=Peer).find(url='$!eq:None', polling=True):
        if ctr_get_name('threads (polling-{0})'.format(peer.object.agtuuid)) == 0:
            ctr_increment('threads (polling-{0})'.format(peer.object.agtuuid))
            Thread(target=poll, args=(peer.object,)).start()


def advertise(peer):
    try:
        advertisement = create_route_advertisement()
        advertisement.dest = peer.agtuuid
        route_network_message(advertisement)
    finally:
        ctr_decrement('threads (advertising-{0})'.format(peer.agtuuid))

def ad_worker():
    rt = int(random() * 30.0)

    register_timer(
        name='ad_worker',
        target=ad_worker,
        timeout=rt
    ).start()

    age_routes(rt)

    for peer in get_peers():
        if ctr_get_name('threads (advertising-{0})'.format(peer.agtuuid)) == 0:
            ctr_increment('threads (advertising-{0})'.format(peer.agtuuid))

            Thread(target=advertise, args=(peer,)).start()

Thread(target=ad_worker).start()
Thread(target=poll_worker).start()
# Thread(target=anon_worker).start()
