#!/usr/bin/python

ASYNC_CASCADE_TIMEOUT = 300
SYNC_CASCADE_TIMEOUT = 15

import cherrypy
import traceback

from threading import Timer, Thread
from base64 import b64encode, b64decode
from time import time, sleep

from ramdocument import Collection as RAMCollection
from document import Collection as SQLCollection
from messages import push_message
from tagging import get_tag_values
from utils import sucky_uuid
from counters import increment as ctr_increment
from function import run_function_by_uuid, \
                     run_function_by_name
from hostint import process_sync, \
                    file_read
                         
def service_cascade_request(message):
    ctr_increment("cascades serviced")
    
    cascade_response = RAMCollection("cascade responses").get_object()
    cascade_response.object = message
    cascade_response.set()

def create_anonymous_cascade_request(message):
    ctr_increment("cascades created")
    
    cascade_request = {
        "cscuuid" : sucky_uuid(),
        "request" : message["request"],
        "timestamp" : time(),
        "etags" : message["etags"],
        "ftags" : message["ftags"],
        "src" : cherrypy.config.get("agtuuid"),
        "dest" : None,
        "type" : "cascade request",
        "anonymous" : True
    }
    
    Thread(target = process_cascade_request, args = (cascade_request,)).start()
        
def create_cascade_request(message):
    ctr_increment("cascades created")
    
    cascade_request = {
        "cscuuid" : sucky_uuid(),
        "request" : message["request"],
        "timestamp" : time(),
        "etags" : message["etags"],
        "ftags" : message["ftags"],
        "src" : cherrypy.config.get("agtuuid"),
        "dest" : None,
        "type" : "cascade request",
        "anonymous" : False
    }
    
    Thread(target = process_cascade_request, args = (cascade_request,)).start()
        
    return cascade_request

def process_cascade_request(message):
    ctr_increment("cascades processed")
    
    cascade_requests = RAMCollection("cascade requests")
    
    try:
        if len(cascade_requests.find_objuuids(cscuuid = message["cscuuid"])) == 0:
            cascade_request = cascade_requests.get_object()
            cascade_request.object = message
            cascade_request.set()
            
            if len(message["ftags"]) > 0:
                if len(list(set(message["ftags"]) & set(get_tag_values()))) > 0:
                    Thread(target = forward_cascade_request, args = (message,)).start()
            else:
                Thread(target = forward_cascade_request, args = (message,)).start()
            
            if len(message["etags"]) > 0:
                if len(list(set(message["etags"]) & set(get_tag_values()))) > 0:
                    Thread(target = execute_cascade_request, args = (message,)).start()
            else:
                Thread(target = execute_cascade_request, args = (message,)).start()
    except:
        pass
        
def forward_cascade_request(message):
    ctr_increment("cascades forwarded")
    
    peers = SQLCollection("peers")
    
    for objuuid in peers.list_objuuids():
        try:
            message["dest"] = peers.get_object(objuuid).object["agtuuid"]
        except:
            peers.get_object(objuuid).destroy()
        
        try:
            if message["dest"] != cherrypy.config.get("agtuuid"):
                push_message(message)
        except:
            pass

def pop_cascade_responses(cscuuid):
    responses = RAMCollection("cascade responses")
    
    response_objects = []
    
    for objuuid in responses.find_objuuids(cscuuid = cscuuid):
        response = responses.get_object(objuuid)
        
        response_objects.append(response.object)
        response.destroy()

    return response_objects

def wait_on_cascade_responses(cscuuid, timeout = None):
    if timeout == None:
        sleep(SYNC_CASCADE_TIMEOUT)
    else:
        sleep(timeout)
    
    response_objects = []
    
    for response in RAMCollection("cascade responses").find(cscuuid = cscuuid):
        response_objects.append(response.object)
        response.destroy()
    
    for request in RAMCollection("cascade requests").find(cscuuid = cscuuid):
        request.destroy()
    
    return response_objects

def get_cascade_responses(cscuuid):
    response_objects = []
    
    for response in RAMCollection("cascade responses").find(cscuuid = cscuuid):
        response_objects.append(response.object)
    
    return response_objects

def execute_cascade_request(message):
    ctr_increment("cascades executed")
    
    request = message["request"]
    response = {}
    
    try:
        if request["type"] == "process sync":
            if "timeout" in request:
                status, stdout, stderr = process_sync(request["command"], \
                                                      timeout = request["timeout"])
            else:
                status, stdout, stderr = process_sync(request["command"])
            
            response["type"] = request["type"]
            response["stdout"] = b64encode(stdout)
            response["stderr"] = b64encode(stderr)
            response["status"] = status
            
            if message["anonymous"] == False:
                push_message({
                    "type" : "cascade response",
                    "dest" : message["src"],
                    "cscuuid" : message["cscuuid"],
                    "response" : response,
                    "src" : cherrypy.config.get("agtuuid")
                })
        
        
        
        
        elif request["type"] == "file read":
            response["type"] = request["type"]
            response["b64data"] = b64encode(file_read(request["filename"]))
            
            push_message({
                "type" : "cascade response",
                "dest" : message["src"],
                "cscuuid" : message["cscuuid"],
                "response" : response,
                "src" : cherrypy.config.get("agtuuid")
            })
        
        
        
        
        elif request["type"] == "delete route":
            for route in RAMCollection("routes").find(agtuuid = request["agtuuid"]):
                route.destroy()
            
            for route in RAMCollection("routes").find(gtwuuid = request["agtuuid"]):
                route.destroy()
            



        elif request["type"] == "run function":
            if "name" in request:
                response = run_function_by_name(request["name"], request["event"], message)
            else:
                response = run_function_by_uuid(request["fctuuid"], request["event"], message)
            
            if response != None and \
               message["anonymous"] == False:
                push_message({
                    "type" : "cascade response",
                    "dest" : message["src"],
                    "cscuuid" : message["cscuuid"],
                    "response" : response,
                    "src" : cherrypy.config.get("agtuuid")
                })
        
        
        
        
        elif request["type"] == "find collection objects":
            collection = SQLCollection(request["name"])
            
            response = []
            
            for objuuid in collection.find_objuuids(**request["query"]):
                response.append(collection.get_object(objuuid).object)
            
            if len(response) > 0:
                push_message({
                    "type" : "cascade response",
                    "dest" : message["src"],
                    "cscuuid" : message["cscuuid"],
                    "response" : response,
                    "src" : cherrypy.config.get("agtuuid")
                })
    except:
        pass    
    
def prune():
    requests = RAMCollection("cascade requests")
    responses = RAMCollection("cascade responses")
    
    cscuuids = []
    
    for objuuid in requests.list_objuuids():
        request = requests.get_object(objuuid)
        
        try:
            if time() - request.object["timestamp"] > ASYNC_CASCADE_TIMEOUT:
                request.destroy()
            else:
                cscuuids.append(request.object["cscuuid"])
        except:
            request.destroy()

    for objuuid in responses.list_objuuids():
        response = responses.get_object(objuuid)
        
        try:
            if response.object["cscuuid"] not in cscuuids:
                response.destroy()
        except:
            response.destroy()

def worker():
    Timer(60.0, worker).start()
    prune()
    
collection = RAMCollection("cascade requests")
collection.create_attribute("cscuuid", "['cscuuid']")

collection = RAMCollection("cascade responses")
collection.create_attribute("cscuuid", "['cscuuid']")

Thread(target = worker).start()