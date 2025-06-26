from threading import Thread
from time import time

from stembot import logging
from stembot.dao.collection import Collection
from stembot.scheduling import register_timer
from stembot.types.network import NetworkCascade

CASCADE_TIMEOUT = 60

def worker():
    cutoff = time() - CASCADE_TIMEOUT

    cascades = Collection('cascades', in_memory=True, model=NetworkCascade)
    for cascade in cascades.find(create_time=f'$lt:{cutoff}'):
        logging.debug(f'Expiring cascade {cascade.object.cscuuid}')
        cascade.destroy()

    register_timer(
        name='broadcast_worker',
        target=worker,
        timeout=1
    ).start()


collection = Collection('cascades', in_memory=True, model=NetworkCascade)
collection.create_attribute('cscuuid', "/cscuuid")

Thread(target=worker).start()
