#!/usr/bin/python3
from time import time
from threading import Thread
from typing import List

from stembot.audit import logging
from stembot.executor.timers import register_timer
from stembot.dao import Collection
from stembot.types.network import NetworkMessage

MESSAGE_TIMEOUT = 60

def push_network_message(message: NetworkMessage):
    messages = Collection('messages', in_memory=True, model=NetworkMessage)
    logging.debug(f'{message.src} -> {message.type} -> {message.dest}')
    messages.upsert_object(message)


def pop_network_messages(**kargs) -> List[NetworkMessage]:
    messages = Collection('messages', in_memory=True, model=NetworkMessage)
    message_list = []
    for message in messages.find(**kargs):
        logging.debug(f'{message.object.src} -> {message.object.type} -> {message.object.dest}')
        message_list.append(message.object)
        message.destroy()
    return message_list


def expire_network_messages():
    messages = Collection('messages', in_memory=True, model=NetworkMessage)
    for message in messages.find(timestamp=f'$lt:{time()-MESSAGE_TIMEOUT}'):
        logging.warning(f'{message.object.src} -> {message.object.type} -> {message.object.dest}')
        message.destroy()


def worker():
    register_timer(
        name='message_worker',
        target=worker,
        timeout=60
    ).start()
    expire_network_messages()


collection = Collection('messages', in_memory=True, model=NetworkMessage)
collection.create_attribute('dest', "/dest")
collection.create_attribute('type', "/type")

Thread(target = worker).start()
