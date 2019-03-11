#!/usr/bin/python

import traceback

from copy import deepcopy
from counters import increment
from threading import Lock
from utils import sucky_uuid

document_lock = Lock()
document = {}

class Document:
    def __init__(self):
        document_lock.acquire()
        
        if "TBL_JSON_COL" not in document:
            document["TBL_JSON_COL"] = {}
        
        if "TBL_JSON_OBJ" not in document:
            document["TBL_JSON_OBJ"] = {}
        
        if "TBL_JSON_ATTR" not in document:
            document["TBL_JSON_ATTR"] = {}
        
        if "TBL_JSON_IDX" not in document:
            document["TBL_JSON_IDX"] = {}
        
        document_lock.release()
    
    def create_object(self, coluuid, objuuid):
        try:
            document_lock.acquire()
            
            object = {
                "objuuid" : objuuid, 
                "coluuid" : coluuid
            }
            
            document["TBL_JSON_OBJ"]["-".join([coluuid, objuuid])] = object
        except:
            print traceback.format_exc()
        finally:
            document_lock.release()
    
    def set_object(self, coluuid, objuuid, object):
        try:
            document_lock.acquire()
            
            object = deepcopy(object)
            
            object["objuuid"] = objuuid
            object["coluuid"] = coluuid
            
            document["TBL_JSON_OBJ"]["-".join([coluuid, objuuid])] = object
            
            keys = []
            for key, value in document["TBL_JSON_IDX"].iteritems():
                if objuuid in key:
                    keys.append(key)
            
            for key in keys:
                del document["TBL_JSON_IDX"][key]

            attributes = {}
            for key, value in document["TBL_JSON_ATTR"].iteritems():
                if value["coluuid"] == coluuid:
                    attributes[document["TBL_JSON_ATTR"][key]["attribute_name"]] = document["TBL_JSON_ATTR"][key]["path"]
                
            for attribute_name in attributes:
                try:
                    document["TBL_JSON_IDX"]["-".join([coluuid, objuuid, attribute_name])] = {
                        "coluuid" : coluuid, 
                        "attribute_name" : attribute_name, 
                        "objuuid" : objuuid, 
                        "value" : str(eval("str(self.get_object_no_lock(objuuid)" + attributes[attribute_name] + ")"))
                    }
                except:
                    continue
        except:
            print traceback.format_exc()
        finally:
            document_lock.release()
    
    def get_object_no_lock(self, objuuid):
        for key, value in document["TBL_JSON_OBJ"].iteritems():
            if objuuid in key:
                return deepcopy(value)
        
        raise IndexError, "OBJUUID not found!"
    
    def get_object(self, objuuid):
        document_lock.acquire()
        
        for key, value in document["TBL_JSON_OBJ"].iteritems():
            if objuuid in key:
                document_lock.release()
                return deepcopy(value)
        
        document_lock.release()
        raise IndexError, "OBJUUID not found!"
    
    def find_objects(self, coluuid, attribute, value):
        value = str(value)
        
        document_lock.acquire()
        
        objuuids = []
        for key, index in document["TBL_JSON_IDX"].iteritems():
            if index["value"] == value and \
               index["coluuid"] == coluuid and \
               index["attribute_name"] == attribute:
                objuuids.append(index["objuuid"])
        
        document_lock.release()
        
        return objuuids
    
    def delete_object(self, objuuid):
        try:
            document_lock.acquire()
            
            keys = []
            for key, value in document["TBL_JSON_OBJ"].iteritems():
                if objuuid in key:
                    keys.append(key)
            
            for key in keys:
                del document["TBL_JSON_OBJ"][key]
            
            keys = []
            for key, value in document["TBL_JSON_IDX"].iteritems():
                if objuuid in key:
                    keys.append(key)
            
            for key in keys:
                del document["TBL_JSON_IDX"][key]
        except:
            print traceback.format_exc()
        finally:
            document_lock.release()
    
    def create_attribute(self, coluuid, attribute, path):
        try:
            document_lock.acquire()
            
            document["TBL_JSON_ATTR"]["-".join([coluuid, attribute])] = {
                "path" : path, 
                "attribute_name" : attribute, 
                "coluuid" : coluuid
            }
            
            for key, value in document["TBL_JSON_IDX"].iteritems():
                if value["attribute_name"] == attribute:
                    del document["TBL_JSON_IDX"][key]
        
            objects = {}
            for key, value in document["TBL_JSON_OBJ"].iteritems():
                if coluuid in key:
                    objects[object["objuuid"]] = document["TBL_JSON_OBJ"][key]
            
            for objuuid in objects:
                try:
                    document["TBL_JSON_IDX"]["-".join([coluuid, objuuid, attribute])] = {
                        "coluuid" : coluuid, 
                        "attribute_name" : attribute, 
                        "objuuid" : objuuid, 
                        "value" : str(eval("str(objects[objuuid]" + path + ")"))
                    }
                except:
                    traceback.format_exc()
        except:
            print traceback.format_exc()
        finally:
            document_lock.release()
    
    def delete_attribute(self, coluuid, attribute):
        try:
            document_lock.acquire()
            
            keys = []
            
            for key, value in document["TBL_JSON_ATTR"].iteritems():
                if value["attribute_name"] == attribute and value["coluuid"] == coluuid:
                    keys.append(key)
            
            for key in keys:
                del document["TBL_JSON_ATTR"][key]
            
            keys = []
            for key, value in document["TBL_JSON_IDX"].iteritems():
                if value["attribute_name"] == attribute and value["coluuid"] == coluuid:
                    keys.append(key)
            
            for key in keys:
                del document["TBL_JSON_IDX"][key]
        except:
            print traceback.format_exc()
        finally:
            document_lock.release()
        
    def list_attributes(self, coluuid):
        document_lock.acquire()
        
        attributes = {}
        for key, value in document["TBL_JSON_ATTR"].iteritems():
            if value["coluuid"] == coluuid:
                attributes[document["TBL_JSON_ATTR"][key]["attribute_name"]] = document["TBL_JSON_ATTR"][key]["path"]
        
        document_lock.release()
        
        return attributes
    
    def create_collection(self, uuid = None, name = "New Collection"):
        document_lock.acquire()

        if not uuid:
            uuid = sucky_uuid()
            
        document["TBL_JSON_COL"][uuid] = name

        document_lock.release()

        return uuid
    
    def delete_collection(self, uuid):
        try:
            document_lock.acquire()
            
            del document["TBL_JSON_COL"][uuid]
            
            keys = []
            for key in document["TBL_JSON_OBJ"]:
                if uuid in key:
                    keys.append(key)
            
            for key in keys:
                del document["TBL_JSON_OBJ"][key]
            
            keys = []
            for key in document["TBL_JSON_ATTR"]:
                if uuid in key:
                    keys.append(key)
                    
            for key in keys:
                del document["TBL_JSON_ATTR"][key]
            
            keys = []
            for key in document["TBL_JSON_IDX"]:
                if uuid in key:
                    keys.append(key)
            
            for key in keys:
                del document["TBL_JSON_IDX"][key]
        except:
            print traceback.format_exc()
        finally:
            document_lock.release()
    
    def rename_collection(self, uuid, name):
        document_lock.acquire()
        document["TBL_JSON_COL"][uuid] = name
        document_lock.release()
    
    def list_collections(self):
        document_lock.acquire()
        
        collections = {}
        for key, value in document["TBL_JSON_COL"].iteritems():
            collections[value] = key
        
        document_lock.release()
        
        return collections
    
    def list_collection_objects(self, coluuid):
        try:
            document_lock.acquire()
            
            objuuids = []
            for key, value in document["TBL_JSON_OBJ"].iteritems():
                if coluuid in key:
                    objuuids.append(value["objuuid"])
        except:
            print traceback.format_exc()
        finally:
            document_lock.release()
        
        return objuuids
        
    def list_objects(self):
        try:
            document_lock.acquire()
            
            objuuids = []
            for key, value in document["TBL_JSON_OBJ"].iteritems():
                objuuids.append(value["objuuid"])
        except:
            print traceback.format_exc()
        finally:
            document_lock.release()

        return objuuids

