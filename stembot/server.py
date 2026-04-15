"""FastAPI server startup and configuration for the stembot agent.

Initializes and runs the FastAPI application with proper logging, signal handling,
and graceful shutdown support. Configures rotating file logging and stderr output,
sets up exception handling, and registers signal handlers for clean termination.

The server runs the FastAPI app from the processor module, which provides the
/control and /mpi endpoints for control form and network message handling.
"""

import logging
import sys
import signal

import uvicorn

from stembot.models.config import CONFIG
from stembot.scheduling import shutdown_timers

def main() -> None:
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
        log_level=logging.INFO,
        workers=4
    )


if __name__ == '__main__':
    main() # pylint: disable=no-value-for-parameter
