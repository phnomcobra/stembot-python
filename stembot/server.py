from base64 import b64encode
import hashlib
from logging.handlers import TimedRotatingFileHandler
import logging
import os
import sys

import cherrypy

from stembot.dao import kvstore
from stembot.dao.utils import get_uuid_str
from stembot.formatting import StemBotFormatter
from stembot.processor import Root
from stembot.scheduling import shutdown_timers

def main():
    """This function configures and starts the web server."""
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

    logfile_path = os.path.join('/log')
    os.makedirs(logfile_path, exist_ok=True)

    app_handler = TimedRotatingFileHandler(
        os.path.join(logfile_path, 'application.log'),
        when="D",
        backupCount=30
    )

    app_handler.setFormatter(StemBotFormatter())

    stderr_handler = logging.StreamHandler(sys.stderr)

    logger = logging.getLogger()
    logger.addHandler(app_handler)
    logger.addHandler(stderr_handler)
    logger.setLevel(logging.DEBUG)

    def exception_hook(exc_type, exc_value, exc_traceback):
        logger.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

    sys.excepthook = exception_hook

    cherrypy.config.update(config)
    cherrypy.engine.subscribe('stop', shutdown_timers)
    cherrypy.quickstart(Root())