class Object(Document):
    def __init__(self, coluuid, objuuid):
        Document.__init__(self)
        
        self.objuuid = objuuid
        self.coluuid = coluuid
        self.load()
        
        increment("ram object reads")
    
    def load(self):
        try:
            self.object = Document.get_object(self, self.objuuid)
        except IndexError:
            Document.create_object(self, self.coluuid, self.objuuid)
            self.object = Document.get_object(self, self.objuuid)
            increment("ram object writes")
        finally:
            increment("ram object reads")
    
    def set(self):
        Document.set_object(self, self.coluuid, self.objuuid, self.object)
        increment("ram object writes")
    
    def destroy(self):
        Document.delete_object(self, self.objuuid)
        self.object = None
        increment("ram object writes")

class Collection(Document):
    def __init__(self, collection_name):
        Document.__init__(self)
        self.collection_name = collection_name
        
        try:
            self.coluuid = Document.list_collections(self)[self.collection_name]
        except KeyError:
            self.coluuid = Document.create_collection(self, name = self.collection_name)

    def destroy(self):
        Document.delete_collection(self, self.coluuid)
    
    def rename(self, name):
        Document.rename_collection(self, self.coluuid, name)
        self.collection_name = name
    
    def create_attribute(self, attribute, path):
        Document.create_attribute(self, self.coluuid, attribute, path)
    
    def delete_attribute(self, attribute):
        Document.delete_attribute(self, self.coluuid, attribute)
    
    def find(self, **kargs):
        objuuid_sets = []
        
        if len(kargs) == 0:
            objuuid_sets.append(self.list_objuuids())

        for attribute, value in kargs.iteritems():
            objuuid_sets.append(Document.find_objects(self, self.coluuid, attribute, value))
        
        intersection = set(objuuid_sets[0])
        for objuuids in objuuid_sets[1:]:
            intersection = intersection.intersection(set(objuuids))
        
        objects = []
        for objuuid in list(intersection):
            objects.append(Object(self.coluuid, objuuid))
        
        return objects
    
    def find_objuuids(self, **kargs):
        objuuid_sets = []

        if len(kargs) == 0:
            objuuid_sets.append(self.list_objuuids())
        
        for attribute, value in kargs.iteritems():
            objuuid_sets.append(Document.find_objects(self, self.coluuid, attribute, value))
        
        intersection = set(objuuid_sets[0])
        for objuuids in objuuid_sets[1:]:
            intersection = intersection.intersection(set(objuuids))
        
        objuuids = []
        for objuuid in list(intersection):
            objuuids.append(objuuid)
        
        return objuuids

    def get_object(self, objuuid = None):
        if not objuuid:
            objuuid = sucky_uuid()
        return Object(self.coluuid, objuuid)
    
    def list_objuuids(self):
        return Document.list_collection_objects(self, self.coluuid)