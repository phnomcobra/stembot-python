"""CLI package for agent control and network management.

Assembles the `main` click group from individual command modules.
"""
import click

from stembot.cli.bench import bench
from stembot.cli.delete import delete
from stembot.cli.discover import discover
from stembot.cli.put import put
from stembot.cli.run import run
from stembot.cli.stat import stat


@click.group(help='Agent control and network management')
def main():
    """CLI entry point for agent control and network management.

    Provides command-line interface for discovering peers, managing agent
    topology, querying statistics, benchmarking performance, and executing
    remote operations on stembot agents.
    """


main.add_command(bench)
main.add_command(delete)
main.add_command(discover)
main.add_command(put)
main.add_command(run)
main.add_command(stat)
