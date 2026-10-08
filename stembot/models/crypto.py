"""Pydantic model for an encrypted key record persisted by KeyManager (see stembot.crypto)."""
import base64
import binascii
from hashlib import sha256
import struct
from typing import Annotated

from _hashlib import HASH
from pydantic import AfterValidator, BaseModel, Field, PositiveFloat

from stembot.dao.utils import get_uuid_str
from stembot.enums import KeyType


def validate_n_bytes(n: int):
    """Builds a pydantic AfterValidator enforcing that a bytes field is exactly n bytes long.

    Args:
        n:
            The required length in bytes.

    Returns:
        A validator function suitable for use with pydantic's AfterValidator.
    """
    def _validate(value: bytes) -> bytes:
        if len(value) != n:
            raise ValueError(f'value must be exactly {n} bytes, got {len(value)} bytes')
        return value
    return _validate


def validate_b64_n_bytes(n: int):
    """Builds a pydantic AfterValidator enforcing that a string is valid base64 decoding to n bytes.

    Args:
        n:
            The required decoded length in bytes.

    Returns:
        A validator function suitable for use with pydantic's AfterValidator.
    """
    def _validate(value: str) -> str:
        try:
            decoded = base64.b64decode(value, validate=True)
        except binascii.Error as exc:
            raise ValueError('value must be a valid base64-encoded string') from exc
        if len(decoded) != n:
            raise ValueError(f'decoded value must be exactly {n} bytes, got {len(decoded)} bytes')
        return value
    return _validate


class KeyDistribution(BaseModel):
    """An unencrypted key record used to distribute a cryptographic key to an agent.

    Attributes:
        b64_key:       The base64-encoded distributed key.
        objuuid:       The object UUID identifying this key within its collection.
        duration_secs: The duration in seconds for which this key is valid.
    """
    b64_key:       Annotated[str, AfterValidator(validate_b64_n_bytes(32))] = Field()
    objuuid:       str                                                      = Field()
    duration_secs: PositiveFloat                                            = Field()

    def __init__(self, /, **data):
        """An unencrypted key record used to distribute a cryptographic key to an agent.

        Attributes:
            key:           The decrypted key bytes.
            objuuid:       The object UUID identifying this key within its collection.
            duration_secs: The duration in seconds for which this key is valid.
        """
        if 'key' in data:
            data['b64_key'] = base64.b64encode(data.pop('key')).decode('ascii')
        super().__init__(**data)

    @property
    def key(self) -> bytes:
        """Returns the raw decrypted key bytes."""
        return base64.b64decode(self.b64_key)


# pylint: disable=line-too-long
class Key(BaseModel):
    """An encrypted key record.

    encrypted_key holds the AES-EAX ciphertext of a decrypted key, wrapped under an
    intermediate key derived from the KeyManager's local master key (see hasher()).
    nonce and tag are the accompanying AES-EAX nonce and authentication tag.

    Attributes:
        encrypted_key: The wrapped key ciphertext, or None if not yet set.
        nonce:         The AES-EAX nonce used to wrap encrypted_key.
        tag:           The AES-EAX authentication tag for encrypted_key.
        create_time:   Unix timestamp when this key was created.
        expire_time:   Unix timestamp after which this key is no longer valid.
        type:          The type of key (USER, AUTO, or DIST).
        agtuuid:       The agent UUID associated with this key, if any.
        objuuid:       The object UUID identifying this key within its collection.
        coluuid:       The UUID of the collection this key belongs to.
    """
    encrypted_key: Annotated[bytes, AfterValidator(validate_n_bytes(32))] | None = Field(default=None)
    nonce:         Annotated[bytes, AfterValidator(validate_n_bytes(16))] | None = Field(default=None)
    tag:           Annotated[bytes, AfterValidator(validate_n_bytes(16))] | None = Field(default=None)
    create_time:   PositiveFloat                                                 = Field(default=0.0)
    expire_time:   PositiveFloat                                                 = Field(default=0.0)
    type:          KeyType                                                       = Field(default=KeyType.AUTO)
    agtuuid:       str | None                                                    = Field(default=None)
    objuuid:       str | None                                                    = Field(default_factory=get_uuid_str)
    coluuid:       str | None                                                    = Field(default=None)

    def hasher(self) -> HASH:
        """Builds a SHA-256 hash of this key's identity and lifetime.

        This is the basis for the intermediate key that wraps encrypted_key; the
        caller must still feed in the master key before calling digest()/hexdigest().

        Returns:
            A SHA-256 hash object updated with objuuid, agtuuid, type, create_time, and expire_time.
        """
        hasher = sha256()
        hasher.update(str(self.coluuid).encode())
        hasher.update(str(self.objuuid).encode())
        hasher.update(str(self.agtuuid).encode())
        hasher.update(str(self.type).encode())
        hasher.update(struct.pack('f', self.create_time))
        hasher.update(struct.pack('f', self.expire_time))
        return hasher
