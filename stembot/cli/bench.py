"""bench command — benchmark agent throughput across multiple payload sizes."""
import time
from concurrent.futures import ThreadPoolExecutor

import click

from stembot.executor.agent import AgentClient
from stembot.models.config import CONFIG
from stembot.models.control import Benchmark, CheckTicket, CloseTicket, ControlFormTicket
from stembot.cli.utils import KB, MB, format_bytes, format_bandwidth


# pylint: disable=too-many-locals
def _bench(agtuuid: str, size: int = 1, concurrency: int = 1, timeout: int = 15):
    """Benchmark inbound and outbound throughput on a remote agent.

    Sends two batches of concurrent Benchmark tickets to the target agent:
    one to measure outbound throughput (client → agent) and one to measure
    inbound throughput (agent → client). Bandwidth is calculated per ticket
    using the difference between service_time and create_time.

    Args:
        agtuuid: UUID of the target agent for benchmarking
        size: Payload size in bytes for each direction (default: 1)
        concurrency: Number of concurrent tickets per direction (default: 1)
        timeout: Seconds to wait for each ticket to be serviced (default: 15)

    Outputs:
        Two benchmark result rows (OUT then IN) with elapsed time,
        total bytes, success count, bytes/op, and bandwidth.

    Note:
        Skips benchmark if size * concurrency > 1GB.
    """
    client = AgentClient(url=CONFIG.client_control_url)

    assert size > 0 and concurrency > 0 and timeout > 0

    def poll_ticket(ticket: ControlFormTicket) -> CheckTicket:
        it = time.time()
        check = CheckTicket(tckuuid=ticket.tckuuid, create_time=ticket.create_time)
        check = client.send_control_form(check)
        backoff = 1
        while check.service_time is None and time.time() - it < timeout:
            time.sleep(backoff)
            check = client.send_control_form(check)
            backoff = min(backoff * 2, timeout)
        client.send_control_form(CloseTicket(tckuuid=ticket.tckuuid))
        return check

    def run_batch(form_factory) -> list[CheckTicket]:
        tickets = [ControlFormTicket(dst=agtuuid, form=form_factory()) for _ in range(concurrency)]
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            tickets = list(executor.map(client.send_control_form, tickets))
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            return list(executor.map(poll_ticket, tickets))

    # Outbound: send `size` bytes to the agent
    outbound_checks = run_batch(lambda: Benchmark(outbound_size=size, inbound_size=None))
    # Inbound: receive `size` bytes from the agent
    inbound_checks  = run_batch(lambda: Benchmark(outbound_size=None, inbound_size=size))

    def calc(checks: list[CheckTicket], bytes_per_ticket: int) -> tuple[float, int, float]:
        completed = [c for c in checks if c.service_time is not None]
        if not completed:
            return 0.0, 0, 0.0
        elapsed     = max(c.service_time - c.create_time for c in completed)
        ok          = len(completed)
        bw          = (ok * bytes_per_ticket) / elapsed if elapsed > 0 else 0.0
        return elapsed, ok, bw

    out_elapsed, out_ok, out_bw = calc(outbound_checks, size)
    in_elapsed,  in_ok,  in_bw  = calc(inbound_checks,  size)

    def fmt_row(direction: str, ok: int, elapsed: float, bw: float) -> str:
        elapsed_str     = f"{elapsed:.3f}s"
        total_bytes_str = format_bytes(ok * size)
        success_str     = f"{ok}:{concurrency}"
        size_str        = format_bytes(size)
        return (
            f"   {direction:<6} "
            f"{elapsed_str:<11} "
            f"{total_bytes_str:<12} "
            f"{success_str:<8} "
            f"{size_str:<10} "
            f"{format_bandwidth(bw)}"
        )

    click.echo(fmt_row("OUT", out_ok, out_elapsed, out_bw))
    click.echo(fmt_row("IN",  in_ok,  in_elapsed,  in_bw))


@click.command()
@click.argument('agtuuid', required=True)
@click.option('-t', '--timeout', type=int, default=15, help='Timeout in seconds (default: 15)')
def bench(agtuuid: str, timeout: int):
    """Benchmark agent throughput across multiple payload sizes.

    Runs a comprehensive benchmark suite with varying payload sizes and
    concurrency levels. Tests inbound (agent → client) and outbound
    (client → agent) throughput separately for each size/concurrency pair.
    Bandwidth is computed from the ticket service_time and create_time.

    Args:
        agtuuid: UUID of the agent to benchmark
        timeout: Timeout in seconds for each operation (default: 15)

    Displays:
        - Formatted table with columns: Dir, Elapsed (s), Total Bytes,
          Success, Bytes/Op, Bandwidth
        - Two rows (OUT then IN) for every size/concurrency combination
    """
    click.echo()
    click.echo("=" * 76)
    click.echo(f"Benchmark Results for {agtuuid}")
    click.echo("=" * 76)
    click.echo()

    header = (
        f"   {'Dir':.<6} "
        f"{'Elapsed (s)':.<11} "
        f"{'Total Bytes':.<12} "
        f"{'Success':.<8} "
        f"{'Bytes/Op':.<10} "
        f"Bandwidth"
    )
    click.echo(header)
    click.echo("-" * 76)

    sizes         = [KB * 16 * (2 ** x) for x in range(0, 17)]
    concurrencies = [2 ** x              for x in range(0, 7)]

    try:
        for size in sizes:
            for concurrency in concurrencies:
                if size * concurrency > MB * 256:
                    continue
                _bench(agtuuid=agtuuid, timeout=timeout, size=size, concurrency=concurrency)
    except Exception as exception:  # pylint: disable=broad-except
        click.echo(exception, err=True)

    click.echo("-" * 76)
    click.echo()
    click.echo("=" * 76)
    click.echo()
