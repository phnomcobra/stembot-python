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
import time
import logging

import click
from devtools import pprint

from stembot.executor.agent import ControlFormClient
from stembot.dao import kvstore
from stembot.models.control import DeletePeers, DiscoverPeer, GetPeers, GetRoutes

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
    """
    if delay:
        click.echo(f"Waiting {delay} seconds before discovery...")
        time.sleep(delay)

    client = ControlFormClient(url=kvstore.get('client_control_url'))
    click.echo(f"Discovering peer: {peer_url}")

    result = client.send_control_form(DiscoverPeer(
        url=peer_url,
        polling=polling,
        ttl=ttl,
    ))
    pprint(result)


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
@click.option(
    '--peers',
    'show_peers',
    is_flag=True,
    help='List all peers in the network'
)
@click.option(
    '--routes',
    'show_routes',
    is_flag=True,
    help='List all routes in the network'
)
def list(show_peers, show_routes):
    """List network topology information.

    Use --peers to show all connected peers, or --routes to show routing table.
    """
    client = ControlFormClient(url=kvstore.get('client_control_url'))

    if show_peers:
        click.echo("Network peers:")
        result = client.send_control_form(GetPeers())
        pprint(result)
    elif show_routes:
        click.echo("Network routes:")
        result = client.send_control_form(GetRoutes())
        pprint(result)
    else:
        click.echo("Error: Use --peers or --routes", err=True)


@main.command()
@click.argument('agtuuid', required=True)
@click.option(
    '-t', '--timeout',
    type=int,
    default=15,
    help='Timeout in seconds (default: 15)'
)
def trace(agtuuid, timeout):
    """Find the network path to a specific agent.

    AGTUUID: Agent UUID to trace
    """
    client = ControlFormClient(url=kvstore.get('client_control_url'))
    click.echo(f"Tracing path to agent: {agtuuid} (timeout: {timeout}s)")
    # Note: Trace functionality would need to be implemented in the models
    click.echo("Trace command not yet fully implemented")


@main.command()
@click.argument('agtuuid', required=True)
@click.option(
    '-t', '--timeout',
    type=int,
    default=15,
    help='Timeout in seconds (default: 15)'
)
@click.option(
    '-c', '--continuous',
    is_flag=True,
    help='Continuously ping the agent'
)
def ping(agtuuid, timeout, continuous):
    """Ping an agent to check connectivity.

    AGTUUID: Agent UUID to ping
    """
    client = ControlFormClient(url=kvstore.get('client_control_url'))
    click.echo(f"Pinging agent: {agtuuid} (timeout: {timeout}s)")
    if continuous:
        click.echo("Continuous mode enabled")
    # Note: Ping functionality would need to be implemented in the models
    click.echo("Ping command not yet fully implemented")


if __name__ == '__main__':
    main()
