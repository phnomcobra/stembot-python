"""Online Agent Configuration

Command-line interface for agent control operations using Click.
Supports discovering peers, managing peer connections, listing network topology,
and tracing/pinging agents.

Examples:
    # Discover a peer
    python -m stembot.control discover http://c2:8080/mpi -d 5

    # List all peers
    python -m stembot.control list peers

    # List all routes
    python -m stembot.control list routes

    # Delete a specific agent
    python -m stembot.control delete --agtuuid c2

    # Delete all agents
    python -m stembot.control delete --all

    # Trace an agent (find path to it)
    python -m stembot.control trace c2

    # Ping an agent
    python -m stembot.control ping c2 --continuous
"""
import datetime
import time
import logging

import click
from devtools import pprint

from stembot.enums import ControlFormType
from stembot.executor.agent import ControlFormClient
from stembot.dao import kvstore
from stembot.models.control import ControlFormTicket, DeletePeers, DiscoverPeer, GetConfig, GetPeers, GetRoutes

logger = logging.getLogger(__name__)


@click.group(help='Agent control and network management')
def main():
    """Manage agent connections, discover peers, and manage network topology."""
    pass


@main.command()
@click.argument('peer_url', required=True)
@click.option(
    '-p', '--polling',
    is_flag=True,
    help='Enable polling mode for discovery'
)
@click.option(
    '-d', '--delay',
    type=int,
    default=None,
    help='Delay making discovery request for n number of seconds'
)
@click.option(
    '--ttl',
    type=int,
    default=None,
    help='Time-to-live for the discovery in seconds'
)
def discover(peer_url, polling, delay, ttl):
    """Discover and connect to a peer.

    PEER_URL: URL of the peer to discover (e.g., http://c2:8080/mpi)

    Displays discovery results including:
    - Discovery status and any errors
    - Peer URL and TTL
    - Polling mode status
    """
    if delay:
        click.echo(f"Waiting {delay} seconds before discovery...")
        time.sleep(delay)

    client = ControlFormClient(url=kvstore.get('client_control_url'))
    click.echo(f"Discovering peer: {peer_url}")

    form = client.send_control_form(DiscoverPeer(
        url=peer_url,
        polling=polling,
        ttl=ttl,
    ))

    # Pretty print the discovery result
    click.echo()
    click.echo("=" * 70)
    click.echo("Peer Discovery Result")
    click.echo("=" * 70)

    # Display status
    if form.error:
        click.echo()
        click.echo(click.style("❌ Error", fg='red', bold=True))
        click.echo(f"   {form.error}")
    else:
        click.echo()
        click.echo(click.style("✓ Discovery Successful", fg='green', bold=True))

    # Display discovery details
    click.echo()
    click.echo(click.style("📍 Discovery Details", fg='cyan', bold=True))

    # Peer URL
    click.echo(f"   Peer URL..................... {form.url}")

    # Agent UUID
    if form.agtuuid:
        click.echo(f"   Agent UUID................... {form.agtuuid}")
    else:
        click.echo(f"   Agent UUID................... (not yet assigned)")

    # TTL
    if form.ttl is not None:
        click.echo(f"   TTL (Time-to-Live)........... {form.ttl} seconds")
    else:
        click.echo(f"   TTL (Time-to-Live)........... (not set)")

    # Polling mode
    polling_status = click.style("Enabled", fg='green') if form.polling else click.style("Disabled", fg='yellow')
    click.echo(f"   Polling Mode................. {polling_status}")

    # Additional form details
    click.echo()
    click.echo(click.style("📋 Form Details", fg='cyan', bold=True))

    # Type
    click.echo(f"   Type......................... {form.type.value if hasattr(form.type, 'value') else form.type}")

    # Object UUID
    if form.objuuid:
        click.echo(f"   Object UUID.................. {form.objuuid}")

    # Collection UUID
    if form.coluuid:
        click.echo(f"   Collection UUID.............. {form.coluuid}")

    click.echo()
    click.echo("=" * 70)
    click.echo()


@main.command()
@click.option(
    '--all',
    'delete_all',
    is_flag=True,
    help='Delete all agents'
)
@click.option(
    '--agtuuid',
    type=str,
    default=None,
    help='Delete a specific agent by UUID'
)
def delete(delete_all, agtuuid):
    """Delete one or more peers from the network.

    Use --all to delete all agents, or --agtuuid <UUID> to delete a specific agent.
    """
    client = ControlFormClient(url=kvstore.get('client_control_url'))

    if delete_all:
        click.echo("Deleting all agents...")
        result = client.send_control_form(DeletePeers())
        pprint(result)
    elif agtuuid:
        click.echo(f"Deleting agent: {agtuuid}")
        result = client.send_control_form(DeletePeers(agtuuids=[agtuuid]))
        pprint(result)
    else:
        click.echo("Error: Use --all or --agtuuid <UUID>", err=True)


