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
import time

from stembot.dao import Collection
from stembot.models.schedule import Task

SHUTDOWN = False


def worker():
    tasks = Collection[Task]('tasks')
    
    while not SHUTDOWN:
    
    for task in tasks.find(touch_time=f'$lt:{time.time()}'):
        task.touch()
        if task.status is TaskStatus.RUNNING and task.expire_time and time.time() >= task.expire_time:
            logging.info(f"Running task {task.uuid} with pid {task.pid}")
            task.run()
            collection.upsert_object(task)

    register_timer('worker', worker, 1.0)

def shutdown() -> None:
    """Cancel all active timers and prevent new timer registration.

    Sets the global SHUTDOWN flag to prevent new timers from being registered
    and cancels all currently running timers. Useful for graceful application
    shutdown. Thread-safe via TIMER_LOCK.
    """
    global SHUTDOWN # pylint: disable=global-statement
    SHUTDOWN = True




collection = Collection[Task]('tasks')
collection.create_attribute('touch_time', "/touch_time")

