"""Online Agent Configuration

Command-line interface for agent control operations using Click.
Supports discovering peers, managing peer connections, listing network topology,
and tracing/pinging agents.

Examples:
    # Discover a peer
    python -m stembot.control discover http://c2:8080/mpi -d 5

    # Delete a specific agent
    python -m stembot.control delete --agtuuid c2

    # Delete all agents
    python -m stembot.control delete --all

    # Stat an agent (retrieves configuration, peers, routes, and hops)
    python -m stembot.control stat c2
"""
import datetime
import time

import click

from stembot.enums import ControlFormType
from stembot.executor.agent import ControlFormClient
from stembot.dao import kvstore
from stembot.models.control import ControlFormTicket, DeletePeers, DiscoverPeer, GetConfig, GetPeers, GetRoutes


@click.group(help='Agent control and network management')
def main():
    """Manage agent connections, discover peers, and manage network topology."""


@main.command()
@click.argument('peer_url', required=True)
@click.option('-p', '--polling', is_flag=True, help='Enable polling mode for discovery')
@click.option('-d', '--delay', type=int, default=None, help='Delay making discovery request for n number of seconds')
@click.option('--ttl', type=int, default=None, help='Time-to-live for the discovery in seconds')
def discover(peer_url: str, polling: bool, delay: int, ttl: int):
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
        click.echo("   Agent UUID................... (not yet assigned)")

    # TTL
    if form.ttl is not None:
        click.echo(f"   TTL (Time-to-Live)........... {form.ttl} seconds")
    else:
        click.echo("   TTL (Time-to-Live)........... (not set)")

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
@click.option('--all', 'delete_all', is_flag=True, help='Delete all agents')
@click.option('--agtuuid', type=str, default=None, help='Delete a specific agent by UUID')
def delete(delete_all: bool, agtuuid: str | None):
    client = ControlFormClient(url=kvstore.get('client_control_url'))

    if delete_all:
        click.echo("Deleting all agents...")
        form = client.send_control_form(DeletePeers())
        if error := form.error:
            click.echo(error, err=True)

    elif agtuuid:
        click.echo(f"Deleting agent: {agtuuid}")
        form = client.send_control_form(DeletePeers(agtuuids=[agtuuid]))
        if error := form.error:
            click.echo(error, err=True)
    else:
        click.echo("Error: Use --all or --agtuuid <UUID>", err=True)


@main.command()
@click.argument('agtuuid', required=True)
@click.option('-t', '--timeout', type=int, default=15, help='Timeout in seconds (default: 15)')
def stat(agtuuid: str, timeout: int):
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
        # Format destroy_time as ISO datetime
        destroy_time_str = "N/A"
        if isinstance(peer.destroy_time, (int, float)):
            destroy_time_str = datetime.datetime.fromtimestamp(peer.destroy_time).isoformat()

        # Format refresh_time as ISO datetime
        refresh_time_str = "N/A"
        if isinstance(peer.refresh_time, (int, float)):
            refresh_time_str = datetime.datetime.fromtimestamp(peer.refresh_time).isoformat()

        peer_display = (
            f"   {peer.agtuuid:.<36} "
            f"Polling: {peer.polling:.<5} "
            f"Destroy: {destroy_time_str:.<26} "
            f"Refresh: {refresh_time_str:.<26} "
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


if __name__ == '__main__':
    main()
