from threading import Lock
from threading import Timer

timers = {}
shutdown = False
lock = Lock()

def register_timer(name, target, timeout, args=[]):
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
        except:
            print(f'Cleanup on {name} failed!')
    lock.release()

    register_timer(
        name='timer cleanup',
        target=register_timer,
        timeout=60
    )

def shutdown_timers():
    print('Shutting down timers...')
    shutdown = True
    lock.acquire()
    for name in timers:
        try:
            timers[name].cancel()
            print(f'Cancelled {name}.')
        except:
            print(f'Cancelling {name} failed!')
    lock.release()

register_timer(
    name='timer cleanup',
    target=register_timer,
    timeout=60
)
