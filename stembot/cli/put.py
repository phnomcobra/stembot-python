"""put command — transfer a file from source to destination."""
import time

import click

from stembot.enums import ControlFormType
from stembot.executor.agent import AgentClient
from stembot.executor.file import load_file_to_form, write_file_from_form
from stembot.models.config import CONFIG
from stembot.models.control import CheckTicket, CloseTicket, ControlFormTicket, LoadFile, WriteFile


# pylint: disable=too-many-branches, too-many-statements, too-many-locals, too-many-arguments, line-too-long
@click.command()
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
        it = time.time()
        check = CheckTicket(tckuuid=ticket.tckuuid, create_time=ticket.create_time)
        check = client.send_control_form(check)
        while check.service_time is None and time.time() - it < timeout * 2:
            time.sleep(1)
            check = client.send_control_form(check)

        if check.service_time is not None:
            ticket.type = ControlFormType.READ_TICKET
            ticket = client.send_control_form(ticket)

        client.send_control_form(CloseTicket(tckuuid=ticket.tckuuid))
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
        it = time.time()
        check = CheckTicket(tckuuid=ticket.tckuuid, create_time=ticket.create_time)
        ticket.form.b64zlib = ""
        check = client.send_control_form(check)
        while check.service_time is None and time.time() - it < timeout * 2:
            time.sleep(1)
            check = client.send_control_form(check)

        if check.service_time is not None:
            ticket.type = ControlFormType.READ_TICKET
            ticket = client.send_control_form(ticket)

        client.send_control_form(CloseTicket(tckuuid=ticket.tckuuid))
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
