"""Pydantic model for an encrypted key record persisted by KeyManager (see stembot.crypto)."""
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
        objuuid:       The object UUID identifying this key within its collection.
        coluuid:       The UUID of the collection this key belongs to.
    """
    encrypted_key: Annotated[bytes, AfterValidator(validate_n_bytes(32))] | None = Field(default=None)
    nonce:         Annotated[bytes, AfterValidator(validate_n_bytes(16))] | None = Field(default=None)
    tag:           Annotated[bytes, AfterValidator(validate_n_bytes(16))] | None = Field(default=None)
    create_time:   PositiveFloat                                                 = Field(default=0.0)
    expire_time:   PositiveFloat                                                 = Field(default=0.0)
    type:          KeyType                                                       = Field(default=KeyType.AUTO)
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
        hasher.update(str(self.objuuid).encode())
        hasher.update(str(self.type).encode())
        hasher.update(struct.pack('f', self.create_time))
        hasher.update(struct.pack('f', self.expire_time))
        return hasher
