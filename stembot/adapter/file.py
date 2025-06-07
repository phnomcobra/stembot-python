#!/usr/bin/python3

FILE_HANDLE_TIME_OUT = 60

import traceback

from threading import Timer, Lock, Thread
from time import time
from stembot.dao.utils import get_uuid_str
from stembot.scheduling import register_timer

file_handles = {}
file_handles_lock = Lock()

def file_handle_seek(fhduuid, position):
    file_handles[fhduuid]['file'].seek(position)
    file_handles[fhduuid]['contact'] = time()

def file_handle_truncate(fhduuid, num_bytes):
    file_handles[fhduuid]['file'].truncate(num_bytes)
    file_handles[fhduuid]['contact'] = time()

def file_handle_read(fhduuid, num_bytes=None):
    file_handles[fhduuid]['contact'] = time()
    if num_bytes == None:
        return file_handles[fhduuid]['file'].read()
    else:
        return file_handles[fhduuid]['file'].read(num_bytes)

def file_handle_write(fhduuid, data):
    file_handles[fhduuid]['file'].write(data)
    file_handles[fhduuid]['contact'] = time()

def file_handle_tell(fhduuid):
    file_handles[fhduuid]['contact'] = time()
    return file_handles[fhduuid]['file'].tell()

def create_file_handle(filename, mode):
    fhduuid = get_uuid_str()

    try:
        file_handles_lock.acquire()
        file_handles[fhduuid] = {}
        file_handles[fhduuid]['contact'] = time()
        file_handles[fhduuid]['file'] = open(filename, mode)
        Thread(target=file_handle_time_out_worker, args=(fhduuid,)).start()
        file_handles_lock.release()
    except:
        del file_handles[fhduuid]
        file_handles_lock.release()
        raise Exception(traceback.format_exc())

    return fhduuid

def close_file_handle(fhduuid):
    try:
        file_handles_lock.acquire()
        try:
            file_handles[fhduuid]['file'].close()
        except:
            pass
        del file_handles[fhduuid]
        file_handles_lock.release()
    except Exception as e:
        file_handles_lock.release()
        raise Exception(traceback.format_exc())

def file_read(filename):
    f = open(filename, 'rb')
    data = f.read()
    f.close()
    return data

def file_write(filename, data):
    f = open(filename, 'wb')
    f.write(data)
    f.close()

def file_handle_time_out_worker(fhduuid):
    try:
        if time() - file_handles[fhduuid]['contact'] > FILE_HANDLE_TIME_OUT:
            close_file_handle(fhduuid)
        else:
            register_timer(
                name=fhduuid,
                target=file_handle_time_out_worker,
                args=(fhduuid,),
                timeout=60
            ).start()
    except:
        pass
