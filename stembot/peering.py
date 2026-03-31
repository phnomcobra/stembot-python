#!/usr/bin/python3
from time import time
from typing import List

import cherrypy

from stembot.dao import Collection
from stembot.types.network import Advertisement
from stembot.types.routing import Peer, Route

PEER_TIMEOUT = 60
PEER_REFRESH = 30
MAX_WEIGHT = 600

def touch_peer(agtuuid):
    peers = Collection[Peer]('peers', in_memory=True).find(agtuuid=agtuuid)

    if len(peers) == 0:
        create_peer(agtuuid, ttl=PEER_TIMEOUT)
    else:
        if (
            not peers[0].object.url and
            peers[0].object.refresh_time and
            peers[0].object.refresh_time < time()
        ):
            create_peer(agtuuid, ttl=PEER_TIMEOUT)


def delete_peer(agtuuid):
    for peer in Collection[Peer]('peers', in_memory=True).find(agtuuid=agtuuid):
        peer.destroy()

    for peer in Collection[Peer]('peers').find(agtuuid=agtuuid):
        peer.destroy()


def delete_peers():
    peers = Collection[Peer]('peers')

    for peer in peers.find():
        peer.destroy()

    peers = Collection[Peer]('peers', in_memory=True)

    for peer in peers.find():
        peer.destroy()


def create_peer(agtuuid, url=None, ttl=None, polling=False):
    peer_collection = Collection[Peer]('peers')

    peers = peer_collection.find(agtuuid=agtuuid)

    if len(peers) == 1:
        peer = peers[0]
    else:
        peer = peer_collection.get_object()

    peer.object.agtuuid = agtuuid
    peer.object.url     = url
    peer.object.polling = polling

    if ttl:
        peer.object.destroy_time = time() + ttl
        peer.object.refresh_time = time() + PEER_REFRESH
    else:
        peer.object.destroy_time = None
        peer.object.refresh_time = None

    peer.commit()

    peer_collection_in_memory = Collection[Peer]('peers', in_memory=True)

    peers = peer_collection_in_memory.find(agtuuid=agtuuid)

    if len(peers) == 1:
        peer = peers[0]
    else:
        peer = peer_collection_in_memory.get_object()

    peer.object.agtuuid = agtuuid
    peer.object.url     = url
    peer.object.polling = polling

    if ttl:
        peer.object.destroy_time = time() + ttl
        peer.object.refresh_time = time() + PEER_REFRESH
    else:
        peer.object.destroy_time = None
        peer.object.refresh_time = None

    peer.commit()

    return peer


def delete_route(agtuuid, gtwuuid):
    routes = Collection[Route]('routes', in_memory=True)
    for route in routes.find(agtuuid=agtuuid, gtwuuid=gtwuuid):
        route.destroy()


def age_routes(v):
    for route in Collection[Route]('routes', in_memory=True).find():
        if route.object.weight > MAX_WEIGHT:
            route.destroy()
        else:
            route.object.weight = route.object.weight + v
            route.commit()


def create_route(agtuuid: str, gtwuuid: str, weight: int):
    routes = Collection[Route]('routes', in_memory=True)

    matches = routes.find(agtuuid=agtuuid, gtwuuid=gtwuuid)

    if len(matches) > 1:
        # Shouldn't be more the 1 route agtuuid/gtwuuid
        # If so, empty the collection and create a new route
        for route in matches:
            route.destroy()

        routes.build_object(
            gtwuuid=gtwuuid,
            agtuuid=agtuuid,
            weight=weight
        )
    elif len(matches) == 1:
        # Already have this route but at a higher weight
        # Set the weight to the lower, incoming weight
        route = matches[0]
        if route.object.weight > weight:
            route.object.weight = weight
            route.commit()
    else:
        # Never seen this agtuuid/gtwuuid combination before
        # So create the route.
        routes.build_object(
            gtwuuid=gtwuuid,
            agtuuid=agtuuid,
            weight=weight
        )


def process_route_advertisement(advertisement: Advertisement):
    peers = Collection[Peer]('peers', in_memory=True)

    ignored_agtuuids = [cherrypy.config.get('agtuuid')] + \
                       [peer.object.agtuuid for peer in peers.find()]

    for route in [r for r in advertisement.routes if r.agtuuid not in ignored_agtuuids]:
        create_route(
            route.agtuuid,
            advertisement.agtuuid,
            route.weight + 1
        )

    prune()


def get_peers() -> List[Peer]:
    return [
        item.object for item
        in Collection[Peer]('peers', in_memory=True).find()
    ]


def get_routes() -> List[Route]:
    return [
        item.object for item
        in Collection[Route]('routes', in_memory=True).find()
    ]


def prune():
    routes       = Collection[Route]('routes', in_memory=True)
    peers_in_ram = Collection[Peer]('peers', in_memory=True)
    peers        = Collection[Peer]('peers')

    peer_agtuuids = []

    for peer in peers.find() + peers_in_ram.find():
        if peer.object.destroy_time and peer.object.destroy_time < time():
            peer.destroy()
            continue
        peer_agtuuids.append(peer.object.agtuuid)

    for route in routes.find():
        if (
            route.object.gtwuuid not in peer_agtuuids or
            len(peers_in_ram.find_objuuids(agtuuid=route.object.agtuuid)) > 0 or
            route.object.agtuuid == cherrypy.config.get('agtuuid')
        ):
            route.destroy()


# pylint: disable=no-member
def create_route_advertisement() -> Advertisement:
    prune()

    routes = Collection[Route]('routes', in_memory=True)
    peers = Collection[Peer]('peers', in_memory=True)

    advertisement = Advertisement(agtuuid=cherrypy.config.get('agtuuid'))

    for route in routes.find():
        route.object.gtwuuid = cherrypy.config.get('agtuuid')
        advertisement.routes.append(route.object)

    for peer in peers.find(agtuuid="$!eq:None"):
        route = Route(
            agtuuid=peer.object.agtuuid,
            weight=0,
            gtwuuid=cherrypy.config.get('agtuuid')
        )
        advertisement.routes.append(route)

    return advertisement


def init_peers():
    ram_peers = Collection[Peer]('peers', in_memory=True)
    peers = Collection[Peer]('peers')
    for peer in peers.find():
        ram_peers.upsert_object(peer.object)


collection = Collection[Peer]('peers')
collection.create_attribute('agtuuid', "/agtuuid")
collection.create_attribute('polling', "/polling")
collection.create_attribute('url', "/url")

collection = Collection[Peer]('peers', in_memory=True)
collection.create_attribute('agtuuid', "/agtuuid")
collection.create_attribute('polling', "/polling")
collection.create_attribute('url', "/url")

collection = Collection[Route]('routes', in_memory=True)
collection.create_attribute('agtuuid', "/agtuuid")
collection.create_attribute('gtwuuid', "/gtwuuid")
collection.create_attribute('weight', "/weight")

init_peers()
