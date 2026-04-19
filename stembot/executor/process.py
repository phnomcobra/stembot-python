"""Subprocess execution with timeout enforcement and output capture.

Provides synchronous subprocess execution with automatic timeout management.
Commands can be executed in shell mode (string) or non-shell mode (list).
Stdout and stderr are captured and stored in the SyncProcess form along with
return code and elapsed execution time.

Key features:
- Timeout-based process termination via timer-based kill mechanism
- Automatic elapsed time measurement
- Support for both shell and non-shell command execution
- Complete stdout and stderr capture
- Integration with control form lifecycle
"""

from subprocess import Popen, PIPE
from threading import Timer
from time import time

from stembot.models.control import SyncProcess

def sync_process(form: SyncProcess) -> SyncProcess:
    """Execute a subprocess with timeout enforcement and output capture.

    Executes a command specified in the SyncProcess form using Popen. The command
    can be a list (non-shell execution) or string (shell execution). A timer-based
    timeout mechanism will forcefully kill the process if execution exceeds the
    specified timeout duration.

    Stdout and stderr are captured asynchronously during process execution. The
    nested kill_process function is registered with the timer to terminate the
    process on timeout.

    Execution time is measured from start to completion (including timeout
    cancellation cleanup).

    Args:
        form: A SyncProcess form containing:
            - command: Command to execute (list for shell=False, str for shell=True)
            - timeout: Maximum execution time in seconds before forced termination

    Returns:
        The same SyncProcess form with populated fields:
        - stdout: Decoded standard output as string
        - stderr: Decoded standard error as string
        - status: Process return code (exit status)
        - start_time: Unix timestamp when execution began
        - elapsed_time: Total elapsed time from start to completion in seconds

    Note:
        The timeout timer is always cancelled in a finally block to ensure
        cleanup even if the process completes before the timeout.
    """
    if isinstance(form.command, list):
        shell = False
    else:
        shell = True

    process = Popen(form.command, stdout=PIPE, stderr=PIPE, shell=shell)

    def kill_process(p: Popen) -> None:
        """Terminate a process by sending SIGKILL.

        Args:
            p: The Popen process object to kill.
        """
        p.kill()

    timer = Timer(form.timeout, kill_process, args=(process,))

    try:
        timer.start()
        form.start_time = time()
        process_output_buffer, process_stderr_buffer = process.communicate()
    finally:
        form.elapsed_time = time() - form.start_time
        timer.cancel()

    form.stdout = process_output_buffer.decode()
    form.stderr = process_stderr_buffer.decode()
    form.status = process.returncode

    return form
