#!/usr/bin/python3

from typing import Optional
import cherrypy
import json
import traceback

from Crypto.Cipher import AES
from random import random, randrange
from threading import Thread, Timer, Lock
from base64 import b64encode, b64decode
from time import time, sleep

from stembot.adapter.agent import NetworkMessageClient
from stembot.audit import logging
from stembot.executor import cron
from stembot.executor import script
from stembot.executor.ticket import process_ticket
from stembot.executor.ticket import service_ticket
from stembot.executor.ticket import create_ticket
from stembot.executor.ticket import wait_on_ticket_response
from stembot.executor.ticket import get_ticket_response
from stembot.executor.ticket import delete_ticket
from stembot.dao import Collection
from stembot.model.messages import pop_messages
from stembot.model.messages import push_message
from stembot.model.peer import create_peer
from stembot.model.peer import touch_peer
from stembot.model.peer import delete_peer
from stembot.model.peer import delete_peers
from stembot.model.peer import process_route_advertisement
from stembot.model.peer import get_peers
from stembot.model.peer import get_routes
from stembot.model.peer import age_routes
from stembot.model.peer import delete_route
from stembot.model.peer import create_route_advertisement
from stembot.executor.cascade import process_cascade_request
from stembot.executor.cascade import service_cascade_request
from stembot.executor.cascade import wait_on_cascade_responses
from stembot.executor.cascade import create_cascade_request
from stembot.executor.counters import increment as ctr_increment
from stembot.executor.counters import decrement as ctr_decrement
from stembot.executor.counters import get_all as ctr_get_all
from stembot.executor.counters import get as ctr_get_name
from stembot.executor.counters import set as ctr_set_name
from stembot.executor.timers import register_timer
from stembot.types.network import Acknowledgement, Advertisement, Cascade, NetworkMessage, NetworkMessageType, NetworkMessages, NetworkMessagesRequest, Ticket

START_TIME = time()

class MPI(object):
    @cherrypy.expose
    def default(self):
        cl = cherrypy.request.headers['Content-Length']
        cipher_b64 = cherrypy.request.body.read(int(cl))
        cipher_text = b64decode(cipher_b64)

        nonce = b64decode(cherrypy.request.headers['Nonce'].encode())
        tag = b64decode(cherrypy.request.headers['Tag'].encode())
        key = b64decode(cherrypy.config.get('server.secret_digest'))[:16]
        request_cipher = AES.new(key, AES.MODE_EAX, nonce=nonce)

        raw_message = request_cipher.decrypt(cipher_text)
        request_cipher.verify(tag)

        message_in = NetworkMessage.model_validate_json(raw_message.decode())

        if isrc := message_in.isrc:
            touch_peer(isrc)

        if message_in.dest is None:
            message_in.dest = cherrypy.config.get('agtuuid')

        if message_in.dest == cherrypy.config.get('agtuuid'):
            try:
                if message := process(message_in):
                    message_out = message
                else:
                    message_out = Acknowledgement(
                        ack_type=message_in.type,
                        src=message_in.src,
                        dest=message_in.dest
                    )
            except: # pylint: disable=bare-except
                message_out = Acknowledgement(
                    ack_type=message_in.type,
                    src=message_in.src,
                    dest=message_in.dest,
                    error=traceback.format_exc()
                )
                logging.exception(message_in.type)
        else:
            message_out = Acknowledgement(
                src=message_in.src,
                ack_type=message_in.type,
                dest=message_in.dest,
                forwarded=forward(message_in)
            )

        raw_message = message_out.model_dump_json().encode()

        response_cipher = AES.new(key, AES.MODE_EAX)

        cipher_text, tag = response_cipher.encrypt_and_digest(raw_message)

        cipher_b64 = b64encode(cipher_text)

        cherrypy.response.headers['Nonce'] = b64encode(response_cipher.nonce).decode()
        cherrypy.response.headers['Tag'] = b64encode(tag).decode()

        return cipher_b64

    default.exposed = True


def process(message: NetworkMessage) -> Optional[NetworkMessage]:
    logging.info(message.type)
    match message.type:
        case NetworkMessageType.PING:
            return None
        case NetworkMessageType.ADVERTISEMENT:
            process_route_advertisement(Advertisement.model_validate(message.model_extra))
            return None
        case NetworkMessageType.TICKET_REQUEST:
            return process_ticket(Ticket.model_validate(message.model_extra))
        case NetworkMessageType.TICKET_RESPONSE:
            service_ticket(Ticket.model_validate(message.model_extra))
            return None
        case NetworkMessageType.CASCADE_REQUEST:
            process_cascade_request(Cascade.model_validate(message.model_extra))
            return None
        case NetworkMessageType.CASCADE_RESPONSE:
            service_cascade_request(Cascade.model_validate(message.model_extra))
            return None
        case NetworkMessageType.MESSAGE_REQUEST:
            return NetworkMessages(
                messages=pull_messages(message.isrc),
                type=NetworkMessageType.MESSAGE_RESPONSE
            )


