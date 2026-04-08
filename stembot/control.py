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
from random import randbytes
import sys
import time

import click

from stembot.enums import ControlFormType
from stembot.executor.agent import ControlFormClient
from stembot.executor.file import load_file_to_form, load_form_from_bytes, write_file_from_form
from stembot.models.config import CONFIG
from stembot.models.control import ControlFormTicket, DeletePeers, DiscoverPeer, GetConfig, GetPeers, GetRoutes, LoadFile, SyncProcess, WriteFile

KB = 1024
MB = 1024 * 1024

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

    client = ControlFormClient(url=CONFIG.client_control_url)
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
    client = ControlFormClient(url=CONFIG.client_control_url)

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
    client = ControlFormClient(url=CONFIG.client_control_url)

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


def _bench(agtuuid: str, size: int=1, concurrency: int=1, timeout: int=15):
    client = ControlFormClient(url=CONFIG.client_control_url)

    assert size > 0 and concurrency > 0 and timeout > 0

    write_tickets: list[ControlFormTicket] = []
    load_tickets:  list[ControlFormTicket] = []

    for i in range(0, concurrency):
        write_form = load_form_from_bytes(data=randbytes(size))
        write_form.path = f'/test.{i}.{size}.dat'
        write_tickets.append(ControlFormTicket(dst=agtuuid, form=write_form))
        load_tickets.append(ControlFormTicket(dst=agtuuid, form=LoadFile(path=write_form.path)))

    outer_it = time.time()

    for i, ticket in enumerate(write_tickets):
        write_tickets[i] = client.send_control_form(ticket)

    for i, ticket in enumerate(write_tickets):
        ticket.type = ControlFormType.READ_TICKET
        it = time.time()
        ticket = client.send_control_form(ticket)
        while ticket.service_time is None and time.time() - it < timeout:
            time.sleep(1)
            ticket = client.send_control_form(ticket)

        ticket.type      = ControlFormType.CLOSE_TICKET
        write_tickets[i] = client.send_control_form(ticket)

    for i, ticket in enumerate(load_tickets):
        load_tickets[i] = client.send_control_form(ticket)

    for i, ticket in enumerate(load_tickets):
        ticket.type = ControlFormType.READ_TICKET
        it = time.time()
        ticket = client.send_control_form(ticket)
        while ticket.service_time is None and time.time() - it < timeout:
            time.sleep(1)
            ticket = client.send_control_form(ticket)

        ticket.type     = ControlFormType.CLOSE_TICKET
        load_tickets[i] = client.send_control_form(ticket)

    outer_et         = time.time() - outer_it
    total_size       = concurrency * size
    bandwidth        = 2.0 * total_size / outer_et
    completed_loads  = [
        x for x in load_tickets if (
            x.service_time and \
            x.error is None and \
            x.form.error is None
        )
    ]
    success_rate_str = f'{len(completed_loads)}:{concurrency}'

    click.echo(f'{round(outer_et, 3): <16} {total_size: <16} {success_rate_str: <16} {size: <16} {round(bandwidth)} ')


@main.command()
@click.argument('agtuuid', required=True)
@click.option('-t', '--timeout', type=int, default=15, help='Timeout in seconds (default: 15)')
def bench(agtuuid: str, timeout: int):
    click.echo('Elapsed Time     Total Bytes      Success Rate     Bytes            Bandwidth')

    sizes         = [KB*16*(2**x) for x in range(0, 11)]
    concurrencies = [2**x         for x in range(0, 6)]

    for size in sizes:
        for concurrency in concurrencies:
            if size * concurrency > 16 * MB:
                continue
            _bench(agtuuid=agtuuid, timeout=timeout, size=size, concurrency=concurrency)


