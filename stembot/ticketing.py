#!/usr/bin/python3
from time import time
from threading import Thread
from typing import Optional

from stembot.dao import Collection
from stembot import logging
from stembot.scheduling import register_timer
from stembot.types.network import NetworkTicket, TicketTraceResponse
from stembot.types.control import ControlFormTicket, ControlFormType, Hop

ASYNC_TICKET_TIMEOUT = 3600

def read_ticket(control_form_ticket: ControlFormTicket) -> Optional[ControlFormTicket]:
    tickets = Collection('tickets', in_memory=True, model=ControlFormTicket)
    for ticket in tickets.find(tckuuid=control_form_ticket.tckuuid):
        ticket.object.type = ControlFormType.READ_TICKET
        return ticket.object


def close_ticket(control_form_ticket: ControlFormTicket):
    tickets = Collection('tickets', in_memory=True, model=ControlFormTicket)
    for ticket in tickets.find(tckuuid=control_form_ticket.tckuuid):
        ticket.destroy()


def service_ticket(network_ticket: NetworkTicket):
    tickets = Collection('tickets', in_memory=True, model=ControlFormTicket)
    for ticket in tickets.find(tckuuid=network_ticket.tckuuid):
        ticket.object.form = network_ticket.form
        ticket.object.service_time = time()
        ticket.set()


def trace_ticket(ticket_trace: TicketTraceResponse):
    tickets = Collection('tickets', in_memory=True, model=ControlFormTicket)
    hop = Hop(hop_time=ticket_trace.hop_time, agtuuid=ticket_trace.src)
    for ticket in tickets.find(tckuuid=ticket_trace.tckuuid):
        ticket.object.hops.append(hop)
        ticket.set()


def worker():
    cutoff = time() - ASYNC_TICKET_TIMEOUT
    tickets = Collection('tickets', in_memory=True, model=ControlFormTicket)
    for ticket in tickets.find(create_time=f'$lt:{cutoff}'):
        logging.warning(f'Expiring ticket {ticket.object.tckuuid}')
        logging.debug(ticket.object)
        ticket.destroy()

    register_timer(
        name='ticket_worker',
        target=worker,
        timeout=60
    ).start()


collection = Collection('tickets', in_memory=True, model=ControlFormTicket)
collection.create_attribute('create_time', "/create_time")
collection.create_attribute('tckuuid', "/tckuuid")

Thread(target=worker).start()
