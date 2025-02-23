#!/usr/bin/python3

PROCESS_HANDLE_TIME_OUT = 60 * 60 * 8

import sys
import traceback

from subprocess import Popen, PIPE
from threading import Timer, Lock, Thread
from time import time
from queue import Queue, Empty
from stembot.dao import get_uuid_str
from stembot.executor.timers import register_timer

ON_POSIX = 'posix' in sys.builtin_module_names

def enqueue_stdout(out, queue):
    for line in iter(out.readline, b''):
        queue.put(line)
    out.close()

def enqueue_stderr(out, queue):
    for line in iter(out.readline, b''):
        queue.put(line)
    out.close()

def process_sync(command, timeout=10):
    if type(command) == type([]):
        shell = False
    else:
        shell = True

    process = Popen(
        command,
        stdout=PIPE,
        stderr=PIPE,
        shell=shell
    )

    kill_process = lambda p: p.kill()

    timer = register_timer(
        name=f'process-{time()}',
        target=kill_process,
        args=(process,),
        timeout=timeout
    )

    try:
        timer.start()
        process_output_buffer, process_stderr_buffer = process.communicate()
    finally:
        timer.cancel()

    return process.returncode, process_output_buffer, process_stderr_buffer

process_handles = {}
process_handles_lock = Lock()

def create_process_handle(command):
    phduuid = get_uuid_str()

    if type(command) == type([]):
        shell = False
    else:
        shell = True

    try:
        process_handles_lock.acquire()
        process_handles[phduuid] = {}
        process_handles[phduuid]['contact'] = time()
        process_handles[phduuid]['process'] = Popen(
            command,
            stdout=PIPE,
            stderr=PIPE,
            stdin=PIPE,
            bufsize=1,
            shell=shell,
            close_fds=ON_POSIX
        )

        process_handles[phduuid]['stdout queue'] = Queue()

        process_handles[phduuid]['stdout thread'] = Thread(
            target=enqueue_stdout,
            args=(
                process_handles[phduuid]['process'].stdout,
                process_handles[phduuid]['stdout queue']
            )
        )
        process_handles[phduuid]['stdout thread'].daemon = True
        process_handles[phduuid]['stdout thread'].start()

        process_handles[phduuid]['stderr queue'] = Queue()

        process_handles[phduuid]['stderr thread'] = Thread(
            target=enqueue_stderr,
            args=(
                process_handles[phduuid]['process'].stderr,
                process_handles[phduuid]['stderr queue']
            )
        )
        process_handles[phduuid]['stderr thread'].daemon = True
        process_handles[phduuid]['stderr thread'].start()

        Thread(target=process_handle_time_out_worker, args=(phduuid,)).start()
        process_handles_lock.release()
    except:
        del process_handles[phduuid]
        process_handles_lock.release()
        raise Exception(traceback.format_exc())

    return phduuid

def process_handle_status(phduuid):
    process_handles[phduuid]['contact'] = time()
    return process_handles[phduuid]['process'].poll()

def process_handle_kill(phduuid):
    process_handles[phduuid]['contact'] = time()
    process_handles[phduuid]['process'].kill()

def process_handle_terminate(phduuid):
    process_handles[phduuid]['contact'] = time()
    process_handles[phduuid]['process'].terminate()

def process_handle_wait(phduuid):
    process_handles[phduuid]['contact'] = time()
    process_handles[phduuid]['process'].wait()

def process_handle_send(phduuid, data):
    process_handles[phduuid]['contact'] = time()
    process_handles[phduuid]['process'].stdin.write(data)
    process_handles[phduuid]['process'].stdin.flush()

def process_handle_recv(phduuid):
    process_handles[phduuid]['contact'] = time()

    stdout = bytearray()
    while True:
        try:
            stdout.extend(process_handles[phduuid]['stdout queue'].get_nowait())
        except Empty:
            break

    stderr = bytearray()
    while True:
        try:
            stderr.extend(process_handles[phduuid]['stderr queue'].get_nowait())
        except Empty:
            break

    return stdout, stderr

def close_process_handle(phduuid):
    try:
        process_handles_lock.acquire()
        try:
            process_handle_terminate(phduuid)
        except:
            pass
        del process_handles[phduuid]
        process_handles_lock.release()
    except:
        process_handles_lock.release()
        raise Exception(traceback.format_exc())

def process_handle_time_out_worker(phduuid):
    try:
        if time() - process_handles[phduuid]['contact'] > PROCESS_HANDLE_TIME_OUT:
            close_process_handle(phduuid)
        else:
            register_timer(
                name=phduuid,
                target=process_handle_time_out_worker,
                args=(phduuid,),
                timeout=60
            ).start()
    except:
        pass
