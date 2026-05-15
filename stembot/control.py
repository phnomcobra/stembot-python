"""CLI control interface for agent management and network operations.

Entry point shim — command implementations live in stembot/cli/.
"""
from stembot.cli import main  # noqa: F401  (re-exported for pyproject.toml entry point)

if __name__ == '__main__':
    main()
