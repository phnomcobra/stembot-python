#!/usr/bin/python

import json
import hashlib
import traceback
import urllib2
import httplib
import ssl
import kvstore

from random import random
from time import sleep, time
from base64 import b64encode, b64decode

class MPIClient:
    def __init__(self, url, secret_digest):
        self.secret_digest = secret_digest
        self.url = url

    def __del__(self):
        try:
            self.session["connection"].close()
        except:
            pass

    def send_json(self, json_in):
        st = time()
        dt = 0
        
        while time() - st < 5.0:
            try:
                return self.__send_json(json_in)
            except:
                sleep(dt)
        
            dt = dt + 0.5
        
        raise Exception("MPI Request Timeout!")

    def __send_json(self, json_in):
        raw_json_in = json.dumps(json_in)
        
        h = hashlib.sha256()
        h.update(self.secret_digest)
        h.update(raw_json_in)
        
        headers = {
            'Content-Type' : 'application/json',
            'Signature' : h.hexdigest()
        }
        
        req = urllib2.Request(url = self.url)
        
        connection = httplib.HTTPSConnection(req.get_host(), context = ssl._create_unverified_context())
        
        connection.request("POST", \
                           req.get_full_url(), \
                           raw_json_in, \
                           headers)
        
        response = connection.getresponse()
        
        signature = response.getheader("Signature")
        
        raw_json_out = response.read()
        
        h = hashlib.sha256()
        h.update(self.secret_digest)
        h.update(raw_json_out)
        
        if h.hexdigest() != signature:
            raise Exception("Signature mismatch encountered!")
        
        json_out = json.loads(raw_json_out)
        
        return json_out

    def ticket_request(self, request):
        message = {
            "type" : "create async ticket",
            "request" : request,
        }
        
        tckuuid = self.send_json(message)["tckuuid"]
        
        st = time()
        dt = 0
        while True:
            sleep(dt)
            
            dt = dt + 0.5
            
            message = {
                "type" : "get ticket response",
                "tckuuid" : tckuuid,
            }
            
            response = self.send_json(message)
            
            if response != None:
                break
            
            if time() - st > 15.0:
                raise Exception("MPI Response Timeout Exceeded!")

        message = {
            "type" : "delete ticket",
            "tckuuid" : tckuuid,
        }
        
        self.send_json(message)
        
        return response
    
    def cascade_request(self, request, timeout = 15, etags = [], ftags = []):
        responses = []
        
        message = {
            "type" : "create cascade async",
            "request" : request,
            "etags" : etags,
            "ftags" : ftags
        }
        
        cscuuid = self.ticket_request(message)["cscuuid"]
        
        
        lrt = time()
        
        while time() - lrt < timeout:
            message = {
                "type" : "pull cascade responses",
                "cscuuid" : cscuuid,
            }
    
            response = self.ticket_request(message)
            
            if len(response) > 0:
                lrt = time()
                responses += response

        return responses