def pull_messages(agtuuid):
    agtuuids = []
    agtuuids.append(agtuuid)

    routes = Collection('routes', in_memory=True)

    routes_dict = {}

    for rteuuid in routes.list_objuuids():
        route = routes.get_object(rteuuid)

        try:
            if route.object['agtuuid'] in routes_dict:
                if float(routes_dict[route.object['agtuuid']]['weight']) > \
                   float(route.object['weight']):
                    routes_dict[route.object['agtuuid']] = {
                        'weight': route.object['weight'],
                        'gtwuuid': route.object['gtwuuid']
                    }
            else:
                routes_dict[route.object['agtuuid']] = {
                    'weight': route.object['weight'],
                    'gtwuuid': route.object['gtwuuid']
                }
        except:
            route.destroy()

    for k, v in routes_dict.items():
        try:
            if v['gtwuuid'] == agtuuid:
                agtuuids.append(k)
        except:
            pass

    messages = []
    for agtuuid in agtuuids:
        messages += pop_messages(dest=agtuuid)

    return messages

def forward(message):
    logging.info(message.type)
    ctr_increment('threads (forwarding)')

    Thread(target=__forward, args=(message,)).start()

def __forward(message):
    peers = Collection('peers', in_memory=True).find(agtuuid=message['dest'])

    if message['dest'] == cherrypy.config.get('agtuuid'):
        process(message)
        ctr_increment('messages forwarded')
    elif len(peers) > 0:
        try:
            if peers[0].object['url'] != None:
                client = NetworkMessageClient(
                    url=peers[0].object['url'],
                    secret_digest=cherrypy.config.get('server.secret_digest')
                )
                acknowledgement = Acknowledgement.model_validate(client.send(message))
                if acknowledgement.error:
                    logging.error(acknowledgement.error)
            else:
                push_message(message)
        except: # pylint: disable=bare-except
            logging.warning(f'''dropped message {message.get('type')}''')
            ctr_increment('messages dropped')
    else:
        weight = None
        best_route = None

        for route in Collection('routes', in_memory=True).find(agtuuid=message['dest']):
            if weight == None or float(route.object['weight']) < float(weight):
                weight = route.object['weight']
                best_route = route

        if best_route is not None:
            gtwuuid = best_route.object['gtwuuid']
        else:
            gtwuuid = None

        peers = Collection('peers', in_memory=True).find(agtuuid=gtwuuid)
        if len(peers) > 0:
            try:
                if peers[0].object['url'] != None:
                    client = NetworkMessageClient(
                        url=peers[0].object['url'],
                        secret_digest=cherrypy.config.get('server.secret_digest')
                    )

                    acknowledgement = Acknowledgement.model_validate(client.send(message))
                    if acknowledgement.error:
                        logging.error(acknowledgement.error)

                    ctr_increment('messages forwarded')
                else:
                    push_message(message)
            except:
                ctr_increment('messages dropped')
        else:
            ctr_increment('messages dropped')

    ctr_decrement('threads (forwarding)')

def anon_worker():
    register_timer(
        name='anon_worker',
        target=anon_worker,
        timeout=0.5
    ).start()

    for message in pop_messages(type='cascade response'):
        Thread(target=process, args=(message,)).start()

    for message in pop_messages(type='cascade request'):
        Thread(target=process, args=(message,)).start()

def poll(peer):
    try:
        if peer['url'] != None and peer['polling'] == True:
            client = NetworkMessageClient(
                url=peer['url'],
                secret_digest=cherrypy.config.get('server.secret_digest')
            )

            messages = NetworkMessages.model_validate(client.send(NetworkMessagesRequest()))

            for message in messages:
                Thread(target=process, args=(message,)).start()
    except: # pylint: disable=bare-except
        logging.exception('Polling messages from peer failed!')

def poll_worker():
    register_timer(
        name='poll_worker',
        target=poll_worker,
        timeout=0.5
    ).start()

    ctr_set_name('uptime', int(time() - START_TIME))

    for peer in get_peers():
        if ctr_get_name('threads (polling-{0})'.format(peer['agtuuid'])) == 0:
            ctr_increment('threads (polling-{0})'.format(peer['agtuuid']))

            Thread(target=poll, args=(peer,)).start()

def advertise(peer):
    try:
        message = create_route_advertisement()
        message['dest'] = peer['agtuuid']
        process(message)
    finally:
        ctr_decrement('threads (advertising-{0})'.format(peer['agtuuid']))

def ad_worker():
    rt = int(random() * 30.0)

    register_timer(
        name='ad_worker',
        target=ad_worker,
        timeout=rt
    ).start()

    age_routes(rt)

    for peer in get_peers():
        if ctr_get_name('threads (advertising-{0})'.format(peer['agtuuid'])) == 0:
            ctr_increment('threads (advertising-{0})'.format(peer['agtuuid']))

            Thread(target=advertise, args=(peer,)).start()

Thread(target=ad_worker).start()
Thread(target=poll_worker).start()
Thread(target=anon_worker).start()
