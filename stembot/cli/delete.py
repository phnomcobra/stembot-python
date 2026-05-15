"""delete command — remove agents from the network."""
import click

from stembot.executor.agent import AgentClient
from stembot.models.config import CONFIG
from stembot.models.control import DeletePeers


@click.command()
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
