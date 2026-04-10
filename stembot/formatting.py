"""Custom logging formatter for the stembot application.

Provides a formatter that outputs logs in the format:
    LEVEL|DATETIME|FILENAME:LINE|FUNCTION|MESSAGE
"""
import logging
import os
from datetime import datetime

class StemBotFormatter(logging.Formatter):
    """Custom formatter that outputs structured log lines.

    Format: LEVEL|DATETIME|FILENAME:LINE|FUNCTION|MESSAGE
    Example: INFO|2026-03-31 14:23:45.123|server.py:L42|main|Starting server
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record into the stembot log format.

        Args:
            record: The LogRecord to format.

        Returns:
            A formatted log line string.
        """
        # Get the level name in uppercase
        level_name = record.levelname

        # Format the timestamp with milliseconds
        timestamp = datetime.fromtimestamp(record.created)
        datetime_str = timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]

        # Get the short filename (just the filename, not the full path)
        short_filename = os.path.basename(record.pathname)

        # Get the line number
        lineno = record.lineno

        # Get the function name
        function_name = record.funcName

        # Get the message
        message = record.getMessage()

        # Build the log line
        log_line = f'{level_name}'
        log_line += f'|{datetime_str}|{short_filename}'
        log_line += f':L{lineno}|{function_name}|{message}'

        # If there's an exception, append it
        if record.exc_info:
            log_line += '\n' + self.formatException(record.exc_info)

        return log_line
