"""test command — generate a synthetic unittest module to exercise agents end-to-end."""
import unittest

import click

from stembot.cli.utils import poll_ticket
from stembot.executor.agent import AgentClient
from stembot.executor.file import load_form_from_bytes
from stembot.models.config import CONFIG
from stembot.models.control import (
    ControlFormTicket, CreateUserKey, GetConfig, GetKeyMetadata, GetPeers, GetRoutes, LoadFile, SyncProcess,
)

client = AgentClient(url=CONFIG.client_control_url)

write_file = load_form_from_bytes(data=b'ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890')
write_file.path = 'test.txt'

TICKET_FORMS = [
    (write_file, False),
    (GetPeers(), False),
    (GetRoutes(), False),
    (GetConfig(), False),
    (GetKeyMetadata(), False),
    (CreateUserKey(agtuuid='test', objuuid='test', passphrase='test'), False),
    (SyncProcess(command='ls /'), False),
    (SyncProcess(command=['bad', 'command']), True),
    (LoadFile(path='test.txt'), False),
    (LoadFile(path='test_bad.txt'), True)
]


class TestDeployment(unittest.TestCase):
    pass


def test_form(ticket, expect_failure, timeout, verbose=False, print_on_failure=False):
    """Assert that a control form ticket was serviced."""
    ticket = poll_ticket(ticket, client, timeout)

    if verbose:
        click.echo(ticket.model_dump_json(indent=4))

    try:
        assert ticket.service_time is not None, f"Ticket was not serviced by {ticket.dst}"

        if not expect_failure:
            assert ticket.error is None, f"Ticket error from {ticket.dst}: {ticket.error}"
            assert ticket.form.error is None, f"Form error from {ticket.dst}: {ticket.form.error}"
    except AssertionError:
        if print_on_failure and not verbose:
            click.echo(ticket.model_dump_json(indent=4))
        raise


def create_test_method(index, ticket, expect_failure, timeout, verbose=False, print_on_failure=False):
    """Factory function to create individual test methods for each form."""
    # Send the ticket to the agent before creating the test method
    ticket = client.send_control_form(ticket)
    def test_method(_self):
        test_form(ticket, expect_failure, timeout, verbose, print_on_failure)
    test_method.__name__ = f'test_{ticket.form.type}_to_{ticket.dst}_i{index}'.lower()
    return test_method


@click.command(name='test')
@click.argument('destinations', required=True)
@click.argument('timeout', required=False, type=int, default=15)
@click.option('-v', '--verbose', is_flag=True, help='Pretty print every ticket before asserting')
@click.option('-f', '--print-on-failure', is_flag=True, help='Pretty print tickets that fail an assertion')
def test(destinations: str, timeout: int = 15, verbose: bool = False, print_on_failure: bool = False):
    """Generate and run a synthetic unittest suite that exercises control forms against agents.

    Builds and executes a unittest suite that sends each form in TICKET_FORMS (file
    transfer, peer/route/config/key queries, user key creation, and process
    execution, including a deliberate failure path) as a ControlFormTicket to
    every destination agent. Every test polls its ticket to completion and
    asserts it was serviced; unless the form is exercising a known failure path,
    it also asserts neither the ticket nor the control form set an error.

    Args:
        destinations: Comma-delimited list of destination agent UUIDs to test against
        timeout: Maximum seconds to wait for each ticket to be serviced (default: 15)
        verbose: Pretty print every ticket's JSON before its asserts are evaluated
        print_on_failure: Pretty print a ticket's JSON only when one of its asserts fails

    Displays:
        - Standard unittest output for each generated test, plus a final summary
    """
    destinations = [dst.strip() for dst in destinations.split(',') if dst.strip()]

    if not destinations:
        raise click.UsageError('No destinations provided')

    forms = []
    for dst in destinations:
        for form, expect_failure in TICKET_FORMS:
            forms.append((ControlFormTicket(dst=dst, form=form, tracing=True), expect_failure))

    for index, (ticket, expect_failure) in enumerate(forms):
        test_fn = create_test_method(index, ticket, expect_failure, timeout, verbose, print_on_failure)
        setattr(TestDeployment, test_fn.__name__, test_fn)

    suite  = unittest.TestLoader().loadTestsFromTestCase(TestDeployment)
    result = unittest.TextTestRunner(verbosity=2).run(suite)

    raise SystemExit(0 if result.wasSuccessful() else 1)
