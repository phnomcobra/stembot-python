#!/usr/bin/python3
from time import sleep, time
import unittest

from devtools import pprint

from stembot.executor.agent import ControlFormClient
from stembot.executor.file import load_form_from_bytes
from stembot.dao import kvstore
from stembot.models.control import ControlForm, GetPeers, ControlFormTicket, ControlFormType, GetRoutes, LoadFile, SyncProcess

client = ControlFormClient(url=kvstore.get('client_control_url'))

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
    SyncProcess(command='hostname')
]

destinations = ['c1', 'c2', 'c3', 'c4', 'c5']

forms = []
for dst in destinations:
    for form in ticket_forms:
        forms.append(client.send_control_form(ControlFormTicket(dst=dst, form=form, tracing=True)))


class TestDeployment(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        """Clean up once after all tests in this class."""
        for form in forms:
            form.type = ControlFormType.CLOSE_TICKET
            client.send_control_form(form)

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

        pprint(form)

        assert ticket.service_time is not None


def create_test_method(index: int, form: ControlForm) -> callable:
    """Factory function to create individual test methods for each form."""
    def _test_method(self):
        self._test_form(form)

    _test_method.__name__ = f'test_{form.form["type"]}_to_{form.dst}_i{index}'
    return _test_method


for index, form in enumerate(forms):
    _test_fn = create_test_method(index, form)
    setattr(TestDeployment, _test_fn.__name__, _test_fn)
