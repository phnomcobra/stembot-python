from logging.handlers import TimedRotatingFileHandler
import logging
import os
import sys

import cherrypy

from stembot.formatting import StemBotFormatter
from stembot.models.config import CONFIG, log_config
from stembot.processor import Root
from stembot.scheduling import shutdown_timers

def main():
    """This function configures and starts the web server."""
    app_handler = TimedRotatingFileHandler(
        os.path.join(CONFIG.log_path, 'application.log'),
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

    log_config()

    config = {
        'agtuuid': CONFIG.agtuuid,
        'log.screen': False,
        'server.socket_host': CONFIG.socket_host,
        'server.socket_port': CONFIG.socket_port,
        'server.secret_digest': CONFIG.key,
        'request.show_tracebacks': False,
        'request.show_mismatched_params': False
    }

    cherrypy.config.update(config)
    cherrypy.engine.subscribe('stop', shutdown_timers)
    cherrypy.quickstart(Root())


if __name__ == '__main__':
    main() # pylint: disable=no-value-for-parameter