@main.command()
@click.argument('src_path', required=True)
@click.argument('dst_path', required=True)
@click.option('-t', '--timeout', type=int, default=15, help='Timeout in seconds (default: 15)')
@click.option('-s', '--src-agtuuid', type=str, default=None)
@click.option('-d', '--dst-agtuuid', type=str, default=None)
def put(src_path: str, dst_path: str | None, timeout: int, src_agtuuid: str | None, dst_agtuuid: str | None):
    """Transfer a file from source to destination.

    SRC_PATH: Path to the source file to transfer
    DST_PATH: Path where the file should be written on the destination agent

    Options:
    - Use --src-agtuuid to specify source agent (local read if not specified)
    - Use --dst-agtuuid to specify destination agent (local write if not specified)
    - Use --timeout to set operation timeout in seconds
    """
    client = ControlFormClient(url=CONFIG.client_control_url)

    # Track timing for read and write operations
    read_start_time    = None
    read_elapsed_time  = 0
    write_start_time   = None
    write_elapsed_time = 0
    read_error         = None
    write_error        = None

    # Load file from source
    load_form = LoadFile(path=src_path)

    if src_agtuuid:
        click.echo(f"Reading from {src_agtuuid}:{src_path}...")
        read_start_time = time.time()
        ticket = client.send_control_form(ControlFormTicket(dst=src_agtuuid, form=load_form))
        ticket.type = ControlFormType.READ_TICKET
        it = time.time()
        while time.time() - it < timeout * 2 and not ticket.service_time:
            ticket = client.send_control_form(ticket)
            time.sleep(1)

        ticket.type = ControlFormType.CLOSE_TICKET
        client.send_control_form(ticket)
        read_elapsed_time = time.time() - read_start_time

        if ticket.service_time is None:
            read_error = "Load ticket never serviced!"
            click.echo(read_error, err=True)

        if ticket.error:
            read_error = ticket.error
            click.echo(ticket.error, err=True)

        if ticket.form.error:
            read_error = ticket.form.error
            click.echo(ticket.form.error, err=True)

        load_form = ticket.form
    else:
        click.echo(f"Reading from local:{src_path}...")
        read_start_time = time.time()
        load_form = load_file_to_form(load_form)
        read_elapsed_time = time.time() - read_start_time

        if load_form.error:
            read_error = load_form.error
            click.echo(load_form.error, err=True)

    # Write file to destination
    write_form = WriteFile(b64zlib=load_form.b64zlib, md5sum=load_form.md5sum, size=load_form.size, path=dst_path) \
        if not read_error else None

    if dst_agtuuid and not read_error:
        click.echo(f"Writing to {dst_agtuuid}:{dst_path}...")
        write_start_time = time.time()
        ticket = client.send_control_form(ControlFormTicket(dst=dst_agtuuid, form=write_form))
        ticket.type = ControlFormType.READ_TICKET
        it = time.time()
        while time.time() - it < timeout * 2 and not ticket.service_time:
            ticket = client.send_control_form(ticket)
            time.sleep(1)

        ticket.type = ControlFormType.CLOSE_TICKET
        client.send_control_form(ticket)
        write_elapsed_time = time.time() - write_start_time

        if ticket.service_time is None:
            write_error = "Write ticket never serviced!"
            click.echo(write_error, err=True)

        if ticket.error:
            write_error = ticket.error
            click.echo(ticket.error, err=True)

        if ticket.form.error:
            write_error = ticket.form.error
            click.echo(ticket.form.error, err=True)

        write_form = ticket.form
    elif not read_error:
        click.echo(f"Writing to local:{dst_path}...")
        write_start_time = time.time()
        write_form = write_file_from_form(write_form)
        write_elapsed_time = time.time() - write_start_time

        if write_form.error:
            write_error = write_form.error
            click.echo(write_form.error, err=True)

    # Pretty print the results
    click.echo()
    click.echo("=" * 70)
    click.echo("File Transfer Result")
    click.echo("=" * 70)

    # Display transfer details
    click.echo()
    click.echo(click.style("📋 Transfer Details", fg='cyan', bold=True))

    src_location = f"{src_agtuuid}:{src_path}" if src_agtuuid else f"local:{src_path}"
    dst_location = f"{dst_agtuuid}:{dst_path}" if dst_agtuuid else f"local:{dst_path}"

    click.echo(f"   Source................... {src_location}")
    click.echo(f"   Destination.............. {dst_location}")

    # Display file information
    click.echo()
    click.echo(click.style("📦 File Information", fg='cyan', bold=True))

    size = load_form.size if hasattr(load_form, 'size') and load_form.size else 0
    md5sum = load_form.md5sum if hasattr(load_form, 'md5sum') and load_form.md5sum else 'N/A'

    click.echo(f"   Size..................... {size} bytes")
    click.echo(f"   MD5 Checksum............. {md5sum}")

    # Display timing information
    click.echo()
    click.echo(click.style("⏱️  Timing Information", fg='cyan', bold=True))

    click.echo(f"   Read Elapsed Time........ {read_elapsed_time:.3f} seconds")
    click.echo(f"   Write Elapsed Time....... {write_elapsed_time:.3f} seconds")
    click.echo(f"   Total Elapsed Time....... {read_elapsed_time + write_elapsed_time:.3f} seconds")

    # Display errors (if any)
    if read_error or write_error:
        click.echo()
        click.echo(click.style("❌ Errors Occurred", fg='red', bold=True))
        if read_error:
            click.echo(f"   Read Error............... {read_error}")
        if write_error:
            click.echo(f"   Write Error.............. {write_error}")
    else:
        click.echo()
        click.echo(click.style("✓ Transfer Complete", fg='green', bold=True))

    click.echo()
    click.echo("=" * 70)
    click.echo()


@main.command()
@click.argument('agtuuid', required=True)
@click.argument('command', required=True)
@click.option('-t', '--timeout', type=int, default=15, help='Timeout in seconds (default: 15)')
def run(agtuuid: str, command: str, timeout: int):
    client       = ControlFormClient(url=CONFIG.client_control_url)
    sync_process = SyncProcess(command=command, timeout=timeout)
    ticket       = client.send_control_form(ControlFormTicket(dst=agtuuid, form=sync_process))

    ticket.type = ControlFormType.READ_TICKET
    it = time.time()
    while time.time() - it < timeout * 2 and not ticket.service_time:
        ticket = client.send_control_form(ticket)
        time.sleep(1)

    ticket.type = ControlFormType.CLOSE_TICKET
    client.send_control_form(ticket)

    if stdout := ticket.form.stdout:
        click.echo(stdout.strip())

    if stderr := ticket.form.stderr:
        click.echo(stderr.strip(), err=True)

    if status := ticket.form.status:
        sys.exit(status)

    if error := ticket.error:
        click.echo(error.strip(), err=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
