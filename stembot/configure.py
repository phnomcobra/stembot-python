"""Offline Agent Configuration

Command-line interface for configuring stembot agent settings using Click.
Supports setting individual options or loading from environment variables.
"""
import hashlib
import os

import click

from stembot.dao import kvstore
from stembot.models.config import LogLevel

def _load_from_environment():
    """Load configuration settings from environment variables.

    Supports the following environment variables:
    - AGT_UUID: Agent identifier
    - AGT_HOST: Server host address
    - AGT_PORT: Server TCP port
    - AGT_LOG_PATH: Log output path
    - AGT_SECRET: Encryption key (will be hashed to 32 bytes)
    - AGT_CLIENT_CONTROL_URL: Client control URL
    - AGT_WORKERS: Number of uvicorn worker processes
    - AGT_LOG_LEVEL_APP: Application log level (DEBUG/INFO/WARNING/ERROR/CRITICAL)
    - AGT_LOG_LEVEL_API: FastAPI/uvicorn log level (DEBUG/INFO/WARNING/ERROR/CRITICAL)
    - AGT_PEER_TIMEOUT_SECS: Seconds before an unresponsive peer is considered dead
    - AGT_PEER_REFRESH_SECS: Seconds between peer refresh cycles
    - AGT_MAX_WEIGHT: Maximum route weight for routing decisions
    - AGT_TICKET_TIMEOUT_SECS: Seconds before a ticket is considered expired
    - AGT_MESSAGE_TIMEOUT_SECS: Seconds before a pending message is discarded
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
        secret_hash = hashlib.sha256(secret_text.encode()).digest()[:32]
        kvstore.commit('secret_digest', secret_hash)
        click.echo("✓ Loaded AGT_SECRET (hashed to 32 bytes)")

    if client_control_url := os.environ.get('AGT_CLIENT_CONTROL_URL'):
        kvstore.commit('client_control_url', client_control_url)
        click.echo(f"✓ Loaded AGT_CLIENT_CONTROL_URL: {client_control_url}")

    if workers := os.environ.get('AGT_WORKERS'):
        kvstore.commit('workers', int(workers))
        click.echo(f"✓ Loaded AGT_WORKERS: {workers}")

    if log_level_app := os.environ.get('AGT_LOG_LEVEL_APP'):
        kvstore.commit('log_level_app', LogLevel[log_level_app.upper()])
        click.echo(f"✓ Loaded AGT_LOG_LEVEL_APP: {log_level_app}")

    if log_level_api := os.environ.get('AGT_LOG_LEVEL_API'):
        kvstore.commit('log_level_api', LogLevel[log_level_api.upper()])
        click.echo(f"✓ Loaded AGT_LOG_LEVEL_API: {log_level_api}")

    if peer_timeout_secs := os.environ.get('AGT_PEER_TIMEOUT_SECS'):
        kvstore.commit('peer_timeout_secs', int(peer_timeout_secs))
        click.echo(f"✓ Loaded AGT_PEER_TIMEOUT_SECS: {peer_timeout_secs}")

    if peer_refresh_secs := os.environ.get('AGT_PEER_REFRESH_SECS'):
        kvstore.commit('peer_refresh_secs', int(peer_refresh_secs))
        click.echo(f"✓ Loaded AGT_PEER_REFRESH_SECS: {peer_refresh_secs}")

    if max_weight := os.environ.get('AGT_MAX_WEIGHT'):
        kvstore.commit('max_weight', int(max_weight))
        click.echo(f"✓ Loaded AGT_MAX_WEIGHT: {max_weight}")

    if ticket_timeout_secs := os.environ.get('AGT_TICKET_TIMEOUT_SECS'):
        kvstore.commit('ticket_timeout_secs', int(ticket_timeout_secs))
        click.echo(f"✓ Loaded AGT_TICKET_TIMEOUT_SECS: {ticket_timeout_secs}")

    if message_timeout_secs := os.environ.get('AGT_MESSAGE_TIMEOUT_SECS'):
        kvstore.commit('message_timeout_secs', int(message_timeout_secs))
        click.echo(f"✓ Loaded AGT_MESSAGE_TIMEOUT_SECS: {message_timeout_secs}")


def _display_config():
    """Display current configuration settings in a formatted table."""
    click.echo("\n" + "="*50)
    click.echo("Current Configuration")
    click.echo("="*50)
    config_items = [
        ('Client Control URL',   kvstore.get('client_control_url')),
        ('Agent ID',             kvstore.get('agtuuid')),
        ('Host',                 kvstore.get('socket_host')),
        ('Port',                 kvstore.get('socket_port')),
        ('Workers',              kvstore.get('workers')),
        ('Log Path',             kvstore.get('log_path')),
        ('Log Level App',        kvstore.get('log_level_app')),
        ('Log Level API',        kvstore.get('log_level_api')),
        ('Peer Timeout Secs',    kvstore.get('peer_timeout_secs')),
        ('Peer Refresh Secs',    kvstore.get('peer_refresh_secs')),
        ('Max Weight',           kvstore.get('max_weight')),
        ('Ticket Timeout Secs',  kvstore.get('ticket_timeout_secs')),
        ('Message Timeout Secs', kvstore.get('message_timeout_secs')),
        ('Secret Digest',        kvstore.get('secret_digest').hex() if kvstore.get('secret_digest') else None),
    ]
    for key, value in config_items:
        # Truncate long values for display
        display_value = str(value)[:60] + "..." if len(str(value)) > 60 else value
        click.echo(f"{key:.<25} {display_value}")
    click.echo("="*50 + "\n")


# pylint: disable=too-many-arguments, too-many-locals, too-many-branches, too-many-statements, line-too-long, too-many-function-args, too-many-options
@click.command(help="Configure offline agent settings")
@click.option('-a', '--agtuuid',        type=str,                                                            help='Agent identifier')
@click.option('-p', '--port',           type=int,                                                            help='Server TCP port')
@click.option('-d', '--host',           type=str,                                                            help='Server host address')
@click.option('-s', '--secret',         type=str,                                                            help='Encryption key (will be hashed to 16 bytes)')
@click.option('-l', '--log-path',       type=str,                                                            help='Log output path')
@click.option('-c', '--client-url',     type=str,                                                            help='Set the agent client control URL')
@click.option('-w', '--workers',        type=int,                                                            help='Number of uvicorn worker processes')
@click.option('--log-level-app',        type=click.Choice([l.name for l in LogLevel], case_sensitive=False), help='Application log level')
@click.option('--log-level-api',        type=click.Choice([l.name for l in LogLevel], case_sensitive=False), help='FastAPI/uvicorn log level')
@click.option('--peer-timeout-secs',    type=int,                                                            help='Seconds before an unresponsive peer is considered dead')
@click.option('--peer-refresh-secs',    type=int,                                                            help='Seconds between peer refresh cycles')
@click.option('--max-weight',           type=int,                                                            help='Maximum route weight for routing decisions')
@click.option('--ticket-timeout-secs',  type=int,                                                            help='Seconds before a ticket is considered expired')
@click.option('--message-timeout-secs', type=int,                                                            help='Seconds before a pending message is discarded')
@click.option('--client-local',         is_flag=True,                                                        help='Set client control URL to local host (http://127.0.0.1:<port>/control)')
@click.option('-v', '--view',           is_flag=True,                                                        help='View current configuration settings')
@click.option('-e', '--load-env',       is_flag=True,                                                        help='Load configuration from environment variables')
def main(
    agtuuid: str | None, port: int | None, host: str | None, secret: str | None, log_path: str | None,
    client_url: str | None, workers: int | None, log_level_app: str | None, log_level_api: str | None,
    peer_timeout_secs: int | None, peer_refresh_secs: int | None, max_weight: int | None,
    ticket_timeout_secs: int | None, message_timeout_secs: int | None,
    client_local: bool, view: bool, load_env: bool
):
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
        secret_hash = hashlib.sha256(secret.encode()).digest()[:32]
        kvstore.commit('secret_digest', secret_hash)
        click.echo("✓ Set Secret (hashed to 32 bytes)")

    if client_url:
        kvstore.commit('client_control_url', client_url)
        click.echo(f"✓ Set Client Control URL: {client_url}")

    if workers:
        kvstore.commit('workers', workers)
        click.echo(f"✓ Set Workers: {workers}")

    if log_level_app:
        kvstore.commit('log_level_app', LogLevel[log_level_app.upper()])
        click.echo(f"✓ Set Log Level App: {log_level_app.upper()}")

    if log_level_api:
        kvstore.commit('log_level_api', LogLevel[log_level_api.upper()])
        click.echo(f"✓ Set Log Level API: {log_level_api.upper()}")

    if peer_timeout_secs:
        kvstore.commit('peer_timeout_secs', peer_timeout_secs)
        click.echo(f"✓ Set Peer Timeout Secs: {peer_timeout_secs}")

    if peer_refresh_secs:
        kvstore.commit('peer_refresh_secs', peer_refresh_secs)
        click.echo(f"✓ Set Peer Refresh Secs: {peer_refresh_secs}")

    if max_weight:
        kvstore.commit('max_weight', max_weight)
        click.echo(f"✓ Set Max Weight: {max_weight}")

    if ticket_timeout_secs:
        kvstore.commit('ticket_timeout_secs', ticket_timeout_secs)
        click.echo(f"✓ Set Ticket Timeout Secs: {ticket_timeout_secs}")

    if message_timeout_secs:
        kvstore.commit('message_timeout_secs', message_timeout_secs)
        click.echo(f"✓ Set Message Timeout Secs: {message_timeout_secs}")

    if client_local:
        local_url = f"http://127.0.0.1:{kvstore.get('socket_port')}/control"
        kvstore.commit('client_control_url', local_url)
        click.echo(f"✓ Set Client Control URL to local: {local_url}")

    # View configuration if requested
    if view:
        _display_config()

    # Show help message if no options provided
    if not any([agtuuid, host, port, log_path, secret, client_url, workers, log_level_app, log_level_api,
                  peer_timeout_secs, peer_refresh_secs, max_weight, ticket_timeout_secs, message_timeout_secs,
                  client_local, load_env, view]):
        click.echo("No options provided. Use --help for usage information.")


if __name__ == '__main__':
    main() # pylint: disable=no-value-for-parameter
