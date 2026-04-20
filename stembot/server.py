"""FastAPI server startup and configuration for the stembot agent.

Initializes and runs the FastAPI application with proper logging, signal handling,
and graceful shutdown support. Configures rotating file logging and stderr output,
sets up exception handling, and registers signal handlers for clean termination.

The server runs the FastAPI app from the processor module, which provides the
/control and /mpi endpoints for control form and network message handling.
"""
import uvicorn

import stembot.processor # Need to import this to register routes and initialize the logger
from stembot.models.config import CONFIG
from stembot.scheduling import start, shutdown

def main() -> None:
    start() # Only the parent process runs the scheduler's event loop
    uvicorn.run(
        'stembot.processor:app',
        host=CONFIG.socket_host,
        port=CONFIG.socket_port,
        log_config=None,
        workers=2
    )
    shutdown()


if __name__ == '__main__':
    main() # pylint: disable=no-value-for-parameter
