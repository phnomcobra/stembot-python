"""key command — remotely manage cryptographic keys on an agent."""
import time

import click

from stembot.cli.utils import poll_ticket
from stembot.executor.agent import AgentClient
from stembot.models.config import CONFIG
from stembot.models.control import ControlFormTicket, CreateUserKey


@click.command(name='set-user-key')
@click.argument('dst_agtuuid', required=True)
@click.argument('objuuid', required=True)
@click.argument('passphrase', required=True)
@click.option('--agtuuid', type=str, default=None, help='Agent UUID to associate with the new user key')
@click.option('-d', '--delay', type=int, default=None, help='Delay making user key request for n number of seconds')
@click.option('-t', '--timeout', type=int, default=15, help='Timeout in seconds (default: 15)')
def set_user_key(dst_agtuuid: str, objuuid: str, passphrase: str, agtuuid: str | None, delay: int | None, timeout: int):
    """Remotely set a user key on an agent.

    Sends a CreateUserKey control form wrapped in a ControlFormTicket to the
    destination agent, instructing it to derive and store a passphrase-based
    user key.

    Args:
        dst_agtuuid: UUID of the agent that should create the user key
        objuuid: UUID to identify the new user key
        passphrase: Shared passphrase used to derive the user key
        agtuuid: UUID of the agent to associate with the new user key
        delay: Delay making user key request for n number of seconds
        timeout: Maximum seconds to wait for the ticket to be serviced (default: 15)

    Displays:
        - Success confirmation, or any ticket/form error encountered
    """
    click.echo(f"Setting user key '{objuuid}' on agent: {dst_agtuuid}")

    if delay:
        click.echo(f"Waiting {delay} seconds before creating user key...")
        time.sleep(delay)

    client = AgentClient(url=CONFIG.client_control_url)
    form   = CreateUserKey(objuuid=objuuid, passphrase=passphrase, agtuuid=agtuuid)
    ticket = client.send_control_form(ControlFormTicket(dst=dst_agtuuid, form=form))
    ticket = poll_ticket(ticket, client, timeout)

    if ticket.service_time is None:
        click.echo("User key ticket never serviced!", err=True)
        return

    if ticket.error:
        click.echo(ticket.error, err=True)
        return

    if ticket.form.error:
        click.echo(ticket.form.error, err=True)
        return

    click.echo(click.style(f"✓ User key '{objuuid}' set on agent {dst_agtuuid}", fg='green'))
