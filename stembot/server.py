"""FastAPI server startup and configuration for the stembot agent.

Initializes and runs the FastAPI application with proper logging, signal handling,
and graceful shutdown support. Configures rotating file logging and stderr output,
sets up exception handling, and registers signal handlers for clean termination.

The server runs the FastAPI app from the processor module, which provides the
/control and /mpi endpoints for control form and network message handling.
"""

import logging
import signal

import uvicorn

from stembot.models.config import CONFIG
from stembot.scheduling import shutdown

def main() -> None:
    """Main entry point for starting the FastAPI server."""
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    uvicorn.run(
        'stembot.processor:app',
        host=CONFIG.socket_host,
        port=CONFIG.socket_port,
        log_config=None,
        log_level=logging.INFO,
        workers=2
    )


if __name__ == '__main__':
    main() # pylint: disable=no-value-for-parameter
