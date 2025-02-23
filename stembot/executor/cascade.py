#!/usr/bin/python3
from threading import Thread
from base64 import b64encode, b64decode
from time import time, sleep

from stembot.dao import Collection
from stembot.model.messages import push_message
from stembot.model.tagging import get_tag_values
from stembot.model import kvstore
from stembot.dao.utils import get_uuid_str
from stembot.executor.counters import increment as ctr_increment
from stembot.adapter.process import process_sync
from stembot.adapter.file import file_read
from stembot.adapter.file import file_write
from stembot.adapter.python import interpret
from stembot.executor.timers import register_timer

ASYNC_CASCADE_TIMEOUT = 300
SYNC_CASCADE_TIMEOUT = 15

def service_cascade_request(message):
    ctr_increment('cascades serviced')

    cascade_response = Collection('cascade responses', in_memory=True).get_object()
    cascade_response.object = message
    cascade_response.set()

def create_anonymous_cascade_request(message):
    ctr_increment('cascades created')

    cascade_request = {
        'cscuuid': get_uuid_str(),
        'request': message['request'],
        'timestamp': time(),
        'etags': message['etags'],
        'ftags': message['ftags'],
        'src': kvstore.get(name='agtuuid'),
        'dest': None,
        'type': 'cascade request',
        'anonymous': True
    }

    Thread(target=process_cascade_request, args=(cascade_request,)).start()

def create_cascade_request(message):
    ctr_increment('cascades created')

    cascade_request = {
        'cscuuid': get_uuid_str(),
        'request': message['request'],
        'timestamp': time(),
        'etags': message['etags'],
        'ftags': message['ftags'],
        'src': kvstore.get(name='agtuuid'),
        'dest': None,
        'type': 'cascade request',
        'anonymous': False
    }

    Thread(target=process_cascade_request, args=(cascade_request,)).start()

    return cascade_request

def process_cascade_request(message):
    ctr_increment('cascades processed')

    cascade_requests = Collection('cascade requests', in_memory=True)

    try:
        if len(cascade_requests.find_objuuids(cscuuid=message['cscuuid'])) == 0:
            cascade_request = cascade_requests.get_object()
            cascade_request.object = message
            cascade_request.set()

            if len(message['ftags']) > 0:
                if len(list(set(message['ftags']) & set(get_tag_values()))) > 0:
                    Thread(target=forward_cascade_request, args=(message,)).start()
            else:
                Thread(target=forward_cascade_request, args=(message,)).start()

            if len(message['etags']) > 0:
                if len(list(set(message['etags']) & set(get_tag_values()))) > 0:
                    Thread(target=execute_cascade_request, args=(message,)).start()
            else:
                Thread(target=execute_cascade_request, args=(message,)).start()
    except:
        pass

def forward_cascade_request(message):
    ctr_increment('cascades forwarded')

    peers = Collection('peers', in_memory=True)

    for objuuid in peers.list_objuuids():
        try:
            message['dest'] = peers.get_object(objuuid).object['agtuuid']
        except:
            peers.get_object(objuuid).destroy()

        try:
            if message['dest'] != kvstore.get(name='agtuuid'):
                push_message(message)
        except:
            pass

def pop_cascade_responses(cscuuid):
    responses = Collection('cascade responses', in_memory=True)

    response_objects = []

    for objuuid in responses.find_objuuids(cscuuid=cscuuid):
        response = responses.get_object(objuuid)

        response_objects.append(response.object)
        response.destroy()

    return response_objects

def wait_on_cascade_responses(cscuuid, timeout=None):
    if timeout == None:
        sleep(SYNC_CASCADE_TIMEOUT)
    else:
        sleep(timeout)

    response_objects = []

    for response in Collection('cascade responses', in_memory=True).find(cscuuid=cscuuid):
        response_objects.append(response.object)
        response.destroy()

    for request in Collection('cascade requests', in_memory=True).find(cscuuid=cscuuid):
        request.destroy()

    return response_objects

def get_cascade_responses(cscuuid):
    response_objects = []

    for response in Collection('cascade responses', in_memory=True).find(cscuuid=cscuuid):
        response_objects.append(response.object)

    return response_objects

def execute_cascade_request(message):
    ctr_increment('cascades executed')

    request = message['request']
    response = {}

    try:
        if request['type'] == 'process sync':
            if 'timeout' in request:
                status, stdout, stderr = process_sync(
                    request['command'],
                    timeout=request['timeout']
                )
            else:
                status, stdout, stderr = process_sync(request['command'])

            response['type'] = request['type']
            response['stdout'] = b64encode(stdout).decode()
            response['stderr'] = b64encode(stderr).decode()
            response['status'] = status

            if message['anonymous'] == False:
                push_message(
                    {
                        'type': 'cascade response',
                        'dest': message['src'],
                        'cscuuid': message['cscuuid'],
                        'response': response,
                        'src': kvstore.get(name='agtuuid')
                    }
                )




        elif request['type'] == 'file read':
            response['type'] = request['type']
            response['b64data'] = b64encode(file_read(request['filename'])).decode()

            push_message(
                {
                    'type': 'cascade response',
                    'dest': message['src'],
                    'cscuuid': message['cscuuid'],
                    'response': response,
                    'src': kvstore.get(name='agtuuid')
                }
            )

        elif request['type'] == 'file write':
            file_write(request['filename'], b64decode(request['b64data']))




        elif request['type'] == 'delete route':
            for route in Collection('routes', in_memory=True).find(agtuuid=request['agtuuid']):
                route.destroy()

            for route in Collection('routes', in_memory=True).find(gtwuuid=request['agtuuid']):
                route.destroy()




        elif request['type'] == 'find collection objects':
            collection = Collection(request['name'])

            response = []

            for objuuid in collection.find_objuuids(**request['query']):
                response.append(collection.get_object(objuuid).object)

            if len(response) > 0:
                push_message(
                    {
                        'type': 'cascade response',
                        'dest': message['src'],
                        'cscuuid': message['cscuuid'],
                        'response': response,
                        'src': kvstore.get(name='agtuuid')
                    }
                )




        elif request['type'] == 'execute python':
            response['status'], response['stdout'], response['stderr'] = interpret(request['body'])

            if message['anonymous'] == False:
                push_message(
                    {
                        'type': 'cascade response',
                        'dest': message['src'],
                        'cscuuid': message['cscuuid'],
                        'response': response,
                        'src': kvstore.get(name='agtuuid')
                    }
                )
    except:
        pass

def prune():
    requests = Collection('cascade requests', in_memory=True)
    responses = Collection('cascade responses', in_memory=True)

    cscuuids = []

    for objuuid in requests.list_objuuids():
        request = requests.get_object(objuuid)

        try:
            if time() - request.object['timestamp'] > ASYNC_CASCADE_TIMEOUT:
                request.destroy()
            else:
                cscuuids.append(request.object['cscuuid'])
        except:
            request.destroy()

    for objuuid in responses.list_objuuids():
        response = responses.get_object(objuuid)

        try:
            if response.object['cscuuid'] not in cscuuids:
                response.destroy()
        except:
            response.destroy()

def worker():
    register_timer(
        name='cascade_worker',
        target=worker,
        timeout=60
    ).start()

    prune()

collection = Collection('cascade requests', in_memory=True)
collection.create_attribute('cscuuid', "['cscuuid']")

collection = Collection('cascade responses', in_memory=True)
collection.create_attribute('cscuuid', "['cscuuid']")

Thread(target=worker).start()
