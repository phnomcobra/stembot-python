"""stat command — retrieve and display agent statistics."""
import datetime
import time

import click

from stembot.enums import ControlFormType
from stembot.executor.agent import AgentClient
from stembot.models.config import CONFIG
from stembot.models.control import CheckTicket, CloseTicket, ControlFormTicket, GetConfig, GetPeers, GetRoutes

# pylint: disable=too-many-statements, too-many-locals, too-many-branches
@click.command()
@click.argument('agtuuid', required=True)
@click.option('-t', '--timeout', type=int, default=15, help='Timeout in seconds (default: 15)')
def stat(agtuuid: str, timeout: int):
    """Retrieve and display agent statistics.

    Queries an agent for its current configuration, network peers, routes,
    and hop information (multi-hop route trace). Uses ticket-based polling
    with timeout to wait for responses.

    Args:
        agtuuid: UUID of the agent to query
        timeout: Maximum seconds to wait for each response (default: 15)

    Displays:
        - Elapsed time for the entire query operation
        - Configuration dictionary
        - List of known peers with URLs and polling status
        - List of routes with destination UUIDs, gateway UUIDs, and weights
        - Network hops showing the route trace with timestamps

    Note:
        Sends ControlFormTicket requests with tracing enabled for the
        config query to capture multi-hop route information.
    """
    client = AgentClient(url=CONFIG.client_control_url)

    config_form = client.send_control_form(ControlFormTicket(dst=agtuuid, form=GetConfig(), tracing=True))
    peers_form  = client.send_control_form(ControlFormTicket(dst=agtuuid, form=GetPeers()))
    routes_form = client.send_control_form(ControlFormTicket(dst=agtuuid, form=GetRoutes()))

    it = time.time()
    check = CheckTicket(tckuuid=config_form.tckuuid, create_time=config_form.create_time)
    check = client.send_control_form(check)
    while check.service_time is None and time.time() - it < timeout:
        time.sleep(1)
        check = client.send_control_form(check)

    if check.service_time and check.create_time:
        et = check.service_time - check.create_time
    else:
        et = time.time() - it

    if check.service_time is not None:
        config_form.type = ControlFormType.READ_TICKET
        config_form = client.send_control_form(config_form)

    client.send_control_form(CloseTicket(tckuuid=config_form.tckuuid))

    it = time.time()
    check = CheckTicket(tckuuid=peers_form.tckuuid, create_time=peers_form.create_time)
    check = client.send_control_form(check)
    while check.service_time is None and time.time() - it < timeout:
        time.sleep(1)
        check = client.send_control_form(check)

    if check.service_time is not None:
        peers_form.type = ControlFormType.READ_TICKET
        peers_form = client.send_control_form(peers_form)

    client.send_control_form(CloseTicket(tckuuid=peers_form.tckuuid))

    it = time.time()
    check = CheckTicket(tckuuid=routes_form.tckuuid, create_time=routes_form.create_time)
    check = client.send_control_form(check)
    while check.service_time is None and time.time() - it < timeout:
        time.sleep(1)
        check = client.send_control_form(check)

    if check.service_time is not None:
        routes_form.type = ControlFormType.READ_TICKET
        routes_form = client.send_control_form(routes_form)

    client.send_control_form(CloseTicket(tckuuid=routes_form.tckuuid))

    for form in (config_form, peers_form, routes_form):
        if error := form.error:
            click.echo(error, err=True)

    config = config_form.form.config
    peers  = peers_form.form.peers
    routes = routes_form.form.routes

    # Pretty print the results
    click.echo()
    click.echo("=" * 70)
    click.echo(f"Agent Statistics: {agtuuid}")
    click.echo("=" * 70)

    # Display elapsed time
    click.echo()
    click.echo(click.style("⏱  Elapsed Time", fg='cyan', bold=True))
    click.echo(f"   {et:.3f} seconds")

    # Display configuration
    if config:
        click.echo()
        click.echo(click.style("⚙️  Configuration", fg='cyan', bold=True))
        for key, value in config.items():
            # Truncate long values for display
            display_value = str(value)[:60] + "..." if len(str(value)) > 60 else value
            click.echo(f"   {key:.<36} {display_value}")
    else:
        click.echo()
        click.echo(click.style("⚙️  Configuration", fg='cyan', bold=True))
        click.echo("   (No configuration data received)")

    # Display peers
    click.echo()
    click.echo(click.style("👥 Network Peers", fg='cyan', bold=True))
    for peer in peers:
        peer_display = (
            f"   {peer.agtuuid:.<36} "
            f"Polling: {str(peer.polling): <5} "
            f"URL: {peer.url}"
        )
        click.echo(peer_display)

    # Display routes
    click.echo()
    click.echo(click.style("🛣️  Network Routes", fg='cyan', bold=True))
    for route in sorted(routes, key=lambda r: r.agtuuid):
        click.echo(f"   {route.agtuuid:.<36} → {route.gtwuuid:.<36} (weight: {route.weight})")

    # Display hops
    click.echo()
    click.echo(click.style("🔗 Network Hops", fg='cyan', bold=True))

    for idx, hop in enumerate(sorted(config_form.hops, key=lambda h: h.hop_time), 1):
        # Format hop time nicely
        if isinstance(hop.hop_time, (int, float)):
            hop_time_dt = datetime.datetime.fromtimestamp(hop.hop_time)
            hop_display = f"   [{idx}] {hop.agtuuid:.<36} {hop.type_str:.<20} @ {hop_time_dt.isoformat()}"
        else:
            hop_display = f"   [{idx}] {hop.agtuuid:.<36} {hop.type_str}"

        click.echo(hop_display)

    click.echo()
    click.echo("=" * 70)
    click.echo()
