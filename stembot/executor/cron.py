#!/usr/bin/python

import traceback

from datetime import datetime
from threading import Thread
from threading import Timer
from threading import Lock
from time import time

from stembot.dao.document import Collection as SQLCollection
from stembot.executor.counters import increment as ctr_increment
from stembot.executor.counters import decrement as ctr_decrement
from stembot.adapter.process import process_sync

last_worker_time = time()
jobs = {}
jobs_lock = Lock()

def eval_cron_field(cron_str, now_val):
    result = False
    
    try:
        for field in str(cron_str).split(','):
            if '*' in field:
                result = True
            elif '-' in field:
                if int(now_val) in range(
                    int(field.split('-')[0]),
                    int(field.split('-')[1]) + 1
                ):
                    result = True
            elif int(field) == int(now_val):
                result = True
    except:
        pass
    
    return result

def worker():
    global last_worker_time
    
    collection = SQLCollection('crons')
        
    for cronuuid in collection.list_objuuids():
        try:
            cron = collection.get_object(cronuuid)
            
            if 'enabled' not in cron.object:
                cron.object['enabled'] = False
                cron.set()
            
            if 'minutes' not in cron.object:
                cron.object['minutes'] = '*'
                cron.set()
            
            if 'hours' not in cron.object:
                cron.object['hours'] = '*'
                cron.set()
            
            if 'dayofmonth' not in cron.object:
                cron.object['dayofmonth'] = '*'
                cron.set()
            
            if 'dayofweek' not in cron.object:
                cron.object['dayofweek'] = '*'
                cron.set()
            
            if 'year' not in cron.object:
                cron.object['year'] = '*'
                cron.set()
            
            if 'timeout' not in cron.object:
                cron.object['timeout'] = 60
                cron.set()
            
            if 'command' not in cron.object:
                cron.object['command'] = ''
                cron.set()
            
            if cron.object['enabled'] in (True, 'true'):
                for t in range(int(last_worker_time), int(time()), 60):
                    now = datetime.fromtimestamp(t).now()
                    if (
                        eval_cron_field(cron.object['minutes'], now.minute) and
                        eval_cron_field(cron.object['hours'], now.hour) and
                        eval_cron_field(cron.object['dayofmonth'], now.day) and
                        eval_cron_field(cron.object['dayofweek'], now.weekday()) and
                        eval_cron_field(cron.object['year'], now.year)
                    ):
                        queue(cronuuid)
                        break
        except:
            cron = collection.get_object(cronuuid)
            cron.object['status'] = 1
            cron.object['stdout b64data'] = b64encode(''.encode()).decode()
            cron.object['stderr b64data'] = b64encode(str(traceback.format_exc()).encode()).decode()
            cron.set()
    
    last_worker_time = time()
    Timer(60, worker).start()

def queue(cronuuid):
    jobs_lock.acquire()
    if cronuuid not in jobs:
        jobs[cronuuid] = {}
        ctr_increment('threads (cron-{0})'.format(cronuuid))
        Thread(target=execute, args=(cronuuid,)).start()
    jobs_lock.release()

def execute(cronuuid):
    try:
        cron = SQLCollection('crons').get_object(cronuuid)
        
        status, stdout, stderr = process_sync(
            cron.object['command'],
            timeout=cron.object['timeout']
        )
        
        cron.object['stdout b64data'] = b64encode(stdout).decode()
        cron.object['stderr b64data'] = b64encode(stderr).decode()
        cron.object['status'] = status
        
        cron.set()        
    except:
        pass
    
    ctr_decrement('threads (cron-{0})'.format(cronuuid))
    jobs_lock.acquire()
    del jobs[cronuuid]
    jobs_lock.release()

collection = SQLCollection('crons')

collection.create_attribute('name', "['name']")
collection.create_attribute('enabled', "['enabled']")
collection.create_attribute('status', "['status']")
collection.create_attribute('command', "['command']")

Thread(target=worker).start()
