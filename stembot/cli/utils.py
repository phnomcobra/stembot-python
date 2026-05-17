"""Shared utilities for the CLI."""
import time

from stembot.enums import ControlFormType
from stembot.executor.agent import AgentClient
from stembot.models.control import CheckTicket, CloseTicket, ControlFormTicket


KB = 1024
MB = 1024 * 1024
GB = 1024 * 1024 * 1024


def format_bytes(num_bytes: int | float) -> str:
    """Convert bytes to human-readable format (B, KB, MB, or GB).

    Args:
        num_bytes: Number of bytes to format

    Returns:
        Formatted string with appropriate unit
    """
    num_bytes = float(num_bytes)
    # pylint: disable=too-many-branches, too-many-return-statements
    if num_bytes < KB:
        return f"{num_bytes:.0f} B"
    if num_bytes < MB:
        return f"{num_bytes / KB:.1f} KB"
    if num_bytes < GB:
        return f"{num_bytes / MB:.1f} MB"
    return f"{num_bytes / GB:.1f} GB"


def format_bandwidth(bytes_per_second: int | float) -> str:
    """Convert bytes per second to human-readable format (B/s, KB/s, MB/s, or GB/s).

    Args:
        bytes_per_second: Transfer rate in bytes per second

    Returns:
        Formatted string with appropriate unit
    """
    bytes_per_second = float(bytes_per_second)
    # pylint: disable=too-many-branches, too-many-return-statements
    if bytes_per_second < KB:
        return f"{bytes_per_second:.0f} B/s"
    if bytes_per_second < MB:
        return f"{bytes_per_second / KB:.1f} KB/s"
    if bytes_per_second < GB:
        return f"{bytes_per_second / MB:.1f} MB/s"
    return f"{bytes_per_second / GB:.1f} GB/s"


def poll_ticket(ticket: ControlFormTicket, client: AgentClient, timeout: int) -> ControlFormTicket:
    """Poll a ticket until it is serviced or timeout is reached.

    If serviced, updates the ticket by sending a READ_TICKET request.
    Exponential backoff is used for polling intervals,
    starting at 1 second and doubling each time up to the timeout.
    Ticket is closed after polling regardless of outcome.

    Args:
        ticket: ControlFormTicket to poll
        client: AgentClient to use for sending check requests
        timeout: Maximum seconds to wait for the ticket to be serviced

    Returns:
        Updated ControlFormTicket with service_time if serviced, or original ticket if timed out
    """
    it = time.time()
    check = CheckTicket(tckuuid=ticket.tckuuid, create_time=ticket.create_time)
    check = client.send_control_form(check)
    backoff = 1
    while check.service_time is None and time.time() - it < timeout:
        time.sleep(backoff)
        backoff = min(backoff * 2, timeout - (time.time() - it))
        check = client.send_control_form(check)

    if check.service_time is not None:
        ticket.type = ControlFormType.READ_TICKET
        ticket = client.send_control_form(ticket)

    client.send_control_form(CloseTicket(tckuuid=ticket.tckuuid))

    return ticket
