#!/usr/bin/python

PEER_TIMEOUT = 60
PEER_REFRESH = 60
MAX_WEIGHT = 3600

import cherrypy
import traceback

from time import time
from document import Collection as SQLCollection
from ramdocument import Collection as RAMCollection

def touch_peer(agtuuid):
    if cherrypy.config.get("agtuuid") != agtuuid:
        peers = RAMCollection("peers").find(agtuuid = agtuuid)
        
        if len(peers) == 0:
            create_peer(agtuuid, ttl = PEER_TIMEOUT)
        else:
            if "refresh time" in peers[0].object:
                if peers[0].object["refresh time"] < time():
                    create_peer(agtuuid, ttl = PEER_TIMEOUT)

def delete_peer(agtuuid):
    for peer in RAMCollection("peers").find(agtuuid = agtuuid):
        peer.destroy()
    
    for peer in SQLCollection("peers").find(agtuuid = agtuuid):
        peer.destroy()

def delete_peers():
    peers = SQLCollection("peers")
    
    for peer in peers.find():
        peer.destroy()
    
    peers = RAMCollection("peers")
    
    for peer in peers.find():
        peer.destroy()

def create_peer(agtuuid, url = None, ttl = None, polling = False):
    collection = SQLCollection("peers")
    
    peers = collection.find(agtuuid = agtuuid)
    
    if len(peers) == 1:
        peer = peers[0]
    else:
        peer = collection.get_object()
    
    peer.object = {
        "agtuuid" : agtuuid,
        "url" : url,
        "polling" : polling
    }
    
    if ttl != None:
        peer.object["destroy time"] = time() + ttl
        peer.object["refresh time"] = time() + PEER_REFRESH
    
    peer.set()
    
    collection = RAMCollection("peers")
    
    peers = collection.find(agtuuid = agtuuid)
    
    if len(peers) == 1:
        peer = peers[0]
    else:
        peer = collection.get_object()
    
    peer.object = {
        "agtuuid" : agtuuid,
        "url" : url,
        "polling" : polling
    }
    
    if ttl != None:
        peer.object["destroy time"] = time() + ttl
        peer.object["refresh time"] = time() + PEER_REFRESH
    
    peer.set()
    
    return peer
    
def delete_route(agtuuid, gtwuuid):
    for route in RAMCollection("routes").find(agtuuid = agtuuid, gtwuuid = gtwuuid):
        route.destroy()

def age_routes(v):
    routes = RAMCollection("routes")
    
    for route in routes.find():
        try:
            if route.object["weight"] > MAX_WEIGHT:
                route.destroy()
            else:
                route.object["weight"] = route.object["weight"] + v
                route.set()
        except:
            route.destroy()

def create_route(agtuuid, gtwuuid, weight, timestamp = None):
    collection = RAMCollection("routes")
    
    routes = collection.find(agtuuid = agtuuid, gtwuuid = gtwuuid)
    
    if len(routes) > 1:
        for route in routes:
            route.destroy()
        
        route = collection.get_object()
        route.object = {
            "gtwuuid" : gtwuuid,
            "agtuuid" : agtuuid,
            "weight" : weight,
            #"timestamp" : timestamp
        }
        route.set()
    elif len(routes) == 1:
        route = routes[0]
        if route.object["weight"] > weight:
            route.object["weight"] = weight
            route.set()

        '''
        if route.object["timestamp"] < timestamp:
            route.object["timestamp"] = timestamp
            route.set()
        '''
    else:
        route = collection.get_object()
        route.object = {
            "gtwuuid" : gtwuuid,
            "agtuuid" : agtuuid,
            "weight" : weight,
        }
        route.set()

def process_route_advertisement(advertisement):
    peers = RAMCollection("peers")
    routes = RAMCollection("routes")
    
    ignored_peers = [cherrypy.config.get("agtuuid")]
    for peer in peers.find():
        try:
            ignored_peers.append(peer.object["agtuuid"])
        except:
            pass
    
    for route in advertisement["routes"]:
        try:
            if route["agtuuid"] not in ignored_peers:
                create_route(route["agtuuid"], \
                             advertisement["agtuuid"], \
                             route["weight"] + 1)
        except:
            pass
    
    prune()

def get_peers():
    peer_list = []
    peers = RAMCollection("peers")
    for peer in peers.find():
        peer_list.append(peer.object)
    return peer_list

def get_routes():
    route_list = []
    routes = RAMCollection("routes")
    for route in routes.find():
        route_list.append(route.object)
    return route_list
    
def prune():
    routes = RAMCollection("routes")
    peers = RAMCollection("peers")
    
    peer_agtuuids = []
    
    for peer in peers.find():
        try:
            if "destroy time" in peer.object:
                if peer.object["destroy time"] < time():
                    peer.destroy()
                else:
                    peer_agtuuids.append(peer.object["agtuuid"])
            else:
                peer_agtuuids.append(peer.object["agtuuid"])
        except:
            peer.destroy()
    
    peers = SQLCollection("peers")
    
    for peer in peers.find():
        try:
            if "destroy time" in peer.object:
                if peer.object["destroy time"] < time():
                    peer.destroy()
                else:
                    peer_agtuuids.append(peer.object["agtuuid"])
            else:
                peer_agtuuids.append(peer.object["agtuuid"])
        except:
            peer.destroy()
    
    for route in routes.find():
        try:
            if len(peers.find(agtuuid = route.object["agtuuid"])) > 0 or \
               route.object["agtuuid"] == cherrypy.config.get("agtuuid") or \
               route.object["gtwuuid"] not in peer_agtuuids:
                route.destroy()
        except:
            route.destroy()

def create_route_advertisement():
    prune()
    
    routes = RAMCollection("routes")
    peers = RAMCollection("peers")
     
    advertisement = {}
    advertisement["type"] = "route advertisement"
    advertisement["agtuuid"] = cherrypy.config.get("agtuuid")
    advertisement["routes"] = []
    
    for route in routes.find():
        try:
            if "agtuuid" not in route.object:
                raise Exception("Invalid Route")
            
            if "weight" not in route.object:
                raise Exception("Invalid Route")
                
            temp = {}
            temp["agtuuid"] = route.object["agtuuid"]
            temp["weight"] = route.object["weight"]
            temp["gtwuuid"] = cherrypy.config.get("agtuuid")

            advertisement["routes"].append(temp)
        except:
            route.destroy()

    for peer in peers.find():
        try:
            temp = {}
            temp["agtuuid"] = peer.object["agtuuid"]
            temp["weight"] = 0
            temp["gtwuuid"] = cherrypy.config.get("agtuuid")

            advertisement["routes"].append(temp)
        except:
            peer.destroy()

    return advertisement

def init_peers():
    ram_peers = RAMCollection("peers")
    peers = SQLCollection("peers")
    
    for objuuid in peers.list_objuuids():
        ram_peer = ram_peers.get_object(objuuid)
        ram_peer.object = peers.get_object(objuuid).object
        ram_peer.set()

collection = SQLCollection("peers")
collection.create_attribute("agtuuid", "['agtuuid']")

collection = RAMCollection("peers")
collection.create_attribute("agtuuid", "['agtuuid']")

collection = RAMCollection("routes")
collection.create_attribute("agtuuid", "['agtuuid']")
collection.create_attribute("gtwuuid", "['gtwuuid']")
collection.create_attribute("weight", "['weight']")

init_peers()