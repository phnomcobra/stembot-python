from logging.handlers import TimedRotatingFileHandler
import logging
import os
import sys
import signal

import uvicorn
from fastapi import FastAPI

from stembot.formatting import StemBotFormatter
from stembot.models.config import CONFIG, log_config
from stembot.processor import setup_routes
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

    app = FastAPI()

    def shutdown_handler(signum, frame):
        shutdown_timers()
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGINT, shutdown_handler)

    setup_routes(app)

    uvicorn.run(
        app,
        host=CONFIG.socket_host,
        port=CONFIG.socket_port,
        log_config=None,
        log_level=logging.INFO
    )


if __name__ == '__main__':
    main() # pylint: disable=no-value-for-parameter
