#!/usr/bin/python3
"""This test script is designed to validate the end-to-end functionality of the Stembot system by sending
A variety of control forms to multiple agents and verifying that they are processed correctly. This test suite
uses components from stembot-python to test components in stembot-rust, ensuring that the entire system is working
as expected and that protocol compatibility is maintained between the Python and Rust components. This test does
not automate startup of the system, so the system should be started manually from another project
(e.g. with `docker-compose up`) before running this test.

Destinations and agent configuration settings will need to be matched between this test and the agents actually running.
"""
from time import sleep, time
import unittest

from devtools import pprint

from stembot.executor.agent import AgentClient
from stembot.executor.file import load_form_from_bytes
from stembot.dao import kvstore
from stembot.models.control import GetConfig, GetPeers, ControlFormTicket, ControlFormType, GetRoutes, LoadFile, SyncProcess

client = AgentClient(url=kvstore.get('client_control_url'))

write_file = load_form_from_bytes(data=b'ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890')
write_file.path = '/tmp/test.txt'

ticket_forms = [
    write_file,
    GetPeers(),
    GetRoutes(),
    SyncProcess(command='ls /'),
    SyncProcess(command=['bad', 'command']),
    LoadFile(path='/tmp/test.txt'),
    LoadFile(path='/etc/hosts'),
    SyncProcess(command=['find', '/etc', '-type', 'f', '-name', '*.service']),
    SyncProcess(command='hostname'),
    GetConfig()
]

# These correspond to the agent UUIDs configured in docker-compose.yml for each container.
# The test will send each form to each agent to verify that the system is working end-to-end.
destinations = ['r1', 'r2', 'r3', 'r4', 'r5']

forms = []
for dst in destinations:
    for form in ticket_forms:
        forms.append(ControlFormTicket(dst=dst, form=form, tracing=True))

class TestDeployment(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for form in forms:
            form = client.send_control_form(form)

    @staticmethod
    def _test_form(form: ControlFormTicket):
        """Test a single form by polling for completion.

        Args:
            form: The form to test
        """
        form.type = ControlFormType.READ_TICKET
        init_time = time()
        while time() - init_time < 30:
            form = client.send_control_form(form)
            ticket = ControlFormTicket(**form.model_dump())
            if ticket.service_time:
                break
            sleep(1)

        pprint(ticket)

        form.type = ControlFormType.CLOSE_TICKET
        client.send_control_form(form)

        assert ticket.service_time is not None, "Ticket was not serviced."


def create_test_method(index: int, form: ControlFormTicket) -> callable:
    """Factory function to create individual test methods for each form."""
    def _test_method(self):
        self._test_form(form)

    _test_method.__name__ = f'test_{form.form.type}_to_{form.dst}_i{index}'.lower()
    return _test_method


for index, form in enumerate(forms):
    _test_fn = create_test_method(index, form)
    setattr(TestDeployment, _test_fn.__name__, _test_fn)
