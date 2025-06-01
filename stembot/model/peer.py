#!/usr/bin/python3
from time import time
from typing import List

from stembot.dao import Collection
from stembot.model import kvstore
from stembot.types.network import Advertisement
from stembot.types.routing import Peer, Route

PEER_TIMEOUT = 120
PEER_REFRESH = 60
MAX_WEIGHT = 3600

def touch_peer(agtuuid):
    peers = Collection('peers', in_memory=True, model=Peer).find(agtuuid=agtuuid)

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
    for peer in Collection('peers', in_memory=True, model=Peer).find(agtuuid=agtuuid):
        peer.destroy()

    for peer in Collection('peers', model=Peer).find(agtuuid=agtuuid):
        peer.destroy()


def delete_peers():
    peers = Collection('peers', model=Peer)

    for peer in peers.find():
        peer.destroy()

    peers = Collection('peers', in_memory=True, model=Peer)

    for peer in peers.find():
        peer.destroy()


def create_peer(agtuuid, url=None, ttl=None, polling=False):
    collection = Collection('peers', model=Peer)

    peers = collection.find(agtuuid=agtuuid)

    if len(peers) == 1:
        peer = peers[0]
    else:
        peer = collection.get_object()

    peer.object.agtuuid = agtuuid
    peer.object.url = url
    peer.object.polling = polling

    if ttl:
        peer.object.destroy_time = time() + ttl
        peer.object.refresh_time = time() + PEER_REFRESH
    else:
        peer.object.destroy_time = None
        peer.object.refresh_time = None

    peer.set()

    collection = Collection('peers', in_memory=True, model=Peer)

    peers = collection.find(agtuuid=agtuuid)

    if len(peers) == 1:
        peer = peers[0]
    else:
        peer = collection.get_object()

    peer.object.agtuuid = agtuuid
    peer.object.url = url
    peer.object.polling = polling

    if ttl:
        peer.object.destroy_time = time() + ttl
        peer.object.refresh_time = time() + PEER_REFRESH
    else:
        peer.object.destroy_time = None
        peer.object.refresh_time = None

    peer.set()

    return peer


def delete_route(agtuuid, gtwuuid):
    routes = Collection('routes', in_memory=True, model=Route)
    for route in routes.find(agtuuid=agtuuid, gtwuuid=gtwuuid):
        route.destroy()


def age_routes(v):
    for route in Collection('routes', in_memory=True, model=Route).find():
        if route.object.weight > MAX_WEIGHT:
            route.destroy()
        else:
            route.object.weight = route.object.weight + v
            route.set()


def create_route(agtuuid: str, gtwuuid: str, weight: int):
    routes = Collection('routes', in_memory=True, model=Route)

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
            route.set()
    else:
        # Never seen this agtuuid/gtwuuid combination before
        # So create the route.
        routes.build_object(
            gtwuuid=gtwuuid,
            agtuuid=agtuuid,
            weight=weight
        )


def process_route_advertisement(advertisement: Advertisement):
    peers = Collection('peers', in_memory=True, model=Peer)

    ignored_agtuuids = [kvstore.get('agtuuid')] + \
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
        in Collection('peers', in_memory=True, model=Peer).find()
    ]


def get_routes() -> List[Route]:
    return [
        item.object for item
        in Collection('routes', in_memory=True, model=Route).find()
    ]


def prune():
    routes = Collection('routes', in_memory=True, model=Route)
    peers_in_ram = Collection('peers', in_memory=True, model=Peer)
    peers = Collection('peers', model=Peer)

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
            route.object.agtuuid == kvstore.get('agtuuid')
        ):
            route.destroy()


def create_route_advertisement() -> Advertisement:
    prune()

    routes = Collection('routes', in_memory=True, model=Route)
    peers = Collection('peers', in_memory=True, model=Peer)

    advertisement = Advertisement(agtuuid=kvstore.get('agtuuid'))

    for route in routes.find():
        route.object.gtwuuid = kvstore.get('agtuuid')
        advertisement.routes.append(route.object)

    for peer in peers.find(agtuuid="$!eq:None"):
        route = Route(
            agtuuid=peer.object.agtuuid,
            weight=0,
            gtwuuid=kvstore.get('agtuuid')
        )
        advertisement.routes.append(route)

    return advertisement


def init_peers():
    ram_peers = Collection('peers', in_memory=True, model=Peer)
    peers = Collection('peers', model=Peer)
    for peer in peers.find():
        ram_peers.upsert_object(peer.object)


collection = Collection('peers', model=Peer)
collection.create_attribute('agtuuid', "/agtuuid")
collection.create_attribute('polling', "/polling")
collection.create_attribute('url', "/url")

collection = Collection('peers', in_memory=True, model=Peer)
collection.create_attribute('agtuuid', "/agtuuid")
collection.create_attribute('polling', "/polling")
collection.create_attribute('url', "/url")

collection = Collection('routes', in_memory=True, model=Route)
collection.create_attribute('agtuuid', "/agtuuid")
collection.create_attribute('gtwuuid', "/gtwuuid")
collection.create_attribute('weight', "/weight")

init_peers()
