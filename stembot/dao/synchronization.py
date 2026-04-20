from threading import RLock

from filelock import FileLock

LOCKS = {}

def synchronized(func):
    """Decorator function used for synchronizing document calls.
    The document's connection string is used as the key. Each connection
    string has its own file-based lock, enabling cross-process synchronization.
    """
    def wrapper(*args, **kwargs):
        if args[0] and hasattr(args[0], 'connection_str'):
            lock_key = args[0].connection_str
        else:
            lock_key = 'default'

        if lock_key not in LOCKS:
            if ':memory:' in lock_key:
                LOCKS[lock_key] = RLock(lock_key + '.lock')
            else:
                LOCKS[lock_key] = FileLock(lock_key + '.lock')

        with LOCKS[lock_key]:
            result = func(*args, **kwargs)
        return result
    return wrapper
