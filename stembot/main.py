#!/usr/bin/python3
from base64 import b64encode
import hashlib
from logging.handlers import TimedRotatingFileHandler
import logging
import os
import sys

import cherrypy

from stembot import logging as app_logger
from stembot.dao import kvstore
from stembot.dao.utils import get_uuid_str
from stembot.controller import Root
from stembot.scheduling import shutdown_timers

def start():
    """This function configures and starts the web server."""
    current_dir = os.path.dirname(os.path.abspath(__file__))

    config = {
        'agtuuid': kvstore.get(name='agtuuid', default=get_uuid_str()),
        'log.screen': False,
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
    logger.addHandler(logging.StreamHandler(sys.stderr))
    logger.setLevel(logging.DEBUG)

    cherrypy.config.update(config)
    cherrypy.engine.subscribe('log', app_logger.log)
    cherrypy.engine.subscribe('stop', shutdown_timers)

    cherrypy.quickstart(Root())
