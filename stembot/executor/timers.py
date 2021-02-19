from threading import Timer

timers = {}
shutdown = False

def register_timer(name, target, timeout, args=[]):
    if not shutdown:
        timers[name] = Timer(timeout, target, args=args)
        return timers[name]
    else:
        return None

def shutdown_timers():
    print('Shutting down timers...')
    shutdown = True
    for name in timers:
        try:
            timers[name].cancel()
            print(f'Cancelled {name}.')
        except:
            print(f'Cancelling {name} failed!')

