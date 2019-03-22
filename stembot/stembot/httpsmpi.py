#!/usr/bin/python

import cherrypy
import json
import traceback
import urllib2
import ssl
import hashlib

from random import random, randrange
from threading import Thread, Timer, Lock
from base64 import b64encode, b64decode
from time import time, sleep

import script

from httpsint import send_json
from ticket import process_ticket, \
                   service_ticket, \
                   create_ticket, \
                   wait_on_ticket_response, \
                   get_ticket_response, \
                   delete_ticket
from ramdocument import Collection as RAMCollection
from messages import pop_messages, \
                     push_message
from peer import create_peer, \
                 touch_peer, \
                 delete_peer, \
                 delete_peers, \
                 process_route_advertisement, \
                 get_peers, \
                 get_routes, \
                 age_routes, \
                 delete_route, \
                 create_route_advertisement
from cascade import process_cascade_request, \
                    service_cascade_request, \
                    wait_on_cascade_responses, \
                    create_cascade_request
from counters import increment as ctr_increment, \
                     decrement as ctr_decrement, \
                     get_all as ctr_get_all, \
                     get as ctr_get_name, \
                     set as ctr_set_name

START_TIME = time()

class MPI(object):
    @cherrypy.expose
    def default(self):
        ctr_increment("threads (cherrypy)")
        
        cl = cherrypy.request.headers['Content-Length']
        sg = cherrypy.request.headers['Signature']
        
        raw_message = cherrypy.request.body.read(int(cl))
        ctr_increment("bytes recv (cherrypy)", len(raw_message.encode("utf-8")))
        message_in = json.loads(raw_message)
        
        h = hashlib.sha256()
        h.update(cherrypy.config.get("server.secret_digest"))
        h.update(raw_message)
        
        if h.hexdigest() != sg:
            cherrypy.response.status = 403
            ctr_decrement("threads (cherrypy)")
            return "Signature mismatch encountered!"
        else:
            message_in["timestamp"] = time()
            
            if "isrc" in message_in:
                touch_peer(message_in["isrc"])
    
            if "dest" not in message_in:
                message_in["dest"] = cherrypy.config.get("agtuuid")
            elif message_in["dest"] == None:
                message_in["dest"] = cherrypy.config.get("agtuuid")
            
            message_out = process(message_in)
            
            raw_message = json.dumps(message_out)
            ctr_increment("bytes sent (cherrypy)", len(raw_message.encode("utf-8")))
        
            h = hashlib.sha256()
            h.update(cherrypy.config.get("server.secret_digest"))
            h.update(raw_message)
        
            cherrypy.response.headers['Signature'] = h.hexdigest()
            ctr_decrement("threads (cherrypy)")
            return raw_message

    default.exposed = True

def process(message_in):
    ctr_increment("threads (processing)")
    message_out = __process(message_in)
    ctr_decrement("threads (processing)")
    return message_out

def __process(message):
    ctr_increment("messages processed")

    if message["dest"] == cherrypy.config.get("agtuuid"):
        if message["type"] == "create peer":
            if "url" in message:
                url = message["url"]
            else:
                url = None
            
            if "ttl" in message:
                ttl = message["ttl"]
            else:
                ttl = None
            
            if "polling" in message:
                polling = message["polling"]
            else:
                polling = False
            
            create_peer(message["agtuuid"], \
                        url = url, \
                        ttl = ttl, \
                        polling = polling)
            
            return message
        
        elif message["type"] == "delete peers":
            delete_peers()
            return message
            
        elif message["type"] == "delete peer":
            delete_peer(message["agtuuid"])
            return message
            
        elif message["type"] == "get peers":
            return get_peers()
        
        elif message["type"] == "get routes":
            return get_routes()
            
        elif message["type"] == "route advertisement":
            process_route_advertisement(message)
            return message
        
        elif message["type"] == "discover peer":
            if "ttl" in message:
                ttl = message["ttl"]
            else:
                ttl = None
            
            if "polling" in message:
                polling = message["polling"]
            else:
                polling = False
                
            return discover_peer(message["url"], \
                                 ttl = ttl, \
                                 polling = polling)



            
        elif message["type"] == "create info event":
            return message
        
        
        
        
        elif message["type"] == "get counters":
            return ctr_get_all()
            
            
            
            
        elif message["type"] == "pull messages":
            st = time()
            
            messages = pull_messages(message["isrc"])
            
            while len(messages) == 0 and \
                  time() - st < 5.0:
                sleep(0.5)
                
                messages = pull_messages(message["isrc"])

            return messages

            
            
            
        elif message["type"] == "ticket request":
            process(process_ticket(message))
            return message
            
        elif message["type"] == "ticket response":
            service_ticket(message)
            return message
            
        elif message["type"] == "create sync ticket":
            ticket_message = create_ticket(message["request"])
            forward(ticket_message)
            if "timeout" in message:
                return wait_on_ticket_response(ticket_message["tckuuid"], message["timeout"])
            else:
                return wait_on_ticket_response(ticket_message["tckuuid"])

        elif message["type"] == "create async ticket":
            ticket_message = create_ticket(message["request"])
            forward(ticket_message)
            return ticket_message
            
        elif message["type"] == "get ticket response":
            return get_ticket_response(message["tckuuid"])

        elif message["type"] == "delete ticket":
            delete_ticket(message["tckuuid"])
            return message
        
        
        
        
        elif message["type"] == "cascade request":
            process_cascade_request(message)
            return message
            
        elif message["type"] == "cascade response":
            service_cascade_request(message)
            return message
        
        elif message["type"] == "create cascade sync":
            if "timeout" in message:
                return wait_on_cascade_responses(create_cascade_request(message)["cscuuid"], message["timeout"])
            else:
                return wait_on_cascade_responses(create_cascade_request(message)["cscuuid"])
        
            
        
        
    else:
        forward(message)
        return message

