#!/usr/bin/python3

import cherrypy
import json
import traceback

from Crypto.Cipher import AES
from random import random, randrange
from threading import Thread, Timer, Lock
from base64 import b64encode, b64decode
from time import time, sleep

from stembot.adapter.agent import MPIClient
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

START_TIME = time()

class MPI(object):
    @cherrypy.expose
    def default(self):
        cl = cherrypy.request.headers['Content-Length']
        cipher_b64 = cherrypy.request.body.read(int(cl))
        ctr_increment('bytes recv (cherrypy)', len(cipher_b64))
        cipher_text = b64decode(cipher_b64)

        nonce = b64decode(cherrypy.request.headers['Nonce'].encode())
        tag = b64decode(cherrypy.request.headers['Tag'].encode())
        key = b64decode(cherrypy.config.get('server.secret_digest'))[:16]
        request_cipher = AES.new(key, AES.MODE_EAX, nonce=nonce)

        raw_message = request_cipher.decrypt(cipher_text)
        request_cipher.verify(tag)

        message_in = json.loads(raw_message.decode())

        message_in['timestamp'] = time()

        if 'isrc' in message_in:
            touch_peer(message_in['isrc'])

        if 'dest' not in message_in:
            message_in['dest'] = cherrypy.config.get('agtuuid')
        elif message_in['dest'] == None:
            message_in['dest'] = cherrypy.config.get('agtuuid')

        message_out = process(message_in)

        raw_message = json.dumps(message_out).encode()

        response_cipher = AES.new(key, AES.MODE_EAX)

        cipher_text, tag = response_cipher.encrypt_and_digest(raw_message)

        cipher_b64 = b64encode(cipher_text)
        ctr_increment('bytes sent (cherrypy)', len(cipher_b64))

        cherrypy.response.headers['Nonce'] = b64encode(response_cipher.nonce).decode()
        cherrypy.response.headers['Tag'] = b64encode(tag).decode()

        return cipher_b64

    default.exposed = True

def process(message_in):
    ctr_increment('threads (processing)')
    message_out = __process(message_in)
    ctr_decrement('threads (processing)')
    return message_out

def __process(message):
    ctr_increment('messages processed')

    if message['dest'] == cherrypy.config.get('agtuuid'):
        logging.debug(message['type'])
        if message['type'] == 'create peer':
            if 'url' in message:
                url = message['url']
            else:
                url = None

            if 'ttl' in message:
                ttl = message['ttl']
            else:
                ttl = None

            if 'polling' in message:
                polling = message['polling']
            else:
                polling = False

            create_peer(
                message['agtuuid'],
                url=url,
                ttl=ttl,
                polling=polling
            )

            return message

        elif message['type'] == 'delete peers':
            delete_peers()
            return message

        elif message['type'] == 'delete peer':
            delete_peer(message['agtuuid'])
            return message

        elif message['type'] == 'get peers':
            return get_peers()

        elif message['type'] == 'get routes':
            return get_routes()

        elif message['type'] == 'route advertisement':
            process_route_advertisement(message)
            return message

        elif message['type'] == 'discover peer':
            if 'ttl' in message:
                ttl = message['ttl']
            else:
                ttl = None

            if 'polling' in message:
                polling = message['polling']
            else:
                polling = False

            return discover_peer(
                message['url'],
                ttl=ttl,
                polling=polling
            )




        elif message['type'] == 'create info event':
            return message




        elif message['type'] == 'get counters':
            return ctr_get_all()




        elif message['type'] == 'pull messages':
            st = time()

            messages = pull_messages(message['isrc'])

            while len(messages) == 0 and \
                  time() - st < 5.0:
                sleep(0.5)

                messages = pull_messages(message['isrc'])

            return messages




        elif message['type'] == 'ticket request':
            process(process_ticket(message))
            return message

        elif message['type'] == 'ticket response':
            service_ticket(message)
            return message

        elif message['type'] == 'create sync ticket':
            ticket_message = create_ticket(message['request'])
            forward(ticket_message)
            if 'timeout' in message:
                return wait_on_ticket_response(ticket_message['tckuuid'], message['timeout'])
            else:
                return wait_on_ticket_response(ticket_message['tckuuid'])

        elif message['type'] == 'create async ticket':
            ticket_message = create_ticket(message['request'])
            logging.debug(ticket_message)
            forward(ticket_message)
            return ticket_message

        elif message['type'] == 'get ticket response':
            return get_ticket_response(message['tckuuid'])

        elif message['type'] == 'delete ticket':
            delete_ticket(message['tckuuid'])
            return message




        elif message['type'] == 'cascade request':
            process_cascade_request(message)
            return message

        elif message['type'] == 'cascade response':
            service_cascade_request(message)
            return message

        elif message['type'] == 'create cascade sync':
            if 'timeout' in message:
                return wait_on_cascade_responses(create_cascade_request(message)['cscuuid'], message['timeout'])
            else:
                return wait_on_cascade_responses(create_cascade_request(message)['cscuuid'])
    else:
        forward(message)
        return message

def discover_peer(url, ttl, polling):
    message_in = {
        'type': 'create info event',
        'message': 'Agent Hello'
    }

    message_out = MPIClient(
        url,
        cherrypy.config.get('server.secret_digest')
    ).send_json(message_in)

    peer = create_peer(
        message_out['dest'],
        url=url,
        ttl=ttl,
        polling=polling
    )

    return peer.object

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
                MPIClient(
                    peers[0].object['url'],
                    cherrypy.config.get('server.secret_digest')
                ).send_json(message)

                ctr_increment('messages forwarded')
            else:
                push_message(message)
        except:
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
                    MPIClient(
                        peers[0].object['url'],
                        cherrypy.config.get('server.secret_digest')
                    ).send_json(message)

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
        message = {}
        message['dest'] = peer['agtuuid']
        message['type'] = 'pull messages'

        if peer['url'] != None and peer['polling'] == True:
            messages = MPIClient(
                peer['url'],
                cherrypy.config.get('server.secret_digest')
            ).send_json(message)

            for message in messages:
                Thread(target=process, args=(message,)).start()
    finally:
        ctr_decrement('threads (polling-{0})'.format(peer['agtuuid']))

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
