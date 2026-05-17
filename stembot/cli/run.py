"""run command — execute a command on a remote agent."""
import sys

import click

from stembot.cli.utils import poll_ticket
from stembot.executor.agent import AgentClient
from stembot.models.config import CONFIG
from stembot.models.control import ControlFormTicket, SyncProcess


@click.command()
@click.argument('agtuuid', required=True)
@click.argument('command', required=True)
@click.option('-t', '--timeout', type=int, default=15, help='Timeout in seconds (default: 15)')
def run(agtuuid: str, command: str, timeout: int):
    """Execute a command on a remote agent.

    Sends a command to a remote agent for execution via subprocess.
    Polls for completion with timeout and displays stdout/stderr output.
    Exits with the remote process's return code.

    Args:
        agtuuid: UUID of the agent to execute the command on
        command: Command to execute (string or shell command)
        timeout: Maximum seconds to wait for execution (default: 15)

    Displays:
        - Standard output from the remote process
        - Standard error messages if any

    Exits:
        With the remote process's return code (0 for success, non-zero for error)
        or exit code 1 if ticket service times out or errors occur.

    Note:
        Uses SyncProcess with timeout enforcement. The poll timeout is
        2x the specified timeout to allow process execution time plus polling.
    """
    client       = AgentClient(url=CONFIG.client_control_url)
    sync_process = SyncProcess(command=command, timeout=timeout)
    ticket       = client.send_control_form(ControlFormTicket(dst=agtuuid, form=sync_process))
    ticket       = poll_ticket(ticket, client, timeout * 2)

    if stdout := ticket.form.stdout:
        click.echo(stdout.strip())

    if stderr := ticket.form.stderr:
        click.echo(stderr.strip(), err=True)

    if status := ticket.form.status:
        sys.exit(status)

    if error := ticket.error:
        click.echo(error.strip(), err=True)
        sys.exit(1)