class Console:
    def __init__(self, agtuuid = kvstore.get(name = "agtuuid")):
        port = kvstore.get(name = "socket_port")

        host = kvstore.get(name = "socket_host")
        if host == "0.0.0.0":
            host = "127.0.0.1"
        
        secret_digest = kvstore.get(name = "secret_digest")
        
        url = 'https://{0}:{1}/mpi'.format(host, port)
        
        self.__remote_mpi = MPIClient(url, secret_digest)
        self.__remote_agtuuid = agtuuid
    
    def delete_peer(self, agtuuid):
        message = {
            "dest" : self.__remote_agtuuid,
            "type" : "delete peer",
            "agtuuid" : agtuuid
        }
        
        return self.__remote_mpi.ticket_request(message)
    
    def delete_peers(self):
        message = {
            "dest" : self.__remote_agtuuid,
            "type" : "delete peers"
        }
        
        return self.__remote_mpi.ticket_request(message)
    
    def get_peers(self):
        message = {
            "dest" : self.__remote_agtuuid,
            "type" : "get peers"
        }
        
        return self.__remote_mpi.ticket_request(message)
    
    
    def set_peer(self, url, polling = True, ttl = None):
        message = {
            "dest" : self.__remote_agtuuid,
            "type" : "discover peer",
            "polling" : polling,
            "url" : url
        }
        
        if ttl != None:
            message["ttl"] = ttl
        
        return self.__remote_mpi.ticket_request(message)
    
    def get_routes(self):
        message = {
            "dest" : self.__remote_agtuuid,
            "type" : "get routes"
        }
        
        return self.__remote_mpi.ticket_request(message)
    
    def get_counters(self):
        message = {
            "dest" : self.__remote_agtuuid,
            "type" : "get counters"
        }
        
        return self.__remote_mpi.ticket_request(message)
    
    def file(self, filename, mode):
        return FileWrapper(filename, \
                           self.__remote_agtuuid, \
                           self.__remote_mpi, \
                           mode)

    def AGTCollection(self, name):
        return AGTCollection(self.__remote_mpi, \
                             self.__remote_agtuuid, \
                             name)
    
    def AGTCollections(self, *args, **kargs):
        return AGTCollections(self.__remote_mpi, *args, **kargs)
    
    def Cascade(self, *args, **kargs):
        return Cascade(self.__remote_mpi, *args, **kargs)
    
    def get_remote_agtuuid(self):
        return self.__remote_agtuuid

    def run_function_by_uuid(self, fctuuid, event = {}):
        request = {
            "dest" : self.__remote_agtuuid,
            "type" : "run function",
            "fctuuid" : fctuuid,
            "event" : event
        }
            
        response = self.__remote_mpi.ticket_request(request)
        
        if "exception" in response:
            raise Exception("{0}\n{1}".format(response["exception"], \
                                              json.dumps(response["context"], \
                                                         indent = 4)))
        else:
            return response["result"]
    
    def run_function_by_name(self, name, event = {}):
        request = {
            "dest" : self.__remote_agtuuid,
            "type" : "run function",
            "name" : name,
            "event" : event
        }
        
        response = self.__remote_mpi.ticket_request(request)
        
        if "exception" in response:
            raise Exception("{0}\n{1}".format(response["exception"], \
                                              json.dumps(response["context"], \
                                                         indent = 4)))
        else:
            return response["result"]

    def close(self):
        pass
    
    #### System Command ##########################
    def system(self, command, return_tuple = False, timeout = 3600):
        request = {
            "dest" : self.__remote_agtuuid,
            "type" : "process handle create",
            "command" : command
        }
            
        phduuid = self.__remote_mpi.ticket_request(request)["phduuid"]
        
        request = {
            "dest" : self.__remote_agtuuid,
            "type" : "process handle status",
            "phduuid" : phduuid,
        }
        
        status = self.__remote_mpi.ticket_request(request)["status"]
        
        start_time = time()
        dt = 0
        while status == None:
            dt = dt + .5
            sleep(dt)

            request = {
                "dest" : self.__remote_agtuuid,
                "type" : "process handle status",
                "phduuid" : phduuid,
            }
            
            status = self.__remote_mpi.ticket_request(request)["status"]
            
            if time() - start_time > timeout:
                request = {
                    "dest" : self.__remote_agtuuid,
                    "type" : "process handle close",
                    "phduuid" : phduuid,
                }
            
                self.__remote_mpi.ticket_request(request)
                
                raise Exception("Process timeout exceeded!")

        request = {
            "dest" : self.__remote_agtuuid,
            "type" : "process handle recv",
            "phduuid" : phduuid,
        }
            
        recv_response = self.__remote_mpi.ticket_request(request)
        
        request = {
            "dest" : self.__remote_agtuuid,
            "type" : "process handle close",
            "phduuid" : phduuid,
        }
            
        self.__remote_mpi.ticket_request(request)

        # Lossy ascii character set conversion
        output_buffer = ""
        for c in b64decode(recv_response["stdout b64data"]):
            try:
                output_buffer += c.encode("ascii", "ignore")
            except:
                pass

        # Lossy ascii character set conversion
        stderr_buffer = ""
        for c in b64decode(recv_response["stderr b64data"]):
            try:
                stderr_buffer += c.encode("ascii", "ignore")
            except:
                pass
        
        if return_tuple:
            return status, output_buffer, stderr_buffer
        else:
            return output_buffer + stderr_buffer

