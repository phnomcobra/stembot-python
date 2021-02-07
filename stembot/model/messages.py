#!/usr/bin/python3

MESSAGE_TIMEOUT = 60

from time import time
from threading import Thread, Timer, Lock
from stembot.executor.counters import increment as ctr_increment
from stembot.executor.counters import decrement as ctr_decrement
from stembot.executor.counters import get as get_ctr
from stembot.dao.ramdocument import Collection

message_lock = Lock()

def push_message(message):
    ctr_increment('messages pushed')
    ctr_increment('messages queued')
    message_lock.acquire()
    
    if 'timestamp' not in message:
        message['timestamp'] = time()
    
    messages = Collection('messages')
    new_message = messages.get_object()
    new_message.object = message
    new_message.set()
    
    message_lock.release()

def pop_messages(**kargs):
    message_lock.acquire()
    
    message_list = []
    messages = Collection('messages')
    
    for message in messages.find(**kargs):
        message_list.append(message.object)
        message.destroy()
        ctr_increment('messages popped')
        ctr_decrement('messages queued')

    message_lock.release()
    
    return message_list

def worker():
    Timer(60.0, worker).start()
    
    message_lock.acquire()
    
    messages = Collection('messages')

    for message in messages.find():
        try:
            if time() - message.object['timestamp'] > MESSAGE_TIMEOUT:
                message.destroy()

                ctr_increment('messages expired')
                ctr_decrement('messages queued')
        except:
            message.destroy()

    message_lock.release()

collection = Collection('messages')
collection.create_attribute('dest', "['dest']")
collection.create_attribute('type', "['type']")
    
Thread(target = worker).start()
