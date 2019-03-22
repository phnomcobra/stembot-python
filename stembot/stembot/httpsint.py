#!/usr/bin/python

import json
import traceback
import ssl
import hashlib
import httplib
import urllib2
import cherrypy

from time import time, sleep
from counters import increment
from random import random

def send_json(url, json_in):
    increment("requests attempted ({0})".format(url))
    
    st = time()
    dt = 0
    while time() - st < 5.0:
        try:
            return __send_json(url, json_in)
        except:
            sleep(dt)
            
            increment("requests retried ({0})".format(url))
        
        dt = dt + 0.5

    raise Exception("MPI Request Timeout!")

def __send_json(url, json_in):
    json_in["isrc"] = cherrypy.config.get("agtuuid")
    raw_json_in = json.dumps(json_in)
    
    h = hashlib.sha256()
    h.update(cherrypy.config.get("server.secret_digest"))
    h.update(raw_json_in)
    
    headers = {
        'Content-Type' : 'application/json',
        'Signature' : h.hexdigest()
    }
    
    req = urllib2.Request(url = url)
    
    connection = httplib.HTTPSConnection(req.get_host(), \
                                         context = ssl._create_unverified_context(), \
                                         timeout = 5)
    
    connection.request("POST", \
                       req.get_full_url(), \
                       raw_json_in, \
                       headers)
    
    response = connection.getresponse()
    
    signature = response.getheader("Signature")
    
    raw_json_out = response.read()
    
    increment("bytes sent ({0})".format(url), len(raw_json_in.encode("utf-8")))
    increment("bytes recv ({0})".format(url), len(raw_json_out.encode("utf-8")))
            
    h = hashlib.sha256()
    h.update(cherrypy.config.get("server.secret_digest"))
    h.update(raw_json_out)
    
    if h.hexdigest() != signature:
        raise Exception("Signature mismatch encountered!")
    
    json_out = json.loads(raw_json_out)
    
    increment("requests completed ({0})".format(url))    
            
    return json_out