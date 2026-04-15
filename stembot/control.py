
"""CLI control interface for agent management and network operations.

Provides command-line tools for interacting with stembot agents over HTTP.
Supports peer discovery, topology management, file transfer, benchmarking,
and remote command execution.

Commands:
- discover: Discover and establish connections with peer agents
- delete: Remove agents from the network
- stat: Retrieve agent statistics (config, peers, routes, hops)
- bench: Benchmark agent performance with file I/O operations
- put: Transfer files between agents or local filesystem
- run: Execute remote commands on agents

Key features:
- HTTP-based agent communication with AES-256 encryption
- Multi-hop routing with network topology discovery
- Concurrent file transfer benchmarking with configurable load
- Pretty-printed results with formatted byte sizes and timestamps
- Timeout-based operation cancellation
- Thread pool execution for concurrent operations
"""

import datetime
from concurrent.futures import ThreadPoolExecutor
from random import randbytes
import sys
import time

import click

from stembot.enums import ControlFormType
from stembot.executor.agent import AgentClient
from stembot.executor.file import load_file_to_form, load_form_from_bytes, write_file_from_form
from stembot.models.config import CONFIG
from stembot.models.control import ControlFormTicket, DeletePeers, DiscoverPeer, GetConfig
from stembot.models.control import GetPeers, GetRoutes, LoadFile, SyncProcess, WriteFile

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
    if num_bytes < KB:
        return f"{num_bytes:.0f} B"
    elif num_bytes < MB:
        return f"{num_bytes / KB:.1f} KB"
    elif num_bytes < GB:
        return f"{num_bytes / MB:.1f} MB"
    else:
        return f"{num_bytes / GB:.1f} GB"


def format_bandwidth(bytes_per_second: int | float) -> str:
    """Convert bytes per second to human-readable format (B/s, KB/s, MB/s, or GB/s).

    Args:
        bytes_per_second: Transfer rate in bytes per second

    Returns:
        Formatted string with appropriate unit
    """
    bytes_per_second = float(bytes_per_second)
    if bytes_per_second < KB:
        return f"{bytes_per_second:.0f} B/s"
    elif bytes_per_second < MB:
        return f"{bytes_per_second / KB:.1f} KB/s"
    elif bytes_per_second < GB:
        return f"{bytes_per_second / MB:.1f} MB/s"
    else:
        return f"{bytes_per_second / GB:.1f} GB/s"


@click.group(help='Agent control and network management')
def main():
    """CLI entry point for agent control and network management.

    Provides command-line interface for discovering peers, managing agent
    topology, querying statistics, benchmarking performance, and executing
    remote operations on stembot agents.
    """


@main.command()
@click.argument('peer_url', required=True)
@click.option('-p', '--polling', is_flag=True, help='Enable polling mode for discovery')
@click.option('-d', '--delay', type=int, default=None, help='Delay making discovery request for n number of seconds')
@click.option('--ttl', type=int, default=None, help='Time-to-live for the discovery in seconds')
def discover(peer_url: str, polling: bool, delay: int, ttl: int):
    """Discover and establish connection with a peer agent.

    Initiates a discovery request to a peer agent at the specified URL.
    Optionally enables polling mode for continuous discovery and sets
    time-to-live (TTL) for the discovery request.

    Args:
        peer_url: URL of the peer agent to discover (e.g., http://peer:8080)
        polling: Enable polling mode for continuous discovery updates
        delay: Seconds to wait before making the discovery request
        ttl: Time-to-live for the discovery in seconds

    Displays:
        - Discovery status and peer details (UUID, URL, polling mode)
        - Form information (type, object UUID, collection UUID)
        - Network hops with timestamps for route tracing
    """
    if delay:
        click.echo(f"Waiting {delay} seconds before discovery...")
        time.sleep(delay)

    client = AgentClient(url=CONFIG.client_control_url)
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
    """Remove agents from the network.

    Deletes one or more agents from the network topology. Can delete
    all agents at once or a specific agent by UUID.

    Args:
        delete_all: Delete all agents in the network
        agtuuid: UUID of a specific agent to delete

    Note:
        Must specify either --all or --agtuuid; requires at least one.

    Raises:
        Click error if neither --all nor --agtuuid is provided.
    """
    client = AgentClient(url=CONFIG.client_control_url)

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


