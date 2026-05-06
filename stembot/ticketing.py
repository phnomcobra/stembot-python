"""Ticket management for routed control forms and inter-agent communication.

Manages the lifecycle of control form tickets that are routed through the network
to other agents. Tracks ticket creation, servicing, completion, and trace information
for multi-hop message delivery. Automatically expires old tickets and traces based on
configured timeout values.

Tickets enable reliable request-response patterns for control forms that must traverse
multiple hops through the network. Each ticket has a unique UUID and tracks its path
via hop information, allowing the originating agent to trace the route taken.

Key features:
- Thread-safe ticket lifecycle management with synchronization
- Deduplication of trace messages for multi-hop delivery
- Automatic expiration of old tickets and traces
- Hop tracking for route tracing
"""

from time import time
import logging

from stembot.dao import Collection
from stembot.models.config import CONFIG
from stembot.scheduling import scheduled
from stembot.models.network import NetworkMessageType, NetworkTicket, TicketTraceResponse
from stembot.models.control import ControlFormTicket, ControlFormType


def read_ticket(control_form_ticket: ControlFormTicket) -> ControlFormTicket | None:
    """Retrieve a ticket by UUID and return its current state.

    Looks up a ticket in the in-memory ticket collection by its UUID and returns
    the ticket object with its current form and service time. Sets the ticket type
    to READ_TICKET to indicate it was read.

    Args:
        control_form_ticket: A ticket object containing the tckuuid to look up.

    Returns:
        The ControlFormTicket object if found, or None if not found.
    """
    tickets = Collection[ControlFormTicket]('tickets')
    traces  = Collection[TicketTraceResponse]('traces')
    for ticket in tickets.find(tckuuid=control_form_ticket.tckuuid):
        if ticket.object.tracing:
            ticket.object.hops = [
                trace.object.hop for trace in traces.find(tckuuid=ticket.object.tckuuid)
            ]
        ticket.object.type = ControlFormType.READ_TICKET
        return ticket.object


def close_ticket(control_form_ticket: ControlFormTicket) -> None:
    """Delete a ticket by UUID from the in-memory ticket collection.

    Removes a completed ticket from the collection, cleaning up its entry and
    hop history. Called after a ticket has been serviced and its results consumed.

    Args:
        control_form_ticket: A ticket object containing the tckuuid to delete.
    """
    Collection[ControlFormTicket]('tickets').pop(tckuuid=control_form_ticket.tckuuid)


def service_ticket(network_ticket: NetworkTicket) -> None:
    """Update a ticket with the serviced control form and service time.

    Records the response from servicing a ticket by updating its contained form
    with the response form and recording the service completion time. Thread-safe
    via the @synchronized decorator.

    Args:
        network_ticket: A network ticket containing the response form and tckuuid.
    """
    tickets = Collection[ControlFormTicket]('tickets')
    for ticket in tickets.find(tckuuid=network_ticket.tckuuid):
        ticket.object.form = network_ticket.form
        ticket.object.service_time = time()
        ticket.commit()


def service_trace(ticket_trace: TicketTraceResponse) -> None:
    """Add hop information to a ticket's trace for route tracking.

    Records a hop in the ticket's travel path by adding hop information (time,
    source agent, and message type) to the ticket's hops list. Used for tracing
    the route a ticket takes through the network. Thread-safe via @synchronized.

    Args:
        ticket_trace: A TicketTraceResponse containing hop details and tckuuid.
    """
    traces = Collection[TicketTraceResponse]('traces')
    traces.upsert_object(ticket_trace)


def dedup_trace(network_ticket: NetworkTicket) -> TicketTraceResponse | None:
    """Deduplicate trace messages for a ticket to prevent infinite loops.

    For tickets with tracing enabled, checks if a trace for this ticket and
    message type already exists. If it does, updates its hop_time and returns None
    (treating it as a duplicate). If not, creates a new trace entry and returns it.
    This prevents duplicate traces from being sent back through the network.

    Args:
        network_ticket: The network ticket to check for existing traces.

    Returns:
        A new TicketTraceResponse if this is the first trace for this ticket/type,
        or None if a trace already exists (indicating a duplicate to be ignored).
    """
    if network_ticket.tracing:
        traces = Collection[TicketTraceResponse]('traces')

        matched_traces = traces.find(
            tckuuid=network_ticket.tckuuid,
            network_ticket_type=network_ticket.type
        )

        if matched_traces:
            for matched_trace in matched_traces:
                matched_trace.object.hop_time = time()
                matched_trace.commit()
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


@scheduled(every_secs=CONFIG.ticket_timeout_secs)
def worker() -> None:
    """Background worker that expires old tickets and traces.

    Periodically removes tickets and traces that have exceeded the configured
    timeout period (ticket_timeout_secs). Reschedules itself to run every 1 second.
    Runs in a background thread to provide continuous cleanup of stale ticket data.
    """
    cutoff = time() - CONFIG.ticket_timeout_secs

    tickets = Collection[ControlFormTicket]('tickets')
    for ticket in tickets.pop(create_time=f'$lt:{cutoff}'):
        logging.warning('Expiring ticket %s:%s', ticket.object.type, ticket.object.tckuuid)

    traces = Collection[TicketTraceResponse]('traces')
    for trace in traces.pop(hop_time=f'$lt:{cutoff}'):
        logging.debug('Expiring trace %s', trace.object.tckuuid)


@scheduled(every_secs=60)
def vacuum_ticket_traces() -> None:
    """Vacuum the ticket trace collection to optimize storage.

    Performs a vacuum operation on the ticket trace collection to reclaim space
    from deleted traces and optimize query performance. Should be run
    periodically to maintain efficient storage of ticket traces.
    """
    Collection[TicketTraceResponse]('traces').vacuum()


@scheduled(every_secs=60)
def vacuum_tickets() -> None:
    """Vacuum the ticket collection to optimize storage.

    Performs a vacuum operation on the ticket collection to reclaim space
    from deleted tickets and optimize query performance. Should be run
    periodically to maintain efficient storage of tickets.
    """
    Collection[ControlFormTicket]('tickets').vacuum()


collection = Collection[TicketTraceResponse]('traces')
collection.create_attribute('tckuuid', "/tckuuid")
collection.create_attribute('hop_time', "/hop_time")
collection.create_attribute('network_ticket_type', "/network_ticket_type")

collection = Collection[ControlFormTicket]('tickets')
collection.create_attribute('create_time', "/create_time")
collection.create_attribute('tckuuid', "/tckuuid")