class AGTObject:
    def __init__(self, collection_name, remote_agtuuid, remote_mpi, object):
        self.__remote_agtuuid = remote_agtuuid
        self.__remote_mpi = remote_mpi
        self.__collection_name = collection_name
        
        self.object = object
        
        self.objuuid = self.object["objuuid"]
        self.coluuid = self.object["coluuid"]
        self.agtuuid = remote_agtuuid

    def load(self):
        request = {
            "dest" : self.__remote_agtuuid,
            "type" : "get collection object",
            "objuuid" : self.objuuid,
            "name" : self.__collection_name,
        }
        
        self.object = self.__remote_mpi.ticket_request(request)
        
        self.objuuid = self.object["objuuid"]
        self.coluuid = self.object["coluuid"]

    def set(self):
        request = {
            "dest" : self.__remote_agtuuid,
            "type" : "set collection object",
            "name" : self.__collection_name,
            "object" : self.object
        }
            
        self.__remote_mpi.ticket_request(request)
    
    def destroy(self):
        request = {
            "dest" : self.__remote_agtuuid,
            "type" : "delete collection object",
            "name" : self.__collection_name,
            "objuuid" : self.objuuid
        }
            
        self.__remote_mpi.ticket_request(request)
        
        self.objuuid = None
        self.coluuid = None
        self.object = None

class Cascade:
    def __init__(self, remote_mpi, timeout = 15, etags = [], ftags = []):
        self.__remote_mpi = remote_mpi
        self.__timeout = timeout
        self.__etags = etags
        self.__ftags = ftags
    
    def system(self, command, return_tuple = False):
        request = {
            "type" : "process sync",
            "command" : command,
            "timeout" : self.__timeout / 3
        }
        
        outputs = {}
        
        for cascade_response in self.__remote_mpi.cascade_request(request = request, \
                                                                  timeout = self.__timeout, \
                                                                  etags = self.__etags, \
                                                                  ftags = self.__ftags):
            # Lossy ascii character set conversion
            output_buffer = ""
            for c in b64decode(cascade_response["response"]["stdout"]):
                try:
                    output_buffer += c.encode("ascii", "ignore")
                except:
                    pass
    
            # Lossy ascii character set conversion
            stderr_buffer = ""
            for c in b64decode(cascade_response["response"]["stderr"]):
                try:
                    stderr_buffer += c.encode("ascii", "ignore")
                except:
                    pass
            
            if return_tuple:
                outputs[cascade_response["src"]] = cascade_response["response"]["status"], \
                                                   output_buffer, \
                                                   stderr_buffer
            else:
                outputs[cascade_response["src"]] = output_buffer + stderr_buffer
        
        return outputs
    
    def file_read(self, filename):
        request = {
            "type" : "file read",
            "filename" : filename
        }
        
        outputs = {}
        
        for cascade_response in self.__remote_mpi.cascade_request(request = request, \
                                                                  timeout = self.__timeout, \
                                                                  etags = self.__etags, \
                                                                  ftags = self.__ftags):
            outputs[cascade_response["src"]] = b64decode(cascade_response["response"]["b64data"])
                
        return outputs
    
    def run_function_by_uuid(self, fctuuid, event = {}):
        request = {
            "type" : "run function",
            "fctuuid" : fctuuid,
            "event" : event
        }
            
        outputs = {}
        
        for cascade_response in self.__remote_mpi.cascade_request(request = request, \
                                                                  timeout = self.__timeout, \
                                                                  etags = self.__etags, \
                                                                  ftags = self.__ftags):
            if "result" in cascade_response["response"]:
                outputs[cascade_response["src"]] = cascade_response["response"]["result"]
            elif "exception" in cascade_response["response"]:
                outputs[cascade_response["src"]] = cascade_response["response"]["exception"]
                
        return outputs
    
    def run_function_by_name(self, name, event = {}):
        request = {
            "type" : "run function",
            "name" : name,
            "event" : event
        }
            
        outputs = {}
        
        for cascade_response in self.__remote_mpi.cascade_request(request = request, \
                                                                  timeout = self.__timeout, \
                                                                  etags = self.__etags, \
                                                                  ftags = self.__ftags):
            if "result" in cascade_response["response"]:
                outputs[cascade_response["src"]] = cascade_response["response"]["result"]
            elif "exception" in cascade_response["response"]:
                outputs[cascade_response["src"]] = cascade_response["response"]["exception"]
                
        return outputs

