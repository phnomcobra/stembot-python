#!/usr/bin/python

ASYNC_TICKET_TIMEOUT = 3600
SYNC_TICKET_TIMEOUT = 15

import traceback
import cherrypy

from base64 import b64encode, b64decode
from time import time, sleep
from threading import Thread, Timer

from ramdocument import Collection as RAMCollection
from document import Collection as SQLCollection
from httpsint import send_json
from peer import create_peer, \
                 delete_peer, \
                 delete_peers, \
                 get_peers, \
                 get_routes
from hostint import create_file_handle, \
                    close_file_handle, \
                    file_handle_read, \
                    file_handle_write, \
                    file_handle_seek, \
                    file_handle_tell, \
                    file_handle_truncate, \
                    create_process_handle, \
                    process_handle_status, \
                    process_handle_kill, \
                    process_handle_terminate, \
                    process_handle_wait, \
                    process_handle_recv, \
                    process_handle_send, \
                    close_process_handle
from cascade import create_cascade_request, \
                    create_anonymous_cascade_request, \
                    get_cascade_responses, \
                    pop_cascade_responses, \
                    wait_on_cascade_responses
from counters import increment as ctr_increment, \
                     get_all as ctr_get_all
from function import run_function_by_uuid, \
                     run_function_by_name

def create_ticket(request):
    ctr_increment("tickets created")
    
    tickets = RAMCollection("tickets")
    
    ticket = tickets.get_object()
    
    ticket.object["src"] = cherrypy.config.get("agtuuid")
    
    if "dest" in request:
        ticket.object["dest"] = request["dest"]
    else:
        ticket.object["dest"] = cherrypy.config.get("agtuuid")
    
    ticket.object["timestamp"] = time()
    ticket.object["request"] = request
    ticket.object["response"] = None
    
    ticket.set()
    
    message = {}
    message["type"] = "ticket request"
    message["src"] = ticket.object["src"]
    message["request"] = ticket.object["request"]
    message["dest"] = ticket.object["dest"]
    message["tckuuid"] = ticket.object["objuuid"]
    
    return message
    
