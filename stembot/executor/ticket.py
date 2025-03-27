#!/usr/bin/python3
from base64 import b64encode, b64decode
from time import time, sleep
from threading import Thread
import traceback

from stembot.dao import Collection
from stembot.adapter.agent import MPIClient
from stembot.audit import logging
from stembot.model.peer import create_peer
from stembot.model.peer import delete_peer
from stembot.model.peer import delete_peers
from stembot.model.peer import get_peers
from stembot.model.peer import get_routes
from stembot.model import kvstore
from stembot.adapter.python import interpret
from stembot.adapter.file import create_file_handle
from stembot.adapter.file import close_file_handle
from stembot.adapter.file import file_handle_read
from stembot.adapter.file import file_handle_write
from stembot.adapter.file import file_handle_seek
from stembot.adapter.file import file_handle_tell
from stembot.adapter.file import file_handle_truncate
from stembot.adapter.process import create_process_handle
from stembot.adapter.process import process_handle_status
from stembot.adapter.process import process_handle_kill
from stembot.adapter.process import process_handle_terminate
from stembot.adapter.process import process_handle_wait
from stembot.adapter.process import process_handle_recv
from stembot.adapter.process import process_handle_send
from stembot.adapter.process import close_process_handle
from stembot.executor.cascade import create_cascade_request
from stembot.executor.cascade import create_anonymous_cascade_request
from stembot.executor.cascade import get_cascade_responses
from stembot.executor.cascade import pop_cascade_responses
from stembot.executor.cascade import wait_on_cascade_responses
from stembot.executor.counters import increment as ctr_increment
from stembot.executor.counters import get_all as ctr_get_all
from stembot.executor.timers import register_timer
from stembot.types.network import NetworkMessage, NetworkMessageType, Ticket

ASYNC_TICKET_TIMEOUT = 3600
SYNC_TICKET_TIMEOUT = 15


def create_ticket(request):
    ctr_increment('tickets created')

    tickets = Collection('tickets', in_memory=True)

    ticket = tickets.get_object()

    ticket.object['src'] = kvstore.get(name='agtuuid')

    if 'dest' in request:
        ticket.object['dest'] = request['dest']
    else:
        ticket.object['dest'] = kvstore.get(name='agtuuid')

    ticket.object['timestamp'] = time()
    ticket.object['request'] = request
    ticket.object['response'] = None

    ticket.set()

    message = {}
    message['type'] = 'ticket request'
    message['src'] = ticket.object['src']
    message['request'] = ticket.object['request']
    message['dest'] = ticket.object['dest']
    message['tckuuid'] = ticket.object['objuuid']

    return message

