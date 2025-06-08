#!/usr/bin/python3
from base64 import b64encode, b64decode
from random import random
from threading import Thread
import traceback
from typing import Optional

import cherrypy
from Crypto.Cipher import AES

from stembot.adapter.agent import NetworkMessageClient
from stembot import logging
from stembot.adapter.process import sync_process
from stembot.ticketing import close_ticket, read_ticket, service_ticket, trace_ticket
from stembot.dao import Collection
from stembot.messages import forward_network_message, pop_network_messages, pull_network_messages
from stembot.peering import touch_peer
from stembot.peering import process_route_advertisement
from stembot.peering import age_routes
from stembot.peering import create_route_advertisement
from stembot.peering import create_peer, delete_peer, delete_peers, get_peers, get_routes
from stembot.executor.cascade import process_cascade_request
from stembot.executor.cascade import service_cascade_request
from stembot.scheduling import register_timer
from stembot.types.control import ControlForm, ControlFormType, CreatePeer, DeletePeers, DiscoverPeer, GetPeers, GetRoutes, ControlFormTicket, SyncProcess
from stembot.types.network import Acknowledgement, Advertisement, NetworkCascade, NetworkMessage, NetworkMessageType, NetworkMessagesRequest, NetworkMessagesResponse, NetworkTicket, TicketTraceResponse
from stembot.types.network import Ping
from stembot.types.routing import Peer


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
    logging.debug(form.type)
    match form.type:
        case ControlFormType.DISCOVER_PEER:
            form = DiscoverPeer(**form.model_dump())
            client = NetworkMessageClient(
                url=form.url,
                secret_digest=cherrypy.config.get('server.secret_digest')
            )
            acknowledgement = client.send_network_message(Ping())
            form.agtuuid = acknowledgement.dest
            create_peer(agtuuid=form.agtuuid, url=form.url, ttl=form.ttl, polling=form.polling)
        case ControlFormType.CREATE_PEER:
            form = CreatePeer(**form.model_dump())
            create_peer(agtuuid=form.agtuuid, url=form.url, ttl=form.ttl, polling=form.polling)
        case ControlFormType.DELETE_PEERS:
            form = DeletePeers(**form.model_dump())
            if form.agtuuids:
                for agtuuid in form.agtuuids:
                    delete_peer(agtuuid)
            else:
                delete_peers()
        case ControlFormType.GET_PEERS:
            form = GetPeers(**form.model_dump())
            form.peers = get_peers()
        case ControlFormType.GET_ROUTES:
            form = GetRoutes(**form.model_dump())
            form.routes = get_routes()
        case ControlFormType.SYNC_PROCESS:
            form = sync_process(SyncProcess(**form.model_dump()))
        case ControlFormType.CREATE_TICKET:
            form = create_form_ticket(ControlFormTicket(**form.model_dump()))
        case ControlFormType.READ_TICKET:
            form = read_ticket(ControlFormTicket(**form.model_dump()))
        case ControlFormType.CLOSE_TICKET:
            close_ticket(ControlFormTicket(**form.model_dump()))
        case _:
            logging.warning(f'Unknown control form type encountered: {form.type}')
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


class Root(object):
    mpi = MPI()
    control = Control()


def create_form_ticket(control_form_ticket: ControlFormTicket):
    network_ticket = NetworkTicket(
        form=control_form_ticket.form,
        dest=control_form_ticket.dst,
        tckuuid=control_form_ticket.tckuuid,
        tracing=control_form_ticket.tracing,
        type=NetworkMessageType.TICKET_REQUEST,
        create_time=control_form_ticket.create_time
    )

    tickets = Collection('tickets', in_memory=True, model=ControlFormTicket)
    ticket = tickets.upsert_object(control_form_ticket)

    route_network_message(network_ticket)

    return ticket.object


