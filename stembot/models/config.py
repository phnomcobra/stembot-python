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


def validate_16_bytes(value: bytes) -> bytes:
    """Validator to ensure the bytes value is exactly 16 bytes."""
    if len(value) != 16:
        raise ValueError(f'key must be exactly 16 bytes, got {len(value)} bytes')
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
    agtuuid:            Annotated[str, AfterValidator(validate_1_to_36_chars)]    = Field()
    socket_host:        Annotated[IPvAnyAddress | DomainStr, AfterValidator(str)] = Field()
    socket_port:        PositiveInt                                               = Field()
    key:                Annotated[bytes, AfterValidator(validate_16_bytes)]       = Field()
    client_control_url: Annotated[AnyUrl, AfterValidator(str)]                    = Field()
    log_path:           Annotated[str, AfterValidator(touch_log_dir)]              = Field()


def load_config():
    """Load configuration settings from the key-value store and return a Config instance."""
    global CONFIG # pylint: disable=global-statement

    if CONFIG is not None:
        return CONFIG

    CONFIG = Config(
        agtuuid=kvstore.get(name='agtuuid', default=get_uuid_str()),
        socket_host=kvstore.get(name='socket_host', default='0.0.0.0'),
        socket_port=kvstore.get(name='socket_port', default=8080),
        key=kvstore.get(name='secret_digest', default=hashlib.sha256(b'changeme').digest()[:16]),
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
    logging.debug('Current configuration: %s', lines)


load_config()
