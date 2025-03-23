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

def process_ticket(message):
    ctr_increment('tickets processed')

    message['type'] = 'ticket response'
    message['src'], message['dest'] = message['dest'], message['src']

    request = message['request']
    response = {}

    try:
        logging.debug(request['type'])
        if request['type'] == 'discover peer':
            if 'ttl' in request:
                ttl = request['ttl']
            else:
                ttl = None

            if 'polling' in request:
                polling = request['polling']
            else:
                polling = False

            create_peer(
                MPIClient(
                    request['url'],
                    kvstore.get(name='secret_digest')
                ).send_json({'type': 'create info event'})['dest'],
                url=request['url'],
                ttl=ttl,
                polling=polling
            )

            response = request

        elif request['type'] == 'create peer':
            if 'url' in request:
                url = request['url']
            else:
                url = None

            if 'ttl' in request:
                ttl = request['ttl']
            else:
                ttl = None

            if 'polling' in request:
                polling = request['polling']
            else:
                polling = False

            create_peer(
                request['agtuuid'],
                url=url,
                ttl=ttl,
                polling=polling
            )

            response = request

        elif request['type'] == 'delete peers':
            delete_peers()
            response = request

        elif request['type'] == 'delete peer':
            delete_peer(request['agtuuid'])
            response = request

        elif request['type'] == 'get peers':
            response = get_peers()

        elif request['type'] == 'get routes':
            response = get_routes()




        elif request['type'] == 'get counters':
            response = ctr_get_all()




        elif request['type'] == 'file handle open':
            response['fhduuid'] = create_file_handle(
                request['filename'],
                request['mode']
            )
            response['type'] = request['type']

        elif request['type'] == 'file handle close':
            close_file_handle(request['fhduuid'])
            response = request

        elif request['type'] == 'file handle read':
            if 'size' in request:
                response['b64data'] = b64encode(
                    file_handle_read(
                        request['fhduuid'],
                        request['size']
                    )
                ).decode()
            else:
                response['b64data'] = b64encode(
                    file_handle_read(
                        request['fhduuid']
                    )
                ).decode()
            response['type'] = request['type']

        elif request['type'] == 'file handle write':
            file_handle_write(
                request['fhduuid'],
                b64decode(request['b64data'])
            )
            response = request

        elif request['type'] == 'file handle truncate':
            file_handle_truncate(request['fhduuid'], request['size'])
            response = request

        elif request['type'] == 'file handle seek':
            file_handle_seek(request['fhduuid'], request['position'])
            response = request

        elif request['type'] == 'file handle tell':
            response['position'] = file_handle_tell(request['fhduuid'])
            response['type'] = request['type']




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
    except:
        response['exception'] = traceback.format_exc()

    message['response'] = response

    return message

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