def process_ticket(message):
    ctr_increment("tickets processed")
    
    message["type"] = "ticket response"
    message["src"], message["dest"] = message["dest"], message["src"]
    
    request = message["request"]
    response = {}
    
    try:
        if request["type"] == "discover peer":
            if "ttl" in request:
                ttl = request["ttl"]
            else:
                ttl = None
            
            if "polling" in request:
                polling = request["polling"]
            else:
                request = False

            create_peer(send_json(request["url"], {"type" : "create info event"})["dest"], \
                        url = request["url"], \
                        ttl = ttl, \
                        polling = polling)
            
            response = request

        elif request["type"] == "create peer":
            if "url" in request:
                url = request["url"]
            else:
                url = None
            
            if "ttl" in request:
                ttl = request["ttl"]
            else:
                ttl = None
            
            if "polling" in request:
                polling = request["polling"]
            else:
                polling = False
            
            create_peer(request["agtuuid"], \
                        url = url, \
                        ttl = ttl, \
                        polling = polling)
            
            response = request
        
        elif request["type"] == "delete peers":
            delete_peers()
            response = request
                        
        elif request["type"] == "delete peer":
            delete_peer(request["agtuuid"])
            response = request
        
        elif request["type"] == "get peers":
            response = get_peers()
        
        elif request["type"] == "get routes":
            response = get_routes()
        
        
        
        
        elif request["type"] == "get counters":
            response = ctr_get_all()    
        

            
            
        elif request["type"] == "file handle open":
            response["fhduuid"] = create_file_handle(request["filename"], request["mode"])
            response["type"] = request["type"]
            
        elif request["type"] == "file handle close":
            close_file_handle(request["fhduuid"])
            response = request
            
        elif request["type"] == "file handle read":
            if "size" in request:
                response["b64data"] = b64encode(file_handle_read(request["fhduuid"], request["size"]))
            else:
                response["b64data"] = b64encode(file_handle_read(request["fhduuid"]))
            response["type"] = request["type"]
            
        elif request["type"] == "file handle write":
            file_handle_write(request["fhduuid"], b64decode(request["b64data"]))
            response = request
            
        elif request["type"] == "file handle truncate":
            file_handle_truncate(request["fhduuid"], request["size"])
            response = request
            
        elif request["type"] == "file handle seek":
            file_handle_seek(request["fhduuid"], request["position"])
            response = request
            
        elif request["type"] == "file handle tell":
            response["position"] = file_handle_tell(request["fhduuid"])
            response["type"] = request["type"]
            
            
            
            
        elif request["type"] == "process handle create":
            response["phduuid"] = create_process_handle(request["command"])
            response["type"] = request["type"]
            
        elif request["type"] == "process handle status":
            response["status"] = process_handle_status(request["phduuid"])
            
        elif request["type"] == "process handle kill":
            process_handle_kill(request["phduuid"])
            response = request
            
        elif request["type"] == "process handle terminate":
            process_handle_terminate(request["phduuid"])
            response = request
            
        elif request["type"] == "process handle wait":
            process_handle_wait(request["phduuid"])
            response = request
            
        elif request["type"] == "process handle close":
            close_process_handle(request["phduuid"])
            response = request
            
        elif request["type"] == "process handle send":
            process_handle_send(request["phduuid"], b64decode(request["b64data"]))
            response = request
            
        elif request["type"] == "process handle recv":
            stdout, stderr = process_handle_recv(request["phduuid"])
            response["stdout b64data"] = b64encode(stdout)
            response["stderr b64data"] = b64encode(stderr)
            response["type"] = request["type"]
            
            
            
            
        elif request["type"] == "create cascade async":
            response = create_cascade_request(request)
        
        elif request["type"] == "create cascade anon":
            create_anonymous_cascade_request(request)
            response = request

        elif request["type"] == "create cascade sync":
            if "timeout" in request:
                response = wait_on_cascade_responses(create_cascade_request(request)["cscuuid"], request["timeout"])
            else:
                response = wait_on_cascade_responses(create_cascade_request(request)["cscuuid"])
            
        elif request["type"] == "get cascade responses":
            response = get_cascade_responses(request["cscuuid"])
            
        elif request["type"] == "pull cascade responses":
            response = pop_cascade_responses(request["cscuuid"])
            
            
            
            
        elif request["type"] == "run function":
            if "name" in request:
                response = run_function_by_name(request["name"], request["event"], message)
            else:
                response = run_function_by_uuid(request["fctuuid"], request["event"], message)
        
        
        
        
        elif request["type"] == "delete collection":
            SQLCollection(request["name"]).destroy()
            response = request
        
        elif request["type"] == "rename collection":
            SQLCollection(request["name"]).rename(request["new name"])
            response = request
        
        elif request["type"] == "create collection attribute":
            SQLCollection(request["name"]).create_attribute(request["attribute"], request["path"])
            response = request
        
        elif request["type"] == "delete collection attribute":
            SQLCollection(request["name"]).delete_attribute(request["attribute"])
            response = request
        
        elif request["type"] == "find collection objects":
            response = []
            
            for temp in SQLCollection(request["name"]).find(**request["query"]):
                response.append(temp.object)
        
        elif request["type"] == "find collection object uuids":
            response = SQLCollection(request["name"]).find_objuuids(**request["query"])
        
        elif request["type"] == "get collection object":
            if "objuuid" in request:
                response = SQLCollection(request["name"]).get_object(request["objuuid"]).object
            else:
                response = SQLCollection(request["name"]).get_object().object
        
        elif request["type"] == "set collection object":
            response = request
            c = SQLCollection(request["name"])
            o = c.get_object(request["object"]["objuuid"])
            o.object = request["object"]
            o.set()
        
        elif request["type"] == "delete collection object":
            response = request
            SQLCollection(request["name"]).get_object(request["objuuid"]).destroy()

        elif request["type"] == "list collection object uuids":
            response = SQLCollection(request["name"]).list_objuuids()
        
        
        
        
        else:
            raise Exception("Unknown request type!")
    except:
        response["exception"] = traceback.format_exc()
        
    message["response"] = response
    
    return message

def service_ticket(message):
    ctr_increment("tickets serviced")
    
    tickets = RAMCollection("tickets")
    
    ticket = tickets.get_object(message["tckuuid"])
    ticket.object["response"] = message["response"]
    ticket.set()

def wait_on_ticket_response(tckuuid, timeout = None):
    tickets = RAMCollection("tickets")
    
    if timeout == None:
        timeout = SYNC_TICKET_TIMEOUT
    
    while True:
        ticket = tickets.get_object(tckuuid)
        
        if time() - ticket.object["timestamp"] > timeout:
            ticket.destroy()
            raise Exception("Ticket timeout period reached!")
        
        if ticket.object["response"] != None:
            response = ticket.object["response"]
            ticket.destroy()
            break
        
        sleep(1.0)

    return response

def get_ticket_response(tckuuid):
    tickets = RAMCollection("tickets")
    ticket = tickets.get_object(tckuuid)
    response = ticket.object["response"]
    return response

def delete_ticket(tckuuid):
    RAMCollection("tickets").get_object(tckuuid).destroy()
    
def worker():
    tickets = RAMCollection("tickets")
    
    for objuuid in tickets.list_objuuids():
        ticket = tickets.get_object(objuuid)
        
        try:
            if time() - ticket.object["timestamp"] > ASYNC_TICKET_TIMEOUT:
                ticket.destroy()
                ctr_increment("tickets expired")
        except:
            ticket.destroy()

    Timer(ASYNC_TICKET_TIMEOUT, worker).start()
    
Thread(target = worker).start()