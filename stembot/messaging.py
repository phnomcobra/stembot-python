"""Message queue and forwarding system for network message delivery.

Manages the persistent message queue for messages destined to this agent and
handles routing and forwarding of messages to other agents. Supports both direct
delivery to peers and multi-hop gateway delivery. Automatically expires old
messages and provides functions to push, pull, and pop messages from the queue.

Key features:
- In-memory message queue with persistence support
- Smart gateway selection for multi-hop message delivery
- Automatic message expiration based on timeout configuration
- Message polling for agents without direct URLs
"""

import logging

from time import time
from typing import List

from stembot.executor.agent import AgentClient
from stembot.models.config import CONFIG
from stembot.scheduling import scheduled
from stembot.dao import Collection
from stembot.models.network import Acknowledgement, NetworkMessage, NetworkMessagesRequest
from stembot.models.routing import Peer, Route

def push_network_message(message: NetworkMessage) -> None:
    """Add a message to the in-memory message queue.

    Stores a network message in the message queue for later delivery or polling.
    Messages are kept in memory until delivered or expired.

    Args:
        message: The network message to queue.
    """
    messages = Collection[NetworkMessage]('messages')
    logging.debug(message.type)
    messages.upsert_object(message)


def pull_network_messages(message: NetworkMessagesRequest) -> List[NetworkMessage]:
    """Retrieve all messages destined for an agent and messages routed through it.

    Returns messages destined for the specified agent as well as messages destined
    for other agents that route through this agent as a gateway. Useful for
    determining which messages should be processed locally vs. forwarded.

    Args:
        message: The network message request containing the agent UUID.

    Returns:
        A list of NetworkMessage objects destined for or routing through the agent.
    """
    # Find the best gateway for each destination
    gateway_map = {}
    for route in Collection[Route]('routes').find():
        if route.object.agtuuid in gateway_map:
            if gateway_map[route.object.agtuuid]['weight'] > route.object.weight:
                gateway_map[route.object.agtuuid] = {
                    'weight':  route.object.weight,
                    'gtwuuid': route.object.gtwuuid
                }
        else:
            gateway_map[route.object.agtuuid] = {
                'weight':  route.object.weight,
                'gtwuuid': route.object.gtwuuid
            }

    # Get all the agent ids that route through 'agtuuid' as a gateway
    # and include 'agtuuid'
    agtuuids = [message.isrc]
    for k, v in gateway_map.items():
        if v['gtwuuid'] == message.isrc:
            agtuuids.append(k)

    # Get all messages for the agent and messages routing through it as a gateway
    network_messages = []
    for agtuuid in agtuuids:
        network_messages.extend(pop_network_messages(dest=agtuuid))
    return network_messages


def pop_network_messages(**kwargs) -> List[NetworkMessage]:
    """Remove and return messages matching the specified criteria.

    Retrieves all messages matching the filter criteria and removes them from
    the message queue. Common criteria include 'dest' for destination agent UUID.

    Args:
        **kwargs: Query parameters to filter messages (e.g., dest='agent-uuid').

    Returns:
        A list of NetworkMessage objects matching the criteria.
    """
    messages: List[NetworkMessage] = []
    for message in Collection[NetworkMessage]('messages').find(**kwargs):
        messages.append(message.object)
        message.destroy()
    return messages

    return Collection[NetworkMessage]('messages').find_and_pop(**kwargs)


def forward_network_message(message: NetworkMessage) -> None:
    """Forward a message to its destination via direct delivery or gateway routing.

    Attempts to deliver a message to its destination agent. First tries direct
    delivery to a peer with the destination's UUID. If no direct peer is available,
    selects the best gateway based on route weights and forwards through it.
    If delivery fails and the agent polls for messages, the message is re-queued.

    Args:
        message: The network message to forward.
    """
    peers  = Collection[Peer]('peers')
    routes = Collection[Route]('routes')

    # First try direct delivery to the destination agent
    # Find a peer that a message and forward it directly.
    # If the peer is unreachable or polls for messages, push the message back to the queue.
    for peer in peers.find(agtuuid=message.dest, url="$!eq:None"):
        try:
            client = AgentClient(url=peer.object.url)

            acknowledgement = Acknowledgement(
                **client.send_network_message(message).model_dump()
            )

            if acknowledgement.error:
                logging.error(acknowledgement.error)
        except Exception as exception: # pylint: disable=broad-except
            logging.error('Failed to send network message to %s: %s', peer.object.url, exception)
            push_network_message(message)
        return

    # If no direct peer is found, find the best gateway for the destination and forward to the gateway.
    # The best gateway is the one with the lowest weight route to the destination.
    weight = None
    best_gtwuuid = None
    for route in routes.find(agtuuid=message.dest):
        if weight is None or float(route.object.weight) < float(weight):
            weight = route.object.weight
            best_gtwuuid = route.object.gtwuuid

    # If a gateway is found, forward the message to the gateway.
    # If the gateway is unreachable or polls for messages, push the message back to the queue.
    for peer in peers.find(agtuuid=best_gtwuuid, url="$!eq:None"):
        try:
            client = AgentClient(url=peer.object.url)

            acknowledgement = Acknowledgement(
                **client.send_network_message(message).model_dump()
            )

            if acknowledgement.error:
                logging.error(acknowledgement.error)
        except Exception as exception: # pylint: disable=broad-except
            logging.error('Failed to send network message to %s: %s', peer.object.url, exception)
            push_network_message(message)
        return

    push_network_message(message)


@scheduled(every_secs=CONFIG.message_timeout_secs)
def expire_network_messages() -> None:
    """Remove messages that have exceeded the configured timeout period.

    Scans the message queue for messages older than message_timeout_secs
    and removes them. Prevents old messages from accumulating indefinitely.
    """
    messages = Collection[NetworkMessage]('messages')
    for message in messages.find(timestamp=f'$lt:{time()-CONFIG.message_timeout_secs}'):
        logging.warning(message.object.type)
        logging.debug(message.object)
        message.destroy()


collection = Collection[NetworkMessage]('messages')
collection.create_attribute('dest', "/dest")
collection.create_attribute('timestamp', "/timestamp")