def _bench(agtuuid: str, size: int=1, concurrency: int=1, timeout: int=15, zeros: bool=False):
    """Benchmark file I/O performance on a remote agent.

    Performs concurrent file write and read operations on a remote agent.
    Supports configurable file sizes, concurrency levels, and data content
    (random or zeros). Measures total bandwidth and success rate.

    Args:
        agtuuid: UUID of the target agent for benchmarking
        size: Size of each file in bytes (default: 1)
        concurrency: Number of concurrent operations (default: 1)
        timeout: Seconds to wait for each operation (default: 15)
        zeros: Use zero-filled bytes instead of random data

    Outputs:
        Single benchmark result row with elapsed time, total bytes,
        success rate, bytes per operation, and bandwidth.

    Note:
        Uses ThreadPoolExecutor for concurrent submissions and polling.
        Skips benchmark if size * concurrency > 1GB.
    """
    client = AgentClient(url=CONFIG.client_control_url)

    assert size > 0 and concurrency > 0 and timeout > 0

    write_tickets: list[ControlFormTicket] = []
    load_tickets:  list[ControlFormTicket] = []

    for i in range(0, concurrency):
        if zeros:
            data = bytes([0] * size)
        else:
            data = randbytes(size)
        write_form = load_form_from_bytes(data=data)
        write_form.path = f'/tmp/test.{i}.{size}.dat'
        write_tickets.append(ControlFormTicket(dst=agtuuid, form=write_form))
        load_tickets.append(ControlFormTicket(dst=agtuuid, form=LoadFile(path=write_form.path)))

    outer_it = time.time()

    # Send write tickets using threads
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        write_tickets = list(executor.map(client.send_control_form, write_tickets))

    # Poll for write completion using threads
    def poll_write_ticket(ticket: ControlFormTicket) -> ControlFormTicket:
        ticket.type = ControlFormType.READ_TICKET
        it = time.time()
        ticket = client.send_control_form(ticket)
        while ticket.service_time is None and time.time() - it < timeout:
            time.sleep(1)
            ticket = client.send_control_form(ticket)
        ticket.type = ControlFormType.CLOSE_TICKET
        return client.send_control_form(ticket)

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        write_tickets = list(executor.map(poll_write_ticket, write_tickets))

    # Send load tickets using threads
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        load_tickets = list(executor.map(client.send_control_form, load_tickets))

    # Poll for load completion using threads
    def poll_load_ticket(ticket: ControlFormTicket) -> ControlFormTicket:
        ticket.type = ControlFormType.READ_TICKET
        it = time.time()
        ticket = client.send_control_form(ticket)
        while ticket.service_time is None and time.time() - it < timeout:
            time.sleep(1)
            ticket = client.send_control_form(ticket)
        ticket.type     = ControlFormType.CLOSE_TICKET
        return client.send_control_form(ticket)

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        load_tickets = list(executor.map(poll_load_ticket, load_tickets))

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

    # Format output with units
    elapsed_time_str = f"{round(outer_et, 3)}s"
    total_bytes_str = format_bytes(total_size)
    bytes_per_op_str = format_bytes(size)
    bandwidth_str = format_bandwidth(bandwidth)

    # Pretty print as a single row in the benchmark table
    row = (
        f"   {elapsed_time_str:.<11} "
        f"{total_bytes_str:.<12} "
        f"{success_rate_str:.<8} "
        f"{bytes_per_op_str:.<10} "
        f"{bandwidth_str}"
    )
    click.echo(row)


