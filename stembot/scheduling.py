import logging
import threading
import time

from stembot.dao import Collection
from stembot.enums import TaskStatus
from stembot.models.schedule import Task

SHUTDOWN = False

def scheduled(every_secs: int):
    def decorator(func):
        Collection[Task]('tasks').build_object(call=func, every_secs=every_secs)
        return func
    return decorator


def schedule(task: Task):
    Collection[Task]('tasks').upsert_object(task)


def _dispatch(objuuid: str):
    task = Collection[Task]('tasks').get_object(objuuid=objuuid)
    try:
        task.object.call(*task.object.args, **task.object.kwargs)
    except Exception as e: # pylint: disable=broad-except
        logging.error('Error executing task %s: %s', objuuid, e)

    if task.object.run_once:
        task.destroy()
    else:
        task.object.stop()
        task.commit()


def _loop():
    logging.info('Starting scheduler loop')
    tasks = Collection[Task]('tasks')

    while not SHUTDOWN:
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
    global SHUTDOWN # pylint: disable=global-statement
    SHUTDOWN = True


collection = Collection[Task]('tasks')
collection.create_attribute('touch_time', "/touch_time")

threading.Thread(target=_loop).start()