def route_network_message(message_in: NetworkMessage) -> NetworkMessage:
    if message_in.type in (
        NetworkMessageType.TICKET_REQUEST, NetworkMessageType.TICKET_RESPONSE):
        ticket = NetworkTicket(**message_in.model_dump())
        if ticket.tracing:
            trace_message = TicketTraceResponse(
                dest=(
                    ticket.src if ticket.type == NetworkMessageType.TICKET_REQUEST
                    else ticket.dest
                ),
                tckuuid=ticket.tckuuid
            )

            if trace_message.dest == cherrypy.config.get('agtuuid'):
                process_network_message(trace_message)
            else:
                Thread(target=forward_network_message, args=(trace_message,)).start()

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
    match message.type:
        case NetworkMessageType.PING:
            logging.debug(f'PING: {message.src} -> {message.dest}')
            return None
        case NetworkMessageType.ADVERTISEMENT:
            process_route_advertisement(Advertisement.model_validate(message.model_extra))
            return None
        case NetworkMessageType.TICKET_REQUEST:
            ticket = NetworkTicket(**message.model_dump())
            try:
                ticket.form = process_control_form(ticket.form)
            except: # pylint: disable=bare-except
                ticket.form.error = traceback.format_exc()
                logging.exception(f'Encountered exception with ticket {ticket.tckuuid}')
            ticket.src = message.dest
            ticket.dest = message.src
            ticket.type = NetworkMessageType.TICKET_RESPONSE
            route_network_message(ticket)
            return None
        case NetworkMessageType.TICKET_RESPONSE:
            service_ticket(NetworkTicket(**message.model_dump()))
            return None
        case NetworkMessageType.TICKET_TRACE_RESPONSE:
            trace_ticket(TicketTraceResponse(**message.model_dump()))
            return None
        case NetworkMessageType.CASCADE_REQUEST:
            process_cascade_request(NetworkCascade(**message.model_dump()))
            return None
        case NetworkMessageType.CASCADE_RESPONSE:
            service_cascade_request(NetworkCascade(**message.model_dump()))
            return None
        case NetworkMessageType.MESSAGES_REQUEST:
            return NetworkMessagesRequest(
                messages=pull_network_messages(message.isrc),
                type=NetworkMessageType.MESSAGES_RESPONSE,
                dest=message.isrc
            )
        case _:
            logging.warning(f'Unknown network message type encountered: {message.type}')
            logging.debug(message)


def replay_worker():
    register_timer(
        name='replay_worker',
        target=replay_worker,
        timeout=1.0
    ).start()

    for message in pop_network_messages(dest='$!eq:None'):
        logging.debug(f'{message.src} -> {message.type} -> {message.dest}')
        Thread(target=route_network_message, args=(message,)).start()


def anon_worker():
    register_timer(
        name='anon_worker',
        target=anon_worker,
        timeout=1.0
    ).start()

    for message in pop_network_messages(type='cascade response'):
        Thread(target=process_network_message, args=(message,)).start()

    for message in pop_network_messages(type='cascade request'):
        Thread(target=process_network_message, args=(message,)).start()


def poll_peer(peer: Peer):
    client = NetworkMessageClient(
        url=peer.url,
        secret_digest=cherrypy.config.get('server.secret_digest')
    )

    network_message = client.send_network_message(NetworkMessagesRequest())

    match network_message.type:
        case NetworkMessageType.MESSAGES_RESPONSE:
            network_messages = NetworkMessagesResponse.model_validate(network_message.model_extra)
            for network_message in network_messages.messages:
                Thread(target=route_network_message, args=(network_message,)).start()
        case NetworkMessageType.ACKNOWLEDGEMENT:
            acknowledment = Acknowledgement.model_validate(network_message.model_extra)
            if acknowledment.error:
                logging.error(acknowledment.error)


def poll_worker():
    register_timer(
        name='poll_worker',
        target=poll_worker,
        timeout=1.0
    ).start()

    for peer in Collection('peers', in_memory=True, model=Peer).find(url='$!eq:None', polling=True):
        Thread(target=poll_peer, args=(peer.object,)).start()


def advertise(peer):
    advertisement = create_route_advertisement()
    advertisement.dest = peer.agtuuid
    route_network_message(advertisement)


def ad_worker():
    rt = int(random() * 30.0)

    register_timer(
        name='ad_worker',
        target=ad_worker,
        timeout=rt
    ).start()

    age_routes(rt)

    for peer in Collection('peers', in_memory=True, model=Peer).find():
        Thread(target=advertise, args=(peer.object,)).start()

Thread(target=ad_worker).start()
Thread(target=poll_worker).start()
Thread(target=replay_worker).start()
# Thread(target=anon_worker).start()
