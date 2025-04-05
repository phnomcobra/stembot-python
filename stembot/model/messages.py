#!/usr/bin/python3
from time import time
from threading import Thread
from typing import List

from stembot.audit import logging
from stembot.executor.timers import register_timer
from stembot.dao import Collection
from stembot.types.network import NetworkMessage

MESSAGE_TIMEOUT = 60

def pop_messages(**kargs) -> List[NetworkMessage]:
    message_list = []
    messages = Collection('messages', in_memory=True, model=NetworkMessage)

    for message in messages.find(**kargs):
        message_list.append(message.object)
        message.destroy()

    return message_list


def worker():
    register_timer(
        name='message_worker',
        target=worker,
        timeout=60
    ).start()

    messages = Collection('messages', in_memory=True, model=NetworkMessage)

    for message in messages.find(timestamp=f'$lt:{time()-MESSAGE_TIMEOUT}'):
        logging.warning(f'{message.object.type} expired!')
        message.destroy()


collection = Collection('messages', in_memory=True, model=NetworkMessage)
collection.create_attribute('dest', "/dest")
collection.create_attribute('type', "/type")

Thread(target = worker).start()
