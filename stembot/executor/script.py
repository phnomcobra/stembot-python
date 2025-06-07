#!/usr/bin/python

import sys
import traceback

from datetime import datetime
from threading import Thread
from threading import Timer
from threading import Lock
from time import time

from stembot.dao import Collection as SQLCollection
from stembot.executor.counters import increment as ctr_increment
from stembot.executor.counters import decrement as ctr_decrement
from stembot.scheduling import register_timer
from stembot.adapter.python import interpret

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

    collection = SQLCollection('scripts')

    for scruuid in collection.list_objuuids():
        try:
            script = collection.get_object(scruuid)

            if 'enabled' not in script.object:
                script.object['enabled'] = False
                script.set()

            if 'silent' not in script.object:
                script.object['silent'] = False
                script.set()

            if 'seconds' not in script.object:
                script.object['seconds'] = '0'
                script.set()

            if 'minutes' not in script.object:
                script.object['minutes'] = '*'
                script.set()

            if 'hours' not in script.object:
                script.object['hours'] = '*'
                script.set()

            if 'dayofmonth' not in script.object:
                script.object['dayofmonth'] = '*'
                script.set()

            if 'dayofweek' not in script.object:
                script.object['dayofweek'] = '*'
                script.set()

            if 'year' not in script.object:
                script.object['year'] = '*'
                script.set()

            if 'body' not in script.object:
                script.object['body'] = ''
                script.set()

            if script.object['enabled'] in (True, 'true'):
                for t in range(int(last_worker_time), int(time())):
                    now = datetime.fromtimestamp(t).now()
                    if (
                        eval_cron_field(script.object['seconds'], now.second) and
                        eval_cron_field(script.object['minutes'], now.minute) and
                        eval_cron_field(script.object['hours'], now.hour) and
                        eval_cron_field(script.object['dayofmonth'], now.day) and
                        eval_cron_field(script.object['dayofweek'], now.weekday()) and
                        eval_cron_field(script.object['year'], now.year)
                    ):
                        queue(scruuid)
                        break
        except:
            if script.object['silent'] in (False, 'false'):
                script = collection.get_object(scruuid)
                script.object['status'] = 1
                script.object['stdout'] = ''
                script.object['stderr'] = str(traceback.format_exc())
                script.set()

    last_worker_time = time()

    register_timer(
        name='script_worker',
        target=worker,
        timeout=1
    ).start()

def queue(scruuid):
    jobs_lock.acquire()
    if scruuid not in jobs:
        jobs[scruuid] = {}
        ctr_increment('threads (script-{0})'.format(scruuid))
        Thread(target=execute, args=(scruuid,)).start()
    jobs_lock.release()

def execute(scruuid):
    script = SQLCollection('scripts').get_object(scruuid)

    status, stdout, stderr = interpret(script.object['body'])

    script.object['status'] = status
    script.object['stdout'] = stdout
    script.object['stderr'] = stderr

    if script.object['silent'] in (False, 'false'):
        script.set()

    ctr_decrement('threads (script-{0})'.format(scruuid))

    jobs_lock.acquire()
    del jobs[scruuid]
    jobs_lock.release()

collection = SQLCollection('scripts')

collection.create_attribute('name', "/name")
collection.create_attribute('enabled', "/enabled")
collection.create_attribute('silent', "/silent")
collection.create_attribute('status', "/status")
collection.create_attribute('stdout', "/stdout")
collection.create_attribute('stderr', "/stderr")

Thread(target=worker).start()
