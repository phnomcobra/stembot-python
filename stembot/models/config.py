import hashlib
import logging
import os
from pathlib import Path

from typing import Annotated

from pydantic import AfterValidator, AnyUrl, BaseModel, Field, IPvAnyAddress, PositiveInt
from pydantic_extra_types.domain import DomainStr

from stembot.dao import kvstore
from stembot.dao.utils import get_uuid_str

CONFIG = None


def validate_32_bytes(value: bytes) -> bytes:
    """Validator to ensure the bytes value is exactly 32 bytes."""
    if len(value) != 32:
        raise ValueError(f'key must be exactly 32 bytes, got {len(value)} bytes')
    return value


def validate_1_to_36_chars(value: str) -> str:
    """Validator to ensure the agtuuid is a valid UUID string."""
    if not 1 <= len(value) <= 36:
        raise ValueError(f'agtuuid must be between 1 and 36 characters, got {len(value)}')
    return value


def touch_log_dir(log_path: str) -> str:
    """Validator to ensure the log directory is valid and can be created if it does not exist."""
    log_path = os.path.expanduser(log_path)
    log_dir  = os.path.dirname(log_path)

    if log_dir and not os.path.exists(log_dir):
        try:
            Path(log_dir).mkdir(parents=True, exist_ok=True)
        except Exception as exception:
            raise ValueError(f'Could not create log directory: {exception}') from exception

    return log_path


class Config(BaseModel):
    """Configuration settings for the StemBot distributed agent framework.

    This class encapsulates all runtime configuration for a StemBot agent instance.
    Configuration values are persisted in the key-value store and loaded automatically
    on module import via load_config().

    The Config instance is stored in the module-level CONFIG variable and serves as
    the single source of truth for agent configuration throughout the application.

    Attributes:
        agtuuid: Unique identifier for this agent (UUID string, 1-36 characters).
                 Identifies this agent in the distributed network. Generated randomly
                 if not persisted.
        socket_host: IP address or domain name to bind the HTTP server to.
                    Can be IPv4, IPv6, or a domain name. Defaults to '0.0.0.0' (all interfaces).
        socket_port: Port number for the HTTP server (1-65535). Defaults to 8080.
        key: 32-byte encryption key (AES-256) for message encryption/decryption.
             Must be exactly 32 bytes. Defaults to SHA256(b'changeme').
             IMPORTANT: Change this value in production for security.
        client_control_url: URL where the control client can reach this agent.
                           Used for peer and client communication. Typically in format
                           'http://host:port' or 'https://host:port'.
        log_path: File path for application log file. Supports ~ expansion for home directory.
                 Directory is created if it doesn't exist. Defaults to '~/.stembot/logs'.
        peer_timeout_secs: Seconds before an unresponsive peer is considered dead (default: 60).
        peer_refresh_secs: Seconds between peer refresh cycles (default: 30).
        max_weight: Maximum weight value for routes in routing decisions (default: 600).
        ticket_timeout_secs: Seconds before a ticket is considered expired (default: 600).
        message_timeout_secs: Seconds before a pending message is discarded (default: 600).

    Example:
        The Config is automatically loaded on import:
            from stembot.models.config import CONFIG
            print(CONFIG.agtuuid)
            print(CONFIG.socket_host)
    """
    agtuuid:              Annotated[str, AfterValidator(validate_1_to_36_chars)]    = Field()
    socket_host:          Annotated[IPvAnyAddress | DomainStr, AfterValidator(str)] = Field()
    socket_port:          PositiveInt                                               = Field()
    key:                  Annotated[bytes, AfterValidator(validate_32_bytes)]       = Field()
    client_control_url:   Annotated[AnyUrl, AfterValidator(str)]                    = Field()
    log_path:             Annotated[str, AfterValidator(touch_log_dir)]             = Field()
    peer_timeout_secs:    PositiveInt                                               = Field(default=60)
    peer_refresh_secs:    PositiveInt                                               = Field(default=30)
    max_weight:           PositiveInt                                               = Field(default=600)
    ticket_timeout_secs:  PositiveInt                                               = Field(default=600)
    message_timeout_secs: PositiveInt                                               = Field(default=600)


def load_config():
    """Load configuration settings from the key-value store and return a Config instance."""
    global CONFIG # pylint: disable=global-statement

    if CONFIG is not None:
        return CONFIG

    CONFIG = Config(
        agtuuid=kvstore.get(name='agtuuid', default=get_uuid_str()),
        socket_host=kvstore.get(name='socket_host', default='0.0.0.0'),
        socket_port=kvstore.get(name='socket_port', default=8080),
        key=kvstore.get(name='secret_digest', default=hashlib.sha256(b'changeme').digest()[:32]),
        client_control_url=kvstore.get(name='client_control_url', default='http://localhost:8080'),
        log_path=kvstore.get(name='log_path', default='~/.stembot/logs')
    )


def log_config():
    """Log the current configuration settings."""
    lines = "\n"
    for field_name, field_value in CONFIG.model_dump().items():
        if isinstance(field_value, bytes):
            field_value = field_value.hex()
        lines += f'  {field_name}: {field_value}\n'
    logging.info(lines)


load_config()
