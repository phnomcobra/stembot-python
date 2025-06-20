#!/usr/bin/python3
from time import sleep, time

from devtools import pprint

from stembot.executor.agent import ControlFormClient
from stembot.executor.file import load_form_from_bytes
from stembot.dao import kvstore
from stembot.types.control import GetPeers, ControlFormTicket, ControlFormType, GetRoutes, LoadFile, SyncProcess

client = ControlFormClient(
    url='http://127.0.0.1:8080/control',
    secret_digest=kvstore.get('secret_digest')
)


write_file = load_form_from_bytes(data=b'ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890')
write_file.path = '/tmp/test.txt'

inner_forms = [
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

forms = []

for form in inner_forms:
    ticket = ControlFormTicket(dst='c5', form=form, tracing=True)
    forms.append(client.send_control_form(ticket))

for form in forms:
    form.type = ControlFormType.READ_TICKET
    init_time = time()
    while time() - init_time < 15:
        form = client.send_control_form(form)
        ticket = ControlFormTicket(**form.model_dump())
        if ticket.service_time:
            break
        sleep(1)
    pprint(ticket)

for form in forms:
    form.type = ControlFormType.CLOSE_TICKET
    client.send_control_form(form)