class AGTCollections:
    def __init__(self, remote_mpi, collection_name, timeout = 15, etags = [], ftags = []):
        self.__collection_name = collection_name
        self.__remote_mpi = remote_mpi
        self.__timeout = timeout
        self.__etags = etags
        self.__ftags = ftags
    
    def find(self, **kargs):
        request = {
            "type" : "find collection objects",
            "query" : kargs,
            "name" : self.__collection_name,
        }
        
        objects = []
        
        for cascade_response in self.__remote_mpi.cascade_request(request = request, \
                                                                  etags = self.__etags, \
                                                                  ftags = self.__ftags, \
                                                                  timeout = self.__timeout):
            for object in cascade_response["response"]:
                objects.append(AGTObject(self.__collection_name, \
                                         cascade_response["src"], \
                                         self.__remote_mpi, object))

        return objects

class AGTCollection:
    def __init__(self, remote_mpi, remote_agtuuid, collection_name):
        self.collection_name = collection_name
        self.__remote_mpi = remote_mpi
        self.__remote_agtuuid = remote_agtuuid
        
    def destroy(self):
        request = {
            "dest" : self.__remote_agtuuid,
            "type" : "delete collection",
            "name" : self.collection_name
        }
            
        self.__remote_mpi.ticket_request(request)
    
    def rename(self, name):
        request = {
            "dest" : self.__remote_agtuuid,
            "type" : "rename collection",
            "name" : self.collection_name,
            "new name" : name
        }
            
        self.__remote_mpi.ticket_request(request)
        
        self.collection_name = name
    
    def create_attribute(self, attribute, path):
        request = {
            "dest" : self.__remote_agtuuid,
            "type" : "create collection attribute",
            "attribute" : attribute,
            "path" : path,
            "name" : self.collection_name,
        }
            
        self.__remote_mpi.ticket_request(request)
    
    def delete_attribute(self, attribute):
        request = {
            "dest" : self.__remote_agtuuid,
            "type" : "delete collection attribute",
            "attribute" : attribute,
            "name" : self.collection_name,
        }
            
        self.__remote_mpi.ticket_request(request)
    
    def find(self, **kargs):
        request = {
            "dest" : self.__remote_agtuuid,
            "type" : "find collection objects",
            "query" : kargs,
            "name" : self.collection_name,
        }
        
        objects = []
        for object in self.__remote_mpi.ticket_request(request):
            objects.append(AGTObject(self.collection_name, \
                                     self.__remote_agtuuid, \
                                     self.__remote_mpi, \
                                     object))
        
        return objects

    def find_objuuids(self, **kargs):
        request = {
            "dest" : self.__remote_agtuuid,
            "type" : "find collection object uuids",
            "query" : kargs,
            "name" : self.collection_name,
        }
            
        return self.__remote_mpi.ticket_request(request)

    def get_object(self, objuuid = None):
        if objuuid:
            request = {
                "dest" : self.__remote_agtuuid,
                "type" : "get collection object",
                "objuuid" : objuuid,
                "name" : self.collection_name,
            }
        else:
            request = {
                "dest" : self.__remote_agtuuid,
                "type" : "get collection object",
                "name" : self.collection_name,
            }
            
        return AGTObject(self.collection_name, \
                         self.__remote_agtuuid, \
                         self.__remote_mpi, \
                         self.__remote_mpi.ticket_request(request))
    
    def set_object(self, object):
        request = {
            "dest" : self.__remote_agtuuid,
            "type" : "set collection object",
            "name" : self.collection_name,
            "object" : object
        }
            
        self.__remote_mpi.ticket_request(request)
    
    def delete_object(self, objuuid):
        request = {
            "dest" : self.__remote_agtuuid,
            "type" : "delete collection object",
            "name" : self.collection_name,
            "objuuid" : objuuid
        }
            
        self.__remote_mpi.ticket_request(request)

    def list_objuuids(self):
        request = {
            "dest" : self.__remote_agtuuid,
            "type" : "list collection object uuids",
            "name" : self.collection_name,
        }
            
        return self.__remote_mpi.ticket_request(request)

