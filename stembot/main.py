#!/usr/bin/python3
import hashlib
from logging.handlers import TimedRotatingFileHandler
import logging
import os

import cherrypy

from base64 import b64encode
from stembot.audit import logging as app_logger
from stembot.model import kvstore
from stembot.dao.utils import get_uuid_str
from stembot.controller.root import Root
from stembot.executor.timers import shutdown_timers

def on_cherrypy_log(msg, level):
    """This function subscribes the logger functions to the log
    channel on cherrypy's bus."""
    if level <= 20:
        app_logger.info(msg)
    else:
        app_logger.error(msg)

def start():
    """This function configures and starts the web server."""
    current_dir = os.path.dirname(os.path.abspath(__file__))

    config = {
        'agtuuid': kvstore.get(name='agtuuid', default=get_uuid_str()),
        'log.screen': True,
        'server.socket_host': kvstore.get(name='socket_host', default='0.0.0.0'),
        'server.socket_port': kvstore.get(name='socket_port', default=53080),
        'server.secret_digest': kvstore.get(
            name='secret_digest',
            default=b64encode(hashlib.sha256('changeme'.encode()).digest()).decode()
        ),
        'request.show_tracebacks': False,
        'request.show_mismatched_params': False
    }

    logfile_path = os.path.join(current_dir, './log')
    os.makedirs(logfile_path, exist_ok=True)

    access_handler = TimedRotatingFileHandler(
        os.path.join(logfile_path, 'access.log'),
        when="D",
        backupCount=30
    )
    cherrypy.log.access_log.addHandler(access_handler)

    app_handler = TimedRotatingFileHandler(
        os.path.join(logfile_path, 'application.log'),
        when="D",
        backupCount=30
    )
    logger = logging.getLogger('app')
    logger.addHandler(app_handler)
    logger.setLevel(logging.DEBUG)

    cherrypy.config.update(config)
    cherrypy.engine.subscribe('log', on_cherrypy_log)
    cherrypy.engine.subscribe('stop', shutdown_timers)
    cherrypy.quickstart(Root())