def discover_peer(url, ttl, polling):
    message_in = {
        "type" : "create info event",
        "message" : "Agent Hello"
    }
    
    message_out = send_json(url, message_in)
    
    peer = create_peer(message_out["dest"], \
                       url = url, \
                       ttl = ttl, \
                       polling = polling)
            
    return peer.object

def pull_messages(agtuuid):
    agtuuids = []
    agtuuids.append(agtuuid)
    
    routes = RAMCollection("routes")
    
    routes_dict = {}
    
    for rteuuid in routes.list_objuuids():
        route = routes.get_object(rteuuid)
        
        try:
            if route.object["agtuuid"] in routes_dict:
                if float(routes_dict[route.object["agtuuid"]]["weight"]) > \
                   float(route.object["weight"]):
                    routes_dict[route.object["agtuuid"]] = {
                        "weight" : route.object["weight"],
                        "gtwuuid" : route.object["gtwuuid"]
                    }    
            else:
                routes_dict[route.object["agtuuid"]] = {
                    "weight" : route.object["weight"],
                    "gtwuuid" : route.object["gtwuuid"]
                }
        except:
            route.destroy()
            
    for k, v in routes_dict.iteritems():
        try:
            if v["gtwuuid"] == agtuuid:
                agtuuids.append(k)
        except:
            pass
    
    messages = []
    for agtuuid in agtuuids:
        messages += pop_messages(dest = agtuuid)
    
    return messages

def forward(message):
    ctr_increment("threads (forwarding)")
    
    Thread(target = __forward, args = (message,)).start()

def __forward(message):
    peers = RAMCollection("peers").find(agtuuid = message["dest"])
    
    if message["dest"] == cherrypy.config.get("agtuuid"):
        process(message)
        ctr_increment("messages forwarded")
    elif len(peers) > 0:
        try:
            if peers[0].object["url"] != None:
                send_json(peers[0].object["url"], message)
                ctr_increment("messages forwarded")
            else:
                push_message(message)
        except:
            ctr_increment("messages dropped")
    else:
        weight = None
        best_route = None
        
        for route in RAMCollection("routes").find(agtuuid = message["dest"]):
            if weight == None or \
               float(route.object["weight"]) < float(weight):
                weight = route.object["weight"]
                best_route = route
        
        if best_route is not None:
            gtwuuid = best_route.object["gtwuuid"]
        else:
            gtwuuid = None
                    
        peers = RAMCollection("peers").find(agtuuid = gtwuuid)
        if len(peers) > 0:
            try:
                if peers[0].object["url"] != None:
                    send_json(peers[0].object["url"], message)
                    ctr_increment("messages forwarded")
                else:
                    push_message(message)
            except:
                ctr_increment("messages dropped")
        else:
            ctr_increment("messages dropped")
    
    ctr_decrement("threads (forwarding)")

def anon_worker():
    Timer(0.5, anon_worker).start()
    
    for message in pop_messages(type = "cascade response"):
        Thread(target = process, args = (message,)).start()
    
    for message in pop_messages(type = "cascade request"):
        Thread(target = process, args = (message,)).start()

def poll(peer):
    try:
        message = {}
        message["dest"] = peer["agtuuid"]
        message["type"] = "pull messages"

        if peer["url"] != None and \
           peer["polling"] == True:
            for message in send_json(peer["url"], message):
                Thread(target = process, args = (message,)).start()
    finally:
        ctr_decrement("threads (polling-{0})".format(peer["agtuuid"]))

def poll_worker():
    Timer(0.5, poll_worker).start()

    ctr_set_name("uptime", int(time() - START_TIME))

    for peer in get_peers():
        if ctr_get_name("threads (polling-{0})".format(peer["agtuuid"])) == 0:
            ctr_increment("threads (polling-{0})".format(peer["agtuuid"]))
            
            Thread(target = poll, args = (peer,)).start()

def advertise(peer):
    try:
        message = create_route_advertisement()
        message["dest"] = peer["agtuuid"]
        process(message)
    finally:
        ctr_decrement("threads (advertising-{0})".format(peer["agtuuid"]))

def ad_worker():
    rt = int(random() * 30.0)
    
    Timer(rt, ad_worker).start()
    
    age_routes(rt)

    for peer in get_peers():
        if ctr_get_name("threads (advertising-{0})".format(peer["agtuuid"])) == 0:
            ctr_increment("threads (advertising-{0})".format(peer["agtuuid"]))
            
            Thread(target = advertise, args = (peer,)).start()

Thread(target = ad_worker).start()
Thread(target = poll_worker).start()
Thread(target = anon_worker).start()