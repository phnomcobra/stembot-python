#!/usr/bin/python3
import logging

from time import time
from threading import Thread
from typing import List

from stembot.executor.agent import NetworkMessageClient
from stembot.scheduling import register_timer
from stembot.dao import Collection
from stembot.models.network import Acknowledgement, NetworkMessage
from stembot.models.routing import Peer, Route

MESSAGE_TIMEOUT = 60

def push_network_message(message: NetworkMessage):
    messages = Collection[NetworkMessage]('messages', in_memory=True)
    logging.debug(message.type)
    messages.upsert_object(message)


def pull_network_messages(agtuuid: str) -> List[NetworkMessage]:
    # Find the best gateway for each destination
    gateway_map = {}
    for route in Collection[Route]('routes', in_memory=True).find():
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

    # Get all the agent ids that route through 'agtuuid' as a gateway
    # and include 'agtuuid'
    agtuuids = [agtuuid]
    for k, v in gateway_map.items():
        if v['gtwuuid'] == agtuuid:
            agtuuids.append(k)

    network_messages = []
    for network_messages_chunk in [pop_network_messages(dest=agtuuid) for agtuuid in agtuuids]:
        network_messages.extend(network_messages_chunk)

    return network_messages


def pop_network_messages(**kargs) -> List[NetworkMessage]:
    messages = Collection[NetworkMessage]('messages', in_memory=True)
    message_list = []
    for message in messages.find(**kargs):
        logging.debug('%s -> %s', message.object.type, message.object.dest)
        message_list.append(message.object)
        message.destroy()
    return message_list


def forward_network_message(message: NetworkMessage):
    peers = Collection[Peer]('peers', in_memory=True)
    routes = Collection[Route]('routes', in_memory=True)

    for peer in peers.find(agtuuid=message.dest, url="$!eq:None"):
        try:
            client = NetworkMessageClient(url=peer.object.url)

            acknowledgement = Acknowledgement.model_validate(
                client.send_network_message(message).model_extra)

            if acknowledgement.error:
                logging.error(acknowledgement.error)
        except Exception as exception: # pylint: disable=broad-except
            logging.error('Failed to send network message to %s: %s', peer.object.url, exception)
            push_network_message(message)
        return

    weight = None
    best_gtwuuid = None
    for route in routes.find(agtuuid=message.dest):
        if weight is None or float(route.object.weight) < float(weight):
            weight = route.object.weight
            best_gtwuuid = route.object.gtwuuid

    for peer in peers.find(agtuuid=best_gtwuuid, url="$!eq:None"):
        try:
            client = NetworkMessageClient(url=peer.object.url)

            acknowledgement = Acknowledgement.model_validate(
                client.send_network_message(message).model_extra)

            if acknowledgement.error:
                logging.error(acknowledgement.error)
        except: # pylint: disable=bare-except
            logging.exception('Failed to send network message to %s', peer.object.url)
            push_network_message(message)
        return

    push_network_message(message)


def expire_network_messages():
    messages = Collection[NetworkMessage]('messages', in_memory=True)
    for message in messages.find(timestamp=f'$lt:{time()-MESSAGE_TIMEOUT}'):
        logging.warning(message.object.type)
        logging.debug(message.object)
        message.destroy()


def worker():
    register_timer(
        name='message_worker',
        target=worker,
        timeout=1
    ).start()
    expire_network_messages()


collection = Collection[NetworkMessage]('messages', in_memory=True)
collection.create_attribute('dest', "/dest")
collection.create_attribute('timestamp', "/timestamp")

Thread(target=worker).start()
