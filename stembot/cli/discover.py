"""discover command — discover and establish connection with a peer agent."""
import time

import click

from stembot.executor.agent import AgentClient
from stembot.models.config import CONFIG
from stembot.models.control import DiscoverPeer


@click.command()
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
