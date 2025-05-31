#!/usr/bin/python3
from time import sleep

from devtools import pprint

from stembot.adapter.agent import ControlFormClient
from stembot.model import kvstore
from stembot.types.control import GetPeers, ControlFormTicket, ControlFormType

client = ControlFormClient(
    url='http://127.0.0.1:8080/control',
    secret_digest=kvstore.get('secret_digest')
)

ticket = ControlFormTicket(dst='c3', form=GetPeers())
form = client.send_control_form(ticket)

sleep(4)

form.type = ControlFormType.READ_TICKET
form = client.send_control_form(form)
ticket = ControlFormTicket(**form.model_dump())

pprint(ticket)
