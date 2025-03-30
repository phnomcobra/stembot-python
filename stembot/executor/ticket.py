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
    for item in Collection('tickets', in_memory=True).find(tckuuid=control_form_ticket.tckuuid):
        try:
            control_form_ticket = ControlFormTicket.model_validate(item.object)
        except: # pylint: disable=bare-except
            logging.exception(f'Encountered exception with ticket {control_form_ticket.tckuuid}')
            continue
        return control_form_ticket


def service_ticket(network_ticket: NetworkTicket):
    for item in Collection('tickets', in_memory=True).find(tckuuid=network_ticket.tckuuid):
        try:
            control_form_ticket = ControlFormTicket.model_validate(item.object)
        except: # pylint: disable=bare-except
            logging.exception(f'Encountered exception with ticket {network_ticket.tckuuid}')
            continue
        control_form_ticket.form = network_ticket.form
        control_form_ticket.service_time = time()
        item.object = control_form_ticket
        item.set()


def worker():
    for item in Collection('tickets', in_memory=True).find():
        try:
            ticket = ControlFormTicket.model_validate(item.object)
            assert time() - ticket.create_time < ASYNC_TICKET_TIMEOUT
        except AssertionError:
            logging.info(f'Expiring ticket {ticket.tckuuid}')
            item.destroy()
        except: # pylint: disable=bare-except
            logging.exception('Malformed ticket encountered')
            item.destroy()

    register_timer(
        name='ticket_worker',
        target=worker,
        timeout=ASYNC_TICKET_TIMEOUT
    ).start()

Thread(target=worker).start()
