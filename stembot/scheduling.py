import logging
from threading import Lock
from threading import Timer

timers = {}
shutdown = False
lock = Lock()

def register_timer(name, target, timeout, args=[]):
    global shutdown
    if not shutdown:
        lock.acquire()
        timers[name] = Timer(timeout, target, args=args)
        lock.release()
        return timers[name]
    else:
        return None

def cleanup_timers():
    lock.acquire()
    for name in list(timers):
        try:
            if not timers[name].is_alive():
                del timers[name]
        except Exception as error:
            logging.error('Cleanup on %s failed: %s', name, error)
    lock.release()

    register_timer(
        name='timer cleanup',
        target=register_timer,
        timeout=1
    )

def shutdown_timers():
    logging.info('Shutting down timers...')
    global shutdown
    shutdown = True
    lock.acquire()
    for name in timers:
        try:
            timers[name].cancel()
            logging.info('Cancelled %s.', name)
        except Exception as error:
            logging.error('Cancelling %s failed: %s', name, error)
    lock.release()

register_timer(
    name='timer cleanup',
    target=register_timer,
    timeout=1
)
