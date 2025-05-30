#!/usr/bin/python3
from time import time
from threading import Thread

from stembot.dao import Collection
from stembot.audit import logging
from stembot.executor.timers import register_timer
from stembot.types.network import NetworkTicket
from stembot.types.control import ControlFormTicket

ASYNC_TICKET_TIMEOUT = 3600

def read_ticket(control_form_ticket: ControlFormTicket):
    tickets = Collection('tickets', in_memory=True, model=ControlFormTicket)
    for ticket in tickets.find(tckuuid=control_form_ticket.tckuuid):
        return ticket.object


def service_ticket(network_ticket: NetworkTicket):
    tickets = Collection('tickets', in_memory=True, model=ControlFormTicket)
    for ticket in tickets.find(tckuuid=network_ticket.tckuuid):
        ticket.object.form = network_ticket.form
        ticket.object.service_time = time()
        ticket.set()
        logging.debug(ticket.object)


def worker():
    cutoff = time() - ASYNC_TICKET_TIMEOUT
    tickets = Collection('tickets', in_memory=True, model=ControlFormTicket)
    for ticket in tickets.find(create_time=f'$lt:{cutoff}'):
        logging.info(f'Expiring ticket {ticket.object.tckuuid}')
        ticket.destroy()

    register_timer(
        name='ticket_worker',
        target=worker,
        timeout=ASYNC_TICKET_TIMEOUT
    ).start()


collection = Collection('tickets', in_memory=True, model=ControlFormTicket)
collection.create_attribute('create_time', "/create_time")
collection.create_attribute('tckuuid', "/tckuuid")

Thread(target=worker).start()
