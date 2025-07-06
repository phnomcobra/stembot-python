#!/usr/bin/python3
from time import time
from threading import Thread
from typing import Optional

from stembot.dao import Collection
from stembot import logging
from stembot.scheduling import register_timer
from stembot.types.network import NetworkMessageType, NetworkTicket, TicketTraceResponse
from stembot.types.control import ControlFormTicket, ControlFormType, Hop

ASYNC_TICKET_TIMEOUT = 60

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

    hop = Hop(
        hop_time=ticket_trace.hop_time,
        agtuuid=ticket_trace.src,
        type_str=str(ticket_trace.network_ticket_type)
    )

    for ticket in tickets.find(tckuuid=ticket_trace.tckuuid):
        ticket.object.hops.append(hop)
        ticket.set()


def dedup_trace(network_ticket: NetworkTicket) -> Optional[TicketTraceResponse]:
    if network_ticket.tracing:
        traces = Collection('traces', in_memory=True, model=TicketTraceResponse)
        logging.debug(network_ticket.tckuuid)

        matched_traces = traces.find(
            tckuuid=network_ticket.tckuuid,
            network_ticket_type=network_ticket.type
        )

        if matched_traces:
            for matched_trace in matched_traces:
                matched_trace.object.hop_time = time()
                matched_trace.set()
        else:
            trace = TicketTraceResponse(
                dest=(
                    network_ticket.src if network_ticket.type == NetworkMessageType.TICKET_REQUEST
                    else network_ticket.dest
                ),
                tckuuid=network_ticket.tckuuid,
                network_ticket_type=network_ticket.type
            )

            traces.upsert_object(trace)
            return trace
    return None


def worker():
    cutoff = time() - ASYNC_TICKET_TIMEOUT

    tickets = Collection('tickets', in_memory=True, model=ControlFormTicket)
    for ticket in tickets.find(create_time=f'$lt:{cutoff}'):
        logging.warning(f'Expiring ticket {ticket.object.tckuuid}')
        logging.debug(ticket.object)
        ticket.destroy()

    traces = Collection('traces', in_memory=True, model=TicketTraceResponse)
    for trace in traces.find(hop_time=f'$lt:{cutoff}'):
        logging.debug(f'Expiring trace {trace.object.tckuuid}')
        trace.destroy()

    register_timer(
        name='ticket_worker',
        target=worker,
        timeout=1
    ).start()


collection = Collection('traces', in_memory=True, model=TicketTraceResponse)
collection.create_attribute('tckuuid', "/tckuuid")
collection.create_attribute('hop_time', "/hop_time")
collection.create_attribute('network_ticket_type', "/network_ticket_type")


collection = Collection('tickets', in_memory=True, model=ControlFormTicket)
collection.create_attribute('create_time', "/create_time")
collection.create_attribute('tckuuid', "/tckuuid")

Thread(target=worker).start()
