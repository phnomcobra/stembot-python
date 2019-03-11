#!/usr/bin/python

import traceback

from datetime import datetime
from threading import Thread, Timer
from time import time
from imp import new_module

from document import Collection as SQLCollection
from counters import increment as ctr_increment, \
                     decrement as ctr_decrement, \
                     get as ctr_get_name

def eval_cron_field(cron_str, now_val):
    result = False
    
    try:
        for field in str(cron_str).split(','):
            if '*' in field:
                result = True
            elif '-' in field:
                if int(now_val) in range(int(field.split('-')[0]), \
                                         int(field.split('-')[1]) + 1):
                    result = True
            elif int(field) == int(now_val):
                result = True
    except:
        pass
    
    return result

def worker():
    Timer(60.0, worker).start()
    
    now = datetime.now()
    
    collection = SQLCollection("scripts")
        
    for scruuid in collection.list_objuuids():
        try:
            script = collection.get_object(scruuid)
            
            if "enabled" not in script.object:
                script.object["enabled"] = False
                script.set()
            
            if "minutes" not in script.object:
                script.object["minutes"] = "*"
                script.set()
            
            if "hours" not in script.object:
                script.object["hours"] = "*"
                script.set()
            
            if "dayofmonth" not in script.object:
                script.object["dayofmonth"] = "*"
                script.set()
            
            if "dayofweek" not in script.object:
                script.object["dayofweek"] = "*"
                script.set()
            
            if "year" not in script.object:
                script.object["year"] = "*"
                script.set()
            
            if "body" not in script.object:
                script.destroy()
            
            if script.object["enabled"] in (True, "true"):
                if eval_cron_field(script.object["minutes"], now.minute) and \
                   eval_cron_field(script.object["hours"], now.hour) and \
                   eval_cron_field(script.object["dayofmonth"], now.day) and \
                   eval_cron_field(script.object["dayofweek"], now.weekday()) and \
                   eval_cron_field(script.object["year"], now.year) and \
                   ctr_get_name("threads (script-{0})".format(script.objuuid)) == 0:
                    ctr_increment("threads (script-{0})".format(script.objuuid))   
                    Thread(target = run_script, args = (script.objuuid,)).start()
        except:
            script = collection.get_object(scruuid)
            if "body" not in script.object:
                script.destroy()
            else:
                script.object["status"] = 1
                script.object["exception"] = traceback.format_exc()
                script.set()

def run_script(scruuid):
    collection = SQLCollection("scripts")
    
    script = collection.get_object(scruuid)

    tempmodule = new_module("tempmodule")
    
    try:
        exec script.object["body"] in tempmodule.__dict__
        
        if "exception" in script.object:
            del script.object["exception"]
        
        script.object["status"] = 0
        script.set()
    except:
        script.object["status"] = 1
        script.object["exception"] = traceback.format_exc()
        script.set()
    finally:
        ctr_decrement("threads (script-{0})".format(scruuid))

collection = SQLCollection("scripts")

collection.create_attribute("name", "['name']")
collection.create_attribute("enabled", "['enabled']")
collection.create_attribute("status", "['status']")

Thread(target = worker).start()