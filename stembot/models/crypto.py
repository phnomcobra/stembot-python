
import logging
from hashlib import pbkdf2_hmac, sha256
import secrets
import struct
from time import time
from typing import Annotated

from _hashlib import HASH
from Crypto.Cipher import AES
from pydantic import AfterValidator, BaseModel, Field, PositiveFloat
import rust_native_keyring as keyring

from stembot.dao.collection import Collection
from stembot.dao.utils import get_uuid_str

# PBKDF2-HMAC-SHA256 rounds for passphrase-based user key derivation. Must stay
# identical across the Python, Rust, and ESP32 agents, and bounded by the
# slowest of them (ESP32) to keep bootstrap latency acceptable.
KDF_ITERATIONS               = 200_000
KDF_SALT_VERSION             = 'v1'
SERVICE_NAME                 = 'stembot'
MASTER_KEY_NAME              = 'master_key'
USER_KEY_EXPIRATION_DURATION = 600.0  # seconds
AUTO_KEY_EXPIRATION_DURATION = 86400 * 90 # days

# Requires a running Secret Service (e.g. gnome-keyring); unavailable on headless
# hosts/containers without D-Bus, where use_named_store('sample', {...}) would be needed instead.
keyring.use_named_store('secret-service', {})


def validate_n_bytes(n: int):
    def _validate(value: bytes) -> bytes:
        if len(value) != n:
            raise ValueError(f'value must be exactly {n} bytes, got {len(value)} bytes')
        return value
    return _validate


def derive_user_key(passphrase: str, objuuid: str) -> bytes:
    """Deterministically derives a volatile user key from a shared passphrase so that
    independent agents (Python, Rust, ESP32) arrive at the same key without exchanging
    a salt."""
    salt = f'stembot:user-key:{KDF_SALT_VERSION}:{objuuid}'.encode()
    return pbkdf2_hmac('sha256', passphrase.encode(), salt, KDF_ITERATIONS, dklen=32)


class Key(BaseModel):
    encrypted_key: Annotated[bytes, AfterValidator(validate_n_bytes(32))] | None = Field(default=None)
    nonce:         Annotated[bytes, AfterValidator(validate_n_bytes(16))] | None = Field(default=None)
    tag:           Annotated[bytes, AfterValidator(validate_n_bytes(16))] | None = Field(default=None)
    create_time:   PositiveFloat                                                 = Field(default_factory=time)
    expire_time:   PositiveFloat                                                 = Field(default_factory=time)
    objuuid:       str | None                                                    = Field(default_factory=get_uuid_str)
    coluuid:       str | None                                                    = Field(default=None)

    def hasher(self) -> HASH:
        hasher = sha256()
        hasher.update(str(self.objuuid).encode())
        hasher.update(struct.pack('f', self.create_time))
        hasher.update(struct.pack('f', self.expire_time))
        return hasher


class KeyManager():
    def __init__(self):
        entry = keyring.Entry(SERVICE_NAME, MASTER_KEY_NAME)
        try:
            self.master_key = entry.get_secret()
        except RuntimeError:
            logging.warning("Master key not found, generating a new one.")
            entry.set_secret(secrets.token_bytes(32))
            self.master_key = entry.get_secret()
            Collection('keys').destroy()

        self.keys = Collection[Key]('keys')
        self.keys.create_attribute('create_time', '/create_time')
        self.keys.create_attribute('expire_time', '/expire_time')

    def create_user_key(self, objuuid: str, passphrase: str):
        """Derives and stores a fresh key for objuuid's next generation."""
        decrypted_key = derive_user_key(passphrase, objuuid)

        key = self.keys.get_object(objuuid)
        key.object.create_time = create_time = time()
        key.object.expire_time = create_time + USER_KEY_EXPIRATION_DURATION

        hasher = key.object.hasher()
        hasher.update(self.master_key)
        intermediate_key = hasher.digest()

        cipher = AES.new(intermediate_key, AES.MODE_GCM)
        key.object.encrypted_key, key.object.tag = cipher.encrypt_and_digest(decrypted_key)
        key.object.nonce = cipher.nonce
        key.commit()

    def create_auto_key(self):
        key = self.keys.get_object()
        key.object.create_time = create_time = time()
        key.object.expire_time = create_time + AUTO_KEY_EXPIRATION_DURATION

        hasher = key.object.hasher()
        hasher.update(self.master_key)
        intermediate_key = hasher.digest()

        cipher = AES.new(intermediate_key, AES.MODE_GCM)
        decrypted_key = secrets.token_bytes(32)
        key.object.encrypted_key, key.object.tag = cipher.encrypt_and_digest(decrypted_key)
        key.object.nonce = cipher.nonce
        key.commit()

    def decrypt_key(self, objuuid: str) -> bytes:
        key = self.keys.get_object(objuuid)

        if time() >= key.object.expire_time:
            raise KeyError(f"Key '{objuuid}' has expired")

        hasher = key.object.hasher()
        hasher.update(self.master_key)
        intermediate_key = hasher.digest()

        cipher = AES.new(intermediate_key, AES.MODE_GCM, nonce=key.object.nonce)
        try:
            decrypted_key = cipher.decrypt_and_verify(key.object.encrypted_key, key.object.tag)
        except ValueError as exc:
            raise KeyError(f"Decrypted key integrity check failed for key id '{objuuid}'") from exc

        return decrypted_key


km = KeyManager()
km.create_user_key('test_key', 'test_passphrase')
print(km.decrypt_key('test_key'))
