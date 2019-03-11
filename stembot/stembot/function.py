#!/usr/bin/python

import traceback
import json

from copy import deepcopy
from imp import new_module
from document import Collection as SQLCollection
from counters import increment as ctr_increment, \
                     decrement as ctr_decrement

def run_function_by_name(name, event, context):
    # This was done to resolve circular references
    event = deepcopy(event)
    context = deepcopy(context)
    
    collection = SQLCollection("functions")
    
    fctuuids = collection.find_objuuids(name = name)
    
    if len(fctuuids) == 0:
        return {
            "exception" : "Function object for {0} could not be found!".format(name),
            "event" : event,
            "context" : context
        }
    elif len(fctuuids) > 1:
        return {
            "exception" : "Could not disambiguate function objects for {0}!".format(name),
            "event" : event,
            "context" : context
        }
    else:
        return run_function_by_uuid(fctuuids[0], event, context)
    
def run_function_by_uuid(fctuuid, event, context):
    # This was done to resolve circular references
    event = deepcopy(event)
    context = deepcopy(context)
    
    ctr_increment("threads (functions)")
    
    collection = SQLCollection("functions")
    
    function = collection.get_object(fctuuid)

    tempmodule = new_module("tempmodule")
    
    try:
        exec function.object["body"] in tempmodule.__dict__
        
        result = tempmodule.execute(event, context)
        
        ctr_decrement("threads (functions)")
        
        try:
            json.dumps({"test" : result})
            
            return {
                "result" : result,
                "event" : event,
                "context" : context
            }
        except:
            return {
                "exception" : "Result could not be serialized!",
                "event" : event,
                "context" : context
            }
    except:
        ctr_decrement("threads (functions)")
        
        return {
            "exception" : traceback.format_exc(),
            "event" : event,
            "context" : context
        }

collection = SQLCollection("functions")
collection.create_attribute("name", "['name']")