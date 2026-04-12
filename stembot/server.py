"""FastAPI server startup and configuration for the stembot agent.

Initializes and runs the FastAPI application with proper logging, signal handling,
and graceful shutdown support. Configures rotating file logging and stderr output,
sets up exception handling, and registers signal handlers for clean termination.

The server runs the FastAPI app from the processor module, which provides the
/control and /mpi endpoints for control form and network message handling.
"""

from logging.handlers import TimedRotatingFileHandler
import logging
import os
import sys
import signal

import uvicorn

from stembot.formatting import StemBotFormatter
from stembot.models.config import CONFIG, log_config
from stembot.scheduling import shutdown_timers

def main() -> None:
    """Configure logging, signal handlers, and start the FastAPI server.

    Sets up rotating file and stderr logging with custom formatting, configures
    signal handlers for SIGTERM and SIGINT to enable graceful shutdown, and
    registers an exception hook to log uncaught exceptions. Then starts the
    uvicorn server running the FastAPI app from stembot.processor on the
    configured host and port.
    """
    app_handler = TimedRotatingFileHandler(
        os.path.join(CONFIG.log_path, 'application.log'),
        when="h",
        backupCount=1
    )

    app_handler.setFormatter(StemBotFormatter())

    stderr_handler = logging.StreamHandler(sys.stderr)

    logger = logging.getLogger()
    logger.addHandler(app_handler)
    logger.addHandler(stderr_handler)
    logger.setLevel(logging.DEBUG)

    def exception_hook(exc_type, exc_value, exc_traceback) -> None:
        """Log uncaught exceptions to the application logger.

        Custom exception hook that logs all unhandled exceptions with full
        traceback information to provide visibility into unexpected errors.

        Args:
            exc_type: The exception type.
            exc_value: The exception value/instance.
            exc_traceback: The traceback object.
        """
        logger.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

    sys.excepthook = exception_hook

    log_config()

    def shutdown_handler(*_args, **_kargs) -> None:
        """Handle graceful shutdown on SIGTERM or SIGINT.

        Stops all background timers and exits cleanly. Called when the process
        receives SIGTERM or SIGINT signals. Allows background workers to stop
        gracefully before exit.
        """
        shutdown_timers()
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGINT, shutdown_handler)

    uvicorn.run(
        'stembot.processor:app',
        host=CONFIG.socket_host,
        port=CONFIG.socket_port,
        log_config=None,
        log_level=logging.INFO
    )


if __name__ == '__main__':
    main() # pylint: disable=no-value-for-parameter
