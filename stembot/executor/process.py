#!/usr/bin/python3
import sys
from subprocess import Popen, PIPE
from time import time

from stembot.scheduling import register_timer
from stembot.types.control import SyncProcess

ON_POSIX = 'posix' in sys.builtin_module_names

def enqueue_stdout(out, queue):
    for line in iter(out.readline, b''):
        queue.put(line)
    out.close()

def enqueue_stderr(out, queue):
    for line in iter(out.readline, b''):
        queue.put(line)
    out.close()

def sync_process(form: SyncProcess) -> SyncProcess:
    if isinstance(form.command, list):
        shell = False
    else:
        shell = True

    process = Popen(
        form.command,
        stdout=PIPE,
        stderr=PIPE,
        shell=shell
    )

    kill_process = lambda p: p.kill()

    timer = register_timer(
        name=f'process-{time()}',
        target=kill_process,
        args=(process,),
        timeout=form.timeout
    )

    try:
        timer.start()
        form.start_time = time()
        process_output_buffer, process_stderr_buffer = process.communicate()
    finally:
        form.elapsed_time = time() - form.start_time
        timer.cancel()

    form.stdout = process_output_buffer.decode()
    form.stderr = process_stderr_buffer.decode()
    form.status = process.returncode

    return form