@main.command()
@click.argument('agtuuid', required=True)
@click.option(
    '-t', '--timeout',
    type=int,
    default=15,
    help='Timeout in seconds (default: 15)'
)
def stat(agtuuid, timeout):
    client = ControlFormClient(url=kvstore.get('client_control_url'))

    config_form = client.send_control_form(ControlFormTicket(dst=agtuuid, form=GetConfig(), tracing=True))
    peers_form  = client.send_control_form(ControlFormTicket(dst=agtuuid, form=GetPeers()))
    routes_form = client.send_control_form(ControlFormTicket(dst=agtuuid, form=GetRoutes()))

    config_form.type = ControlFormType.READ_TICKET
    it = time.time()
    while time.time() - it < timeout and not config_form.service_time:
        config_form = client.send_control_form(config_form)
        time.sleep(1)

    if config_form.service_time and config_form.create_time:
        et = config_form.service_time - config_form.create_time
    else:
        et = time.time() - it

    config_form.type = ControlFormType.CLOSE_TICKET
    client.send_control_form(config_form)

    peers_form.type = ControlFormType.READ_TICKET
    it = time.time()
    while time.time() - it < timeout and not peers_form.service_time:
        peers_form = client.send_control_form(peers_form)
        time.sleep(1)

    peers_form.type = ControlFormType.CLOSE_TICKET
    client.send_control_form(peers_form)

    routes_form.type = ControlFormType.READ_TICKET
    it = time.time()
    while time.time() - it < timeout and not routes_form.service_time:
        routes_form = client.send_control_form(routes_form)
        time.sleep(1)

    routes_form.type = ControlFormType.CLOSE_TICKET
    client.send_control_form(routes_form)

    hops   = config_form.hops                   if config_form.hops else []
    config = config_form.form.get('config', {}) if config_form.form else {}
    peers  = peers_form.form.get('peers', [])   if peers_form.form  else []
    routes = routes_form.form.get('routes', []) if routes_form.form else []

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
        if isinstance(config, dict):
            for key, value in config.items():
                # Truncate long values for display
                display_value = str(value)[:60] + "..." if len(str(value)) > 60 else value
                click.echo(f"   {key:.<36} {display_value}")
        else:
            click.echo(f"   {config}")
    else:
        click.echo()
        click.echo(click.style("⚙️  Configuration", fg='cyan', bold=True))
        click.echo("   (No configuration data received)")

    # Display peers
    click.echo()
    click.echo(click.style("👥 Network Peers", fg='cyan', bold=True))
    if peers:
        for peer in peers:
            agtuuid_peer = peer.get('agtuuid', 'unknown')
            polling_status = "Yes" if peer.get('polling', False) else "No"
            destroy_time = peer.get('destroy_time')
            refresh_time = peer.get('refresh_time')
            url = peer.get('url', 'N/A')

            # Format destroy_time as ISO datetime
            destroy_time_str = "N/A"
            if isinstance(destroy_time, (int, float)):
                destroy_time_str = datetime.datetime.fromtimestamp(destroy_time).isoformat()

            # Format refresh_time as ISO datetime
            refresh_time_str = "N/A"
            if isinstance(refresh_time, (int, float)):
                refresh_time_str = datetime.datetime.fromtimestamp(refresh_time).isoformat()

            peer_display = (
                f"   {agtuuid_peer:.<36} "
                f"Polling: {polling_status:.<5} "
                f"Destroy: {destroy_time_str:.<26} "
                f"Refresh: {refresh_time_str:.<26} "
                f"URL: {url}"
            )
            click.echo(peer_display)
    else:
        click.echo("   (No peers discovered)")

    # Display routes
    click.echo()
    click.echo(click.style("🛣️  Network Routes", fg='cyan', bold=True))
    if routes:
        for route in routes:
            agtuuid_route = route.get('agtuuid', 'unknown')
            gtwuuid       = route.get('gtwuuid', 'unknown')
            weight        = route.get('weight', 'unknown')

            route_display = f"   {agtuuid_route:.<36} → {gtwuuid:.<36} (weight: {weight})"
            click.echo(route_display)
    else:
        click.echo("   (No routes discovered)")

    # Display hops
    click.echo()
    click.echo(click.style("🔗 Network Hops", fg='cyan', bold=True))
    if hops:
        # Sort hops by time in ascending order
        sorted_hops = sorted(
            hops,
            key=lambda h: h.get('hop_time', float('inf'))
        )

        for idx, hop in enumerate(sorted_hops, 1):
            hop_time    = hop.get('hop_time', 'N/A')
            agtuuid_hop = hop.get('agtuuid', 'unknown')
            hop_type    = hop.get('type_str', 'unknown')

            # Format hop time nicely
            if isinstance(hop_time, (int, float)):
                hop_time_dt = datetime.datetime.fromtimestamp(hop_time)
                hop_display = f"   [{idx}] {agtuuid_hop:.<36} {hop_type:.<20} @ {hop_time_dt.isoformat()}"
            else:
                hop_display = f"   [{idx}] {agtuuid_hop:.<36} {hop_type}"

            click.echo(hop_display)
    else:
        click.echo("   (No hops recorded)")

    click.echo()
    click.echo("=" * 70)
    click.echo()


if __name__ == '__main__':
    main()
