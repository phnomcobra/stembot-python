#!/usr/bin/python3
from time import time

import cherrypy

from stembot.audit import logging
from stembot.dao import Collection

PEER_TIMEOUT = 60
PEER_REFRESH = 60
MAX_WEIGHT = 3600

def touch_peer(agtuuid):
    if cherrypy.config.get('agtuuid') != agtuuid:
        peers = Collection('peers', in_memory=True).find(agtuuid=agtuuid)

        if len(peers) == 0:
            create_peer(agtuuid, ttl=PEER_TIMEOUT)
            logging.info(agtuuid)
        else:
            if 'refresh time' in peers[0].object:
                if peers[0].object['refresh time'] < time():
                    create_peer(agtuuid, ttl=PEER_TIMEOUT)

def delete_peer(agtuuid):
    for peer in Collection('peers', in_memory=True).find(agtuuid=agtuuid):
        peer.destroy()

    for peer in Collection('peers').find(agtuuid=agtuuid):
        peer.destroy()

def delete_peers():
    peers = Collection('peers')

    for peer in peers.find():
        peer.destroy()

    peers = Collection('peers', in_memory=True)

    for peer in peers.find():
        peer.destroy()

def create_peer(agtuuid, url=None, ttl=None, polling=False):
    collection = Collection('peers')

    peers = collection.find(agtuuid=agtuuid)

    if len(peers) == 1:
        peer = peers[0]
    else:
        peer = collection.get_object()

    peer.object = {
        'agtuuid': agtuuid,
        'url': url,
        'polling': polling
    }

    if ttl != None:
        peer.object['destroy time'] = time() + ttl
        peer.object['refresh time'] = time() + PEER_REFRESH

    peer.set()

    collection = Collection('peers', in_memory=True)

    peers = collection.find(agtuuid=agtuuid)

    if len(peers) == 1:
        peer = peers[0]
    else:
        peer = collection.get_object()

    peer.object = {
        'agtuuid': agtuuid,
        'url': url,
        'polling': polling
    }

    if ttl != None:
        peer.object['destroy time'] = time() + ttl
        peer.object['refresh time'] = time() + PEER_REFRESH

    peer.set()

    return peer

def delete_route(agtuuid, gtwuuid):
    for route in Collection('routes', in_memory=True).find(agtuuid=agtuuid, gtwuuid=gtwuuid):
        route.destroy()

def age_routes(v):
    routes = Collection('routes', in_memory=True)

    for route in routes.find():
        try:
            if route.object['weight'] > MAX_WEIGHT:
                route.destroy()
            else:
                route.object['weight'] = route.object['weight'] + v
                route.set()
        except:
            route.destroy()

def create_route(agtuuid, gtwuuid, weight, timestamp=None):
    collection = Collection('routes', in_memory=True)

    routes = collection.find(agtuuid=agtuuid, gtwuuid=gtwuuid)

    if len(routes) > 1:
        for route in routes:
            route.destroy()

        route = collection.get_object()
        route.object = {
            'gtwuuid' : gtwuuid,
            'agtuuid' : agtuuid,
            'weight' : weight
        }
        route.set()
    elif len(routes) == 1:
        route = routes[0]
        if route.object['weight'] > weight:
            route.object['weight'] = weight
            route.set()
    else:
        route = collection.get_object()
        route.object = {
            'gtwuuid': gtwuuid,
            'agtuuid': agtuuid,
            'weight': weight
        }
        route.set()

def process_route_advertisement(advertisement):
    peers = Collection('peers', in_memory=True)
    routes = Collection('routes', in_memory=True)

    ignored_peers = [cherrypy.config.get('agtuuid')]
    for peer in peers.find():
        try:
            ignored_peers.append(peer.object['agtuuid'])
        except:
            pass

    for route in advertisement['routes']:
        try:
            if route['agtuuid'] not in ignored_peers:
                create_route(
                    route['agtuuid'],
                    advertisement['agtuuid'],
                    route['weight'] + 1
                )
        except:
            pass

    prune()

def get_peers():
    peer_list = []
    peers = Collection('peers', in_memory=True)
    for peer in peers.find():
        peer_list.append(peer.object)
    return peer_list

def get_routes():
    route_list = []
    routes = Collection('routes', in_memory=True)
    for route in routes.find():
        route_list.append(route.object)
    return route_list

def prune():
    routes = Collection('routes', in_memory=True)
    peers = Collection('peers', in_memory=True)

    peer_agtuuids = []

    for peer in peers.find():
        try:
            if 'destroy time' in peer.object:
                if peer.object['destroy time'] < time():
                    peer.destroy()
                else:
                    peer_agtuuids.append(peer.object['agtuuid'])
            else:
                peer_agtuuids.append(peer.object['agtuuid'])
        except:
            peer.destroy()

    peers = Collection('peers')

    for peer in peers.find():
        try:
            if 'destroy time' in peer.object:
                if peer.object['destroy time'] < time():
                    peer.destroy()
                else:
                    peer_agtuuids.append(peer.object['agtuuid'])
            else:
                peer_agtuuids.append(peer.object['agtuuid'])
        except:
            peer.destroy()

    for route in routes.find():
        try:
            if (
                len(peers.find(agtuuid=route.object['agtuuid'])) > 0 or
                route.object['agtuuid'] == cherrypy.config.get('agtuuid') or
                route.object['gtwuuid'] not in peer_agtuuids
              ):
                route.destroy()
        except:
            route.destroy()

def create_route_advertisement():
    prune()

    routes = Collection('routes', in_memory=True)
    peers = Collection('peers', in_memory=True)

    advertisement = {}
    advertisement['type'] = 'route advertisement'
    advertisement['agtuuid'] = cherrypy.config.get('agtuuid')
    advertisement['routes'] = []

    for route in routes.find():
        try:
            if 'agtuuid' not in route.object:
                raise Exception('Invalid Route')

            if 'weight' not in route.object:
                raise Exception('Invalid Route')

            temp = {}
            temp['agtuuid'] = route.object['agtuuid']
            temp['weight'] = route.object['weight']
            temp['gtwuuid'] = cherrypy.config.get('agtuuid')

            advertisement['routes'].append(temp)
        except:
            route.destroy()

    for peer in peers.find():
        try:
            temp = {}
            temp['agtuuid'] = peer.object['agtuuid']
            temp['weight'] = 0
            temp['gtwuuid'] = cherrypy.config.get('agtuuid')

            advertisement['routes'].append(temp)
        except:
            peer.destroy()

    return advertisement

def init_peers():
    ram_peers = Collection('peers', in_memory=True)
    peers = Collection('peers')

    for objuuid in peers.list_objuuids():
        ram_peer = ram_peers.get_object(objuuid)
        ram_peer.object = peers.get_object(objuuid).object
        ram_peer.set()

collection = Collection('peers')
collection.create_attribute('agtuuid', "/agtuuid")

collection = Collection('peers', in_memory=True)
collection.create_attribute('agtuuid', "/agtuuid")

collection = Collection('routes', in_memory=True)
collection.create_attribute('agtuuid', "/agtuuid")
collection.create_attribute('gtwuuid', "/gtwuuid")
collection.create_attribute('weight', "/weight")

init_peers()