def process_ticket(ticket: Ticket) -> Ticket:
    ctr_increment('tickets processed')


    ticket.src, ticket.dest = ticket.dest, ticket.src
    ticket.type = NetworkMessageType.TICKET_RESPONSE


    try:
        logging.debug(ticket['type'])
        if ticket['type'] == 'discover peer':
            if 'ttl' in ticket:
                ttl = ticket['ttl']
            else:
                ttl = None

            if 'polling' in ticket:
                polling = ticket['polling']
            else:
                polling = False

            create_peer(
                MPIClient(
                    ticket['url'],
                    kvstore.get(name='secret_digest')
                ).send_json({'type': 'create info event'})['dest'],
                url=ticket['url'],
                ttl=ttl,
                polling=polling
            )

        elif ticket['type'] == 'create peer':
            if 'url' in ticket:
                url = ticket['url']
            else:
                url = None

            if 'ttl' in ticket:
                ttl = ticket['ttl']
            else:
                ttl = None

            if 'polling' in ticket:
                polling = ticket['polling']
            else:
                polling = False

            create_peer(
                ticket['agtuuid'],
                url=url,
                ttl=ttl,
                polling=polling
            )

        elif ticket['type'] == 'delete peers':
            delete_peers()

        elif ticket['type'] == 'delete peer':
            delete_peer(ticket['agtuuid'])

        elif ticket['type'] == 'get peers':
            ticket.response = get_peers()

        elif ticket['type'] == 'get routes':
            ticket.response = get_routes()




        elif ticket['type'] == 'get counters':
            ticket.response = ctr_get_all()





        '''

        elif request['type'] == 'process handle create':
            response['phduuid'] = create_process_handle(request['command'])
            response['type'] = request['type']

        elif request['type'] == 'process handle status':
            response['status'] = process_handle_status(request['phduuid'])

        elif request['type'] == 'process handle kill':
            process_handle_kill(request['phduuid'])
            response = request

        elif request['type'] == 'process handle terminate':
            process_handle_terminate(request['phduuid'])
            response = request

        elif request['type'] == 'process handle wait':
            process_handle_wait(request['phduuid'])
            response = request

        elif request['type'] == 'process handle close':
            close_process_handle(request['phduuid'])
            response = request

        elif request['type'] == 'process handle send':
            process_handle_send(request['phduuid'], b64decode(request['b64data']))
            response = request

        elif request['type'] == 'process handle recv':
            stdout, stderr = process_handle_recv(request['phduuid'])
            response['stdout b64data'] = b64encode(stdout).decode()
            response['stderr b64data'] = b64encode(stderr).decode()
            response['type'] = request['type']




        elif request['type'] == 'create cascade async':
            response = create_cascade_request(request)

        elif request['type'] == 'create cascade anon':
            create_anonymous_cascade_request(request)
            response = request

        elif request['type'] == 'create cascade sync':
            if 'timeout' in request:
                response = wait_on_cascade_responses(
                    create_cascade_request(request)['cscuuid'],
                    request['timeout']
                )
            else:
                response = wait_on_cascade_responses(
                    create_cascade_request(request)['cscuuid']
                )

        elif request['type'] == 'get cascade responses':
            response = get_cascade_responses(request['cscuuid'])

        elif request['type'] == 'pull cascade responses':
            response = pop_cascade_responses(request['cscuuid'])




        elif request['type'] == 'delete collection':
            Collection(request['name']).destroy()
            response = request

        elif request['type'] == 'create collection attribute':
            Collection(request['name']).create_attribute(
                request['attribute'],
                request['path']
            )
            response = request

        elif request['type'] == 'delete collection attribute':
            Collection(request['name']).delete_attribute(request['attribute'])
            response = request

        elif request['type'] == 'find collection objects':
            response = []

            for temp in Collection(request['name']).find(**request['query']):
                response.append(temp.object)

        elif request['type'] == 'find collection object uuids':
            response = Collection(request['name']).find_objuuids(**request['query'])

        elif request['type'] == 'get collection object':
            if 'objuuid' in request:
                response = Collection(request['name']).get_object(request['objuuid']).object
            else:
                response = Collection(request['name']).get_object().object

        elif request['type'] == 'set collection object':
            response = request
            c = Collection(request['name'])
            o = c.get_object(request['object']['objuuid'])
            o.object = request['object']
            o.set()

        elif request['type'] == 'delete collection object':
            response = request
            Collection(request['name']).get_object(request['objuuid']).destroy()

        elif request['type'] == 'list collection object uuids':
            response = Collection(request['name']).list_objuuids()




        elif request['type'] == 'ping':
            response = request




        elif request['type'] == 'execute python':
            response['status'], response['stdout'], response['stderr'] = interpret(request['body'])




        else:
            raise Exception('Unknown request type!')
        '''
    except: # pylint: disable=bare-except
        ticket.error = traceback.format_exc()

    return ticket

def service_ticket(message):
    ctr_increment('tickets serviced')

    tickets = Collection('tickets', in_memory=True)

    ticket = tickets.get_object(message['tckuuid'])
    ticket.object['response'] = message['response']
    ticket.set()

def wait_on_ticket_response(tckuuid, timeout=None):
    tickets = Collection('tickets', in_memory=True)

    if timeout == None:
        timeout = SYNC_TICKET_TIMEOUT

    while True:
        ticket = tickets.get_object(tckuuid)

        if time() - ticket.object['timestamp'] > timeout:
            ticket.destroy()
            raise Exception('Ticket timeout period reached!')

        if ticket.object['response'] != None:
            response = ticket.object['response']
            ticket.destroy()
            break

        sleep(1.0)

    return response

def get_ticket_response(tckuuid):
    tickets = Collection('tickets', in_memory=True)
    ticket = tickets.get_object(tckuuid)
    response = ticket.object['response']
    return response

def delete_ticket(tckuuid):
    Collection('tickets', in_memory=True).get_object(tckuuid).destroy()

def worker():
    tickets = Collection('tickets', in_memory=True)

    for objuuid in tickets.list_objuuids():
        ticket = tickets.get_object(objuuid)

        try:
            if time() - ticket.object['timestamp'] > ASYNC_TICKET_TIMEOUT:
                ticket.destroy()
                ctr_increment('tickets expired')
        except:
            ticket.destroy()

    register_timer(
        name='ticket_worker',
        target=worker,
        timeout=ASYNC_TICKET_TIMEOUT
    ).start()

Thread(target=worker).start()
