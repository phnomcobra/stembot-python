"""Offline Agent Configuration

Command-line interface for configuring stembot agent settings using Click.
Supports setting individual options or loading from environment variables.

Examples:
    # View current configuration
    python -m stembot.configure --view

    # Set agent UUID and port
    python -m stembot.configure --agtuuid my-agent-123 --port 8080

    # Load configuration from environment variables
    python -m stembot.configure --load-env

    # Set client control URL to local host
    python -m stembot.configure --client-local
"""
import hashlib
import os
import logging

import click

from stembot.dao import kvstore

logger = logging.getLogger(__name__)


def _load_from_environment():
    """Load configuration settings from environment variables.

    Supports the following environment variables:
    - AGT_UUID: Agent identifier
    - AGT_HOST: Server host address
    - AGT_PORT: Server TCP port
    - AGT_LOG_PATH: Log output path
    - AGT_SECRET: Encryption key (will be hashed to 16 bytes)
    - AGT_CLIENT_CONTROL_URL: Client control URL
    """
    if agtuuid := os.environ.get('AGT_UUID'):
        kvstore.commit('agtuuid', agtuuid)
        click.echo(f"✓ Loaded AGT_UUID: {agtuuid}")

    if socket_host := os.environ.get('AGT_HOST'):
        kvstore.commit('socket_host', socket_host)
        click.echo(f"✓ Loaded AGT_HOST: {socket_host}")

    if socket_port := os.environ.get('AGT_PORT'):
        kvstore.commit('socket_port', int(socket_port))
        click.echo(f"✓ Loaded AGT_PORT: {socket_port}")

    if log_path := os.environ.get('AGT_LOG_PATH'):
        kvstore.commit('log_path', log_path)
        click.echo(f"✓ Loaded AGT_LOG_PATH: {log_path}")

    if secret_text := os.environ.get('AGT_SECRET'):
        secret_hash = hashlib.sha256(secret_text.encode()).digest()[:16]
        kvstore.commit('secret_digest', secret_hash)
        click.echo("✓ Loaded AGT_SECRET (hashed to 16 bytes)")

    if client_control_url := os.environ.get('AGT_CLIENT_CONTROL_URL'):
        kvstore.commit('client_control_url', client_control_url)
        click.echo(f"✓ Loaded AGT_CLIENT_CONTROL_URL: {client_control_url}")


def _display_config():
    """Display current configuration settings in a formatted table."""
    click.echo("\n" + "="*50)
    click.echo("Current Configuration")
    click.echo("="*50)
    config_items = [
        ('Client Control URL', kvstore.get('client_control_url')),
        ('Agent ID', kvstore.get('agtuuid')),
        ('Host', kvstore.get('socket_host')),
        ('Port', kvstore.get('socket_port')),
        ('Log Path', kvstore.get('log_path')),
        ('Secret Digest', kvstore.get('secret_digest').hex() if kvstore.get('secret_digest') else None),
    ]
    for key, value in config_items:
        # Truncate long values for display
        display_value = str(value)[:60] + "..." if len(str(value)) > 60 else value
        click.echo(f"{key:.<25} {display_value}")
    click.echo("="*50 + "\n")


@click.command(help="Configure offline agent settings")
@click.option(
    '-a', '--agtuuid',
    type=str,
    help='Agent identifier'
)
@click.option(
    '-p', '--port',
    type=int,
    help='Server TCP port'
)
@click.option(
    '-d', '--host',
    type=str,
    help='Server host address'
)
@click.option(
    '-s', '--secret',
    type=str,
    help='Encryption key (will be hashed to 16 bytes)'
)
@click.option(
    '-l', '--log-path',
    type=str,
    help='Log output path'
)
@click.option(
    '-c', '--client-url',
    type=str,
    help='Set the agent client control URL'
)
@click.option(
    '--client-local',
    is_flag=True,
    help='Set client control URL to local host (http://127.0.0.1:<port>/control)'
)
@click.option(
    '-v', '--view',
    is_flag=True,
    help='View current configuration settings'
)
@click.option(
    '-e', '--load-env',
    is_flag=True,
    help='Load configuration from environment variables'
)
def main(agtuuid, port, host, secret, log_path, client_url, client_local, view, load_env):
    """Configure agent settings via command-line options or environment variables.

    Configuration is stored persistently in the kvstore database.
    """
    # Load from environment if requested
    if load_env:
        click.echo("Loading configuration from environment variables...")
        _load_from_environment()

    # Set individual options
    if agtuuid:
        kvstore.commit('agtuuid', agtuuid)
        click.echo(f"✓ Set Agent UUID: {agtuuid}")

    if host:
        kvstore.commit('socket_host', host)
        click.echo(f"✓ Set Host: {host}")

    if port:
        kvstore.commit('socket_port', port)
        click.echo(f"✓ Set Port: {port}")

    if log_path:
        kvstore.commit('log_path', log_path)
        click.echo(f"✓ Set Log Path: {log_path}")

    if secret:
        secret_hash = hashlib.sha256(secret.encode()).digest()[:16]
        kvstore.commit('secret_digest', secret_hash)
        click.echo("✓ Set Secret (hashed to 16 bytes)")

    if client_url:
        kvstore.commit('client_control_url', client_url)
        click.echo(f"✓ Set Client Control URL: {client_url}")

    if client_local:
        local_url = f"http://127.0.0.1:{kvstore.get('socket_port')}/control"
        kvstore.commit('client_control_url', local_url)
        click.echo(f"✓ Set Client Control URL to local: {local_url}")

    # View configuration if requested
    if view:
        _display_config()

    # Show help message if no options provided
    if not any([agtuuid, host, port, log_path, secret, client_url, client_local, load_env, view]):
        click.echo("No options provided. Use --help for usage information.")


if __name__ == '__main__':
    main() # pylint: disable=no-value-for-parameter
