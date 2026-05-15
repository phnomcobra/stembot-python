"""bench command — benchmark agent throughput across multiple payload sizes."""
import time
from concurrent.futures import ThreadPoolExecutor

import click

from stembot.executor.agent import AgentClient
from stembot.models.config import CONFIG
from stembot.models.control import Benchmark, CheckTicket, CloseTicket, ControlFormTicket
from stembot.cli.utils import KB, MB, format_bytes, format_bandwidth


def _bench(agtuuid: str, size: int = 1, concurrency: int = 1, timeout: int = 15):
    """Benchmark inbound and outbound throughput on a remote agent.

    Sends three batches of concurrent Benchmark tickets to the target agent:
    one to measure outbound throughput (client → agent), one to measure
    inbound throughput (agent → client), and one with both inbound and
    outbound sizes set to measure overall bidirectional throughput. Bandwidth
    is calculated per ticket using the difference between service_time and
    create_time.

    Args:
        agtuuid: UUID of the target agent for benchmarking
        size: Payload size in bytes for each direction (default: 1)
        concurrency: Number of concurrent tickets per direction (default: 1)
        timeout: Seconds to wait for each ticket to be serviced (default: 15)

    Outputs:
        One benchmark result row with aggregated totals, success counts
        (inbound:outbound:combined:attempted), and inbound/outbound/overall
        bandwidth columns.

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
    # Combined: send and receive `size` bytes in the same ticket
    combined_checks = run_batch(lambda: Benchmark(outbound_size=size, inbound_size=size))

    def calc(checks: list[CheckTicket], bytes_per_ticket: int) -> tuple[float, int, int]:
        completed = [c for c in checks if c.service_time is not None]
        if not completed:
            return 0.0, 0, 0
        elapsed = max(c.service_time - c.create_time for c in completed)
        total_bytes = len(completed) * bytes_per_ticket
        bw          = total_bytes / elapsed if elapsed > 0 else 0.0
        return bw, len(completed), total_bytes

    out_bw, out_ok, _out_total   = calc(outbound_checks, size)
    in_bw,  in_ok,  _in_total    = calc(inbound_checks, size)
    all_bw, both_ok, _both_total = calc(combined_checks, size * 2)

    def fmt_row() -> str:
        success_str = f"{in_ok}:{out_ok}:{both_ok}:{concurrency}"
        return (
            f"   {format_bytes(size):<10} "
            f"{success_str:<15} "
            f"{format_bandwidth(in_bw):<12} "
            f"{format_bandwidth(out_bw):<12} "
            f"{format_bandwidth(all_bw)}"
        )

    click.echo(fmt_row())


@click.command()
@click.argument('agtuuid', required=True)
@click.option('-t', '--timeout', type=int, default=15, help='Timeout in seconds (default: 15)')
def bench(agtuuid: str, timeout: int):
    """Benchmark agent throughput across multiple payload sizes.

    Runs a comprehensive benchmark suite with varying payload sizes and
    concurrency levels. Tests inbound (agent → client), outbound
    (client → agent), and a combined bidirectional operation (both inbound
    and outbound sizes set) for each size/concurrency pair. Bandwidth is
    computed from the ticket service_time and create_time.

    Args:
        agtuuid: UUID of the agent to benchmark
        timeout: Timeout in seconds for each operation (default: 15)

    Displays:
        - Formatted table with columns: Bytes/Op,
          Success (in:out:combined:attempted), In BW, Out BW, Overall BW
        - One row for every size/concurrency combination
    """
    click.echo()
    click.echo("=" * 78)
    click.echo(click.style(f"📊 Benchmark Results for {agtuuid}", fg='cyan', bold=True))
    click.echo("=" * 78)
    click.echo()

    header = (
        f"   {'Bytes/Op':.<10} "
        f"{'Success in:out:all:try':.<15} "
        f"{'In BW':.<12} "
        f"{'Out BW':.<12} "
        f"{'Overall BW'}"
    )
    click.echo(click.style(header, fg='cyan', bold=True))
    click.echo("-" * 78)

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

    click.echo("-" * 78)
    click.echo()
    click.echo("=" * 78)
    click.echo()
