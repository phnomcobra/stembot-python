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

peers_form = ControlFormTicket(dst='c1', form=GetPeers())
peers_form = client.send_control_form(peers_form)

sleep(5)

peers_form.type = ControlFormType.READ_TICKET
pprint(client.send_control_form(peers_form))
