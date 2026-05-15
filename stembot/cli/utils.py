"""Shared formatting utilities for the CLI."""

KB = 1024
MB = 1024 * 1024
GB = 1024 * 1024 * 1024


def format_bytes(num_bytes: int | float) -> str:
    """Convert bytes to human-readable format (B, KB, MB, or GB).

    Args:
        num_bytes: Number of bytes to format

    Returns:
        Formatted string with appropriate unit
    """
    num_bytes = float(num_bytes)
    # pylint: disable=too-many-branches, too-many-return-statements
    if num_bytes < KB:
        return f"{num_bytes:.0f} B"
    if num_bytes < MB:
        return f"{num_bytes / KB:.1f} KB"
    if num_bytes < GB:
        return f"{num_bytes / MB:.1f} MB"
    return f"{num_bytes / GB:.1f} GB"


def format_bandwidth(bytes_per_second: int | float) -> str:
    """Convert bytes per second to human-readable format (B/s, KB/s, MB/s, or GB/s).

    Args:
        bytes_per_second: Transfer rate in bytes per second

    Returns:
        Formatted string with appropriate unit
    """
    bytes_per_second = float(bytes_per_second)
    # pylint: disable=too-many-branches, too-many-return-statements
    if bytes_per_second < KB:
        return f"{bytes_per_second:.0f} B/s"
    if bytes_per_second < MB:
        return f"{bytes_per_second / KB:.1f} KB/s"
    if bytes_per_second < GB:
        return f"{bytes_per_second / MB:.1f} MB/s"
    return f"{bytes_per_second / GB:.1f} GB/s"
