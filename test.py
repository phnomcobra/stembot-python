#!/usr/bin/python3
from time import sleep, time

from devtools import pprint

from stembot.adapter.agent import ControlFormClient
from stembot.dao import kvstore
from stembot.types.control import GetPeers, ControlFormTicket, ControlFormType, GetRoutes, SyncProcess

client = ControlFormClient(
    url='http://127.0.0.1:8080/control',
    secret_digest=kvstore.get('secret_digest')
)

forms = []

for form in [GetPeers(), GetRoutes(), SyncProcess(command='ls /'), SyncProcess(command=['bad', 'command'])]:
    ticket = ControlFormTicket(dst='c5', form=form, tracing=True)
    forms.append(client.send_control_form(ticket))

for form in forms:
    form.type = ControlFormType.READ_TICKET

    init_time = time()
    sleep_time = 0.2
    while time() - init_time < 60.0:
        form = client.send_control_form(form)
        ticket = ControlFormTicket(**form.model_dump())
        if ticket.service_time:
            break
        sleep(sleep_time)
        sleep_time = sleep_time * 2.0

    pprint(ticket)

for form in forms:
    form.type = ControlFormType.CLOSE_TICKET
    client.send_control_form(form)