@main.command()
@click.argument('agtuuid', required=True)
@click.option('-t', '--timeout', type=int, default=15, help='Timeout in seconds (default: 15)')
@click.option('-z', '--zeros', is_flag=True, help='Use zero bytes instead of random data for testing')
def bench(agtuuid: str, timeout: int, zeros: bool):
    """Benchmark agent file I/O performance across multiple file sizes.

    Runs a comprehensive benchmark suite with varying file sizes and
    concurrency levels. Iterates through sizes from 16KB to 16MB and
    concurrency from 1 to 64. Skips combinations exceeding 1GB total.

    Args:
        agtuuid: UUID of the agent to benchmark
        timeout: Timeout in seconds for each operation (default: 15)
        zeros: Use zero-filled bytes instead of random data

    Displays:
        - Formatted table with columns: Elapsed (s), Total Bytes,
          Success rate (completed:total), Bytes/Op, Bandwidth
        - Results for all size/concurrency combinations (1GB max)

    Note:
        Performs both write (upload) and read (download) operations
        for comprehensive I/O benchmarking.
    """
    # Pretty print header
    click.echo()
    click.echo("=" * 70)
    click.echo(click.style(f"📊 Benchmark Results for {agtuuid}", fg='cyan', bold=True))
    click.echo("=" * 70)
    click.echo()

    # Column headers
    header = (
        f"   {'Elapsed (s)':.<11} "
        f"{'Total Bytes':.<12} "
        f"{'Success':.<8} "
        f"{'Bytes/Op':.<10} "
        f"{'Bandwidth'}"
    )
    click.echo(click.style(header, fg='cyan', bold=True))
    click.echo("-" * 70)

    sizes         = [KB*16*(2**x) for x in range(0, 17)]
    concurrencies = [2**x         for x in range(0, 7)]

    try:
        for size in sizes:
            for concurrency in concurrencies:
                if size * concurrency > GB:
                    continue
                _bench(agtuuid=agtuuid, timeout=timeout, size=size, concurrency=concurrency, zeros=zeros)
    except Exception as exception: # pylint: disable=broad-except
        click.echo(exception, err=True)

    click.echo("-" * 70)
    click.echo()
    click.echo("=" * 70)
    click.echo()


@main.command()
@click.argument('src_path', required=True)
@click.argument('dst_path', required=True)
@click.option('-t', '--timeout', type=int, default=15, help='Timeout in seconds (default: 15)')
@click.option('-s', '--src-agtuuid', type=str, default=None)
@click.option('-d', '--dst-agtuuid', type=str, default=None)
def put(src_path: str, dst_path: str | None, timeout: int, src_agtuuid: str | None, dst_agtuuid: str | None):
    """Transfer a file from source to destination.

    Transfers a file between two agents or between local filesystem and
    an agent. Supports agent-to-agent, local-to-agent, agent-to-local,
    and local-to-local transfers.

    Args:
        src_path: Path to the source file to transfer
        dst_path: Path where the file should be written on the destination
        timeout: Maximum seconds to wait for operations (default: 15)
        src_agtuuid: UUID of source agent (if None, reads from local filesystem)
        dst_agtuuid: UUID of destination agent (if None, writes to local filesystem)

    Displays:
        - Transfer details (source and destination locations)
        - File information (size in bytes, MD5 checksum)
        - Timing information (read time, write time, total time)
        - Error messages if read or write operations fail

    Note:
        Uses LoadFile and WriteFile forms with zlib compression and
        MD5 verification for integrity checking.
    """
    client = AgentClient(url=CONFIG.client_control_url)

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
    """Execute a command on a remote agent.

    Sends a command to a remote agent for execution via subprocess.
    Polls for completion with timeout and displays stdout/stderr output.
    Exits with the remote process's return code.

    Args:
        agtuuid: UUID of the agent to execute the command on
        command: Command to execute (string or shell command)
        timeout: Maximum seconds to wait for execution (default: 15)

    Displays:
        - Standard output from the remote process
        - Standard error messages if any

    Exits:
        With the remote process's return code (0 for success, non-zero for error)
        or exit code 1 if ticket service times out or errors occur.

    Note:
        Uses SyncProcess with timeout enforcement. The poll timeout is
        2x the specified timeout to allow process execution time plus polling.
    """
    client       = AgentClient(url=CONFIG.client_control_url)
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
