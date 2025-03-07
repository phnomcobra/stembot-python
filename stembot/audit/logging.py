"""This module forms the interface for logging."""
from datetime import datetime
from enum import Enum
import logging
import logging.handlers
from inspect import stack
import sys
from typing import Any

LOGGER = logging.getLogger('app')

class LogLevel(Enum):
    """This class is enum for the listed log levels."""
    CRITICAL = 50
    ERROR = 40
    WARNING = 30
    INFO = 20
    DEBUG = 10

def critical(item: Any = ''):
    """This function logs a critical item in the application log.

    Args:
        item:
            Anything that has __str__.
    """
    _log(item, LogLevel.CRITICAL)

def error(item: Any = ''):
    """This function logs a error item in the application log.

    Args:
        item:
            Anything that has __str__.
    """
    _log(item, LogLevel.ERROR)

def warning(item: Any = ''):
    """This function logs a warning item in the application log.

    Args:
        item:
            Anything that has __str__.
    """
    _log(item, LogLevel.WARNING)

def info(item: Any = ''):
    """This function logs a information item in the application log.

    Args:
        item:
            Anything that has __str__.
    """
    _log(item, LogLevel.INFO)

def debug(item: Any = ''):
    """This function logs a debugging item in the application log.

    Args:
        item:
            Anything that has __str__.
    """
    _log(item, LogLevel.DEBUG)

def log(item: Any, level: Any):
    """This function attempts to log an item and attempt to cast level
    into a LogLevel enum. If the cast fails, item is cast as a warning.
    Args:
        item:
            Anything that has __str__.

        level:
            Anything castable as a LogLevel.
    """
    try:
        _log(item, LogLevel(level))
    except: # pylint: disable=bare-except
        _log(item, LogLevel.WARNING)

def _log(item: Any, level: LogLevel):
    """This is a dunder method for handling all the application log events. It has a
    dual functionality. It formats and logs lines via the builtin logger and it
    formats and logs lines via `add_message` which is registered in the front end
    consoles. Inspect is use to read the caller's stack frame to indicate a file and
    function that's generating the log entry. This function is not called directly so that
    that stack frame 2 is caller's frame.

    Args:
        item:
            Anything that has __str__.

        level:
            A `LogLevel` enum indicating what log level to use.
    """
    lines = str(item).split("\n")

    frame = stack()[2]

    if sys.platform == 'win32':
        short_filename = '\\'.join(frame.filename.strip().split('\\')[-2:])
    else:
        short_filename = '/'.join(frame.filename.strip().split('/')[-2:])

    datetime_str = datetime.now().isoformat()

    for line in lines:
        log_line = f'{level.name}'
        log_line += f'|{datetime_str}|{short_filename}'
        log_line += f':L{frame.lineno}|{frame.function}|{line}'

        if level is LogLevel.CRITICAL:
            LOGGER.critical(log_line)
        elif level is LogLevel.ERROR:
            LOGGER.error(log_line)
        elif level is LogLevel.WARNING:
            LOGGER.warning(log_line)
        elif level is LogLevel.INFO:
            LOGGER.info(log_line)
        elif level is LogLevel.DEBUG:
            LOGGER.info(log_line)
