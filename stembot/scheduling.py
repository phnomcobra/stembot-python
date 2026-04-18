"""Task scheduling system for periodic background jobs.

Provides decorator-based scheduling and registry system for registering
periodically-executed functions. Functions are registered by their fully
qualified name (module.function_name) to enable pickling and serialization
of Task objects.

Key features:
- @scheduled decorator to register functions with execution intervals
- Function registry mapping fully qualified names to callables
- Support for one-time and recurring tasks
- Thread-based scheduler loop that discovers and executes tasks
- Task arguments (args, kwargs) and one-time execution control
"""

import logging
import threading
import time

from stembot.dao import Collection
from stembot.enums import TaskStatus
from stembot.models.schedule import Task

OPERATING = False

# Global registry mapping fully qualified function names to callables
_FUNCTION_REGISTRY = {}


def _get_function_ref(func) -> str:
    """Get the fully qualified reference string for a function.

    Args:
        func: A callable function

    Returns:
        Fully qualified reference string in format 'module.function_name'
    """
    module = func.__module__
    name = func.__qualname__
    return f"{module}.{name}"


def _resolve_function_ref(call_ref: str):
    """Resolve a function reference to the actual callable.

    Looks up a registered function by its fully qualified reference.

    Args:
        call_ref: Fully qualified function reference (module.function_name)

    Returns:
        The callable function

    Raises:
        KeyError: If the function reference is not registered
    """
    if call_ref not in _FUNCTION_REGISTRY:
        raise KeyError(f"Function reference not found in registry: {call_ref}")
    return _FUNCTION_REGISTRY[call_ref]


def scheduled(every_secs: int):
    """Decorator to register a function as a scheduled task.

    Registers a function as a task in the tasks collection with a specified
    execution interval. The decorated function is registered in a global
    registry using its fully qualified name to enable serialization.

    Args:
        every_secs: Interval in seconds between task executions

    Returns:
        Decorator function that registers the target function as a task

    Example:
        @scheduled(every_secs=60)
        def my_background_task():
            # This will be executed every 60 seconds
            print("Task executed!")

    Note:
        The decorator stores a string reference to the function (not the
        callable itself) to support pickling and serialization.
    """
    def decorator(func):
        # Register the function in the global registry
        func_ref = _get_function_ref(func)
        _FUNCTION_REGISTRY[func_ref] = func

        # Create and store the task with the function reference
        Collection[Task]('tasks', in_memory=True).build_object(call_ref=func_ref, every_secs=every_secs)
        return func
    return decorator


def _dispatch(objuuid: str):
    """Execute a task by resolving its function reference and calling it.

    Retrieves a task from the collection, resolves its function reference
    using the global registry, executes it with stored arguments, and then
    stops it for next execution.

    Args:
        objuuid: The object UUID of the task to dispatch/execute
    """
    task = Collection[Task]('tasks', in_memory=True).get_object(objuuid=objuuid)
    try:
        # Resolve the function reference from the registry
        func = _resolve_function_ref(task.object.call_ref)
        func(*task.object.args, **task.object.kwargs)
    except Exception as e: # pylint: disable=broad-except
        logging.error('Error executing task %s: %s', objuuid, e)

    task.object.stop()
    task.commit()


def _loop():
    """Main scheduler loop that discovers and executes scheduled tasks.

    Continuously runs until SHUTDOWN is True. Queries the tasks collection
    for tasks whose touch_time has passed, and dispatches them for execution
    in separate threads. Updates task state on each iteration.
    """
    logging.info('Starting scheduler loop')
    tasks = Collection[Task]('tasks', in_memory=True)

    while OPERATING:
        for task in tasks.find(touch_time=f'$lt:{time.time()}'):
            if task.object.status is TaskStatus.STOPPED:
                task.object.touch()
                task.object.run()
                task.commit()
                threading.Thread(target=_dispatch, args=(task.object.objuuid,)).start()
            else:
                task.object.touch()
                task.commit()

        time.sleep(1)
    logging.info('Shutdown scheduler loop')


def shutdown(*_args, **_kargs) -> None:
    """Gracefully shutdown the scheduler loop.

    Sets the OPERATING flag to False, which causes the scheduler loop to exit
    after the current iteration. Can be used as a signal handler for SIGTERM.
    """
    global OPERATING # pylint: disable=global-statement
    OPERATING = False


def start() -> None:
    """Start the scheduler loop in a separate thread.

    Initializes the tasks collection and starts the main scheduler loop in a
    new thread. Also registers signal handlers for graceful shutdown.
    """
    global OPERATING # pylint: disable=global-statement
    if not OPERATING:
        OPERATING = True
        threading.Thread(target=_loop).start()


collection = Collection[Task]('tasks', in_memory=True)
collection.create_attribute('touch_time', "/touch_time")