class FileWrapper:
    def __init__(self, filename, remote_agtuuid, remote_mpi, mode):
        self.__remote_agtuuid = remote_agtuuid
        self.__remote_mpi = remote_mpi
        
        request = {
            "dest" : self.__remote_agtuuid,
            "type" : "file handle open",
            "filename" : filename,
            "mode" : mode
        }
            
        response = self.__remote_mpi.ticket_request(request)
        
        try:
            self.__fhduuid = response["fhduuid"]
        except:
            raise Exception("{0}\n{1}".format(traceback.format_exc(), response))

    def __del__(self):
        self.close()
    
    def tell(self):
        request = {
            "dest" : self.__remote_agtuuid,
            "type" : "file handle tell",
            "fhduuid" : self.__fhduuid,
        }
            
        return self.__remote_mpi.ticket_request(request)["position"]

    def close(self):
        request = {
            "dest" : self.__remote_agtuuid,
            "type" : "file handle close",
            "fhduuid" : self.__fhduuid
        }
            
        self.__remote_mpi.ticket_request(request)

    def open(self, **kargs):
        self.__init__(**kargs)
    
    def fileno(self):
        return 0
    
    def seek(self, seek_position):
        request = {
            "dest" : self.__remote_agtuuid,
            "type" : "file handle seek",
            "fhduuid" : self.__fhduuid,
            "position" : seek_position
        }
            
        self.__remote_mpi.ticket_request(request)
    
    def read(self, num_bytes = None):
        request = {
            "dest" : self.__remote_agtuuid,
            "type" : "file handle read",
            "fhduuid" : self.__fhduuid
        }
        
        if num_bytes != None:
            request["size"] = num_bytes
            
        response = self.__remote_mpi.ticket_request(request)
        
        try:
            return buffer(b64decode(response["b64data"]))
        except:
            raise Exception("{0}\n{1}".format(traceback.format_exc(), response))

    def next(self):        
        request = {
            "dest" : self.__remote_agtuuid,
            "type" : "file handle read",
            "fhduuid" : self.__fhduuid,
            "size" : 1
        }
        
        response = self.__remote_mpi.ticket_request(request)
        
        try:
            return buffer(b64decode(response["b64data"]))
        except:
            raise Exception("{0}\n{1}".format(traceback.format_exc(), response))

    def readline(self, num_bytes = None):        
        org_position = self.tell()
        
        line = ""
        
        while "\n" not in line:
            data = self.read(4096)
            line += data
            
            if len(data) == 0:
                break
        
        self.seek(org_position + len(line))
        
        return line.split("\n")[0]
    
    def readlines(self, num_bytes = None):        
        if num_bytes == None:
            data = str(self.read())
        else:
            data = str(self.read(num_bytes))

        return data.split("\n")
    
    def truncate(self, num_bytes = None):
        request = {
            "dest" : self.__remote_agtuuid,
            "type" : "file handle truncate",
            "fhduuid" : self.__fhduuid
        }
        
        if num_bytes == None:
            request["size"] = self.tell() + 1
        else:
            request["size"] = num_bytes
            
        self.__remote_mpi.ticket_request(request)

    def flush(self):
        pass
    
    def isatty(self):
        return False
    
    def writelines(self, raw_buffer_list):
        for raw_buffer in raw_buffer_list:
            self.write(raw_buffer)
    
    def write(self, raw_buffer):
        buffer = bytearray()
        
        buffer.extend(raw_buffer)
        
        request = {
            "dest" : self.__remote_agtuuid,
            "type" : "file handle write",
            "fhduuid" : self.__fhduuid,
            "b64data" : b64encode(buffer)
        }
            
        self.__remote_mpi.ticket_request(request)