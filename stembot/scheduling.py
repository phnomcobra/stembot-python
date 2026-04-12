"""Timer management and scheduling system for periodic background tasks.

Provides thread-safe management of Python Timer objects used throughout the application
for background workers like message processing, peer polling, and route advertisement.
Handles registration, cleanup, and graceful shutdown of timers with thread-safe locking.

Key features:
- Register named timers with callback functions and timeouts
- Automatic cleanup of completed timers
- Graceful shutdown with cancellation of all active timers
- Thread-safe access via Lock for concurrent timer operations
"""

import logging
from threading import Lock
from threading import Timer

TIMERS     = {}
SHUTDOWN   = False
TIMER_LOCK = Lock()

def register_timer(name: str, target: callable, timeout: float | int, args: list = None) -> Timer | None:
    """Register a named timer that calls a function after a timeout period.

    Creates and registers a Timer object that will execute the target function
    after the specified timeout (in seconds). If the system is shutting down,
    returns None instead of registering the timer. Timers are stored in a global
    registry and can be accessed by name for management.

    Args:
        name: Unique name for the timer (used for identification and cleanup).
        target: Callable function to execute when the timer expires.
        timeout: Time in seconds before the timer fires.
        args: Optional list of arguments to pass to the target function (default: None).

    Returns:
        The Timer object if successfully registered, or None if system is shutting down.
    """
    if not SHUTDOWN:
        TIMER_LOCK.acquire()
        TIMERS[name] = Timer(timeout, target, args=args)
        TIMER_LOCK.release()
        return TIMERS[name]
    else:
        return None


def cleanup_timers() -> None:
    """Remove completed timers from the registry and reschedule cleanup.

    Scans all registered timers and removes those that are no longer running.
    Automatically reschedules itself to run again in 1 second, providing continuous
    cleanup of stale timer entries. Thread-safe via TIMER_LOCK.
    """
    TIMER_LOCK.acquire()
    for name in list(TIMERS):
        try:
            if not TIMERS[name].is_alive():
                del TIMERS[name]
        except Exception as error: # pylint: disable=broad-except
            logging.error('Cleanup on %s failed: %s', name, error)
    TIMER_LOCK.release()
    register_timer(name='timer cleanup', target=cleanup_timers, timeout=1)


def shutdown_timers() -> None:
    """Cancel all active timers and prevent new timer registration.

    Sets the global SHUTDOWN flag to prevent new timers from being registered
    and cancels all currently running timers. Useful for graceful application
    shutdown. Thread-safe via TIMER_LOCK.
    """
    logging.info('Shutting down timers...')
    global SHUTDOWN # pylint: disable=global-statement
    SHUTDOWN = True
    TIMER_LOCK.acquire()
    for name, timer in TIMERS.items():
        try:
            timer.cancel()
            logging.info('Cancelled %s.', name)
        except Exception as error: # pylint: disable=broad-except
            logging.error('Cancelling %s failed: %s', name, error)
    TIMER_LOCK.release()


register_timer(name='timer cleanup', target=cleanup_timers, timeout=1)
