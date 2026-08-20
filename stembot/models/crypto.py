
import logging
from hashlib import sha256
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
from stembot.models.config import validate_32_bytes

SERVICE_NAME        = 'stembot'
MASTER_KEY_NAME     = 'master_key'
EXPIRATION_DURATION = 600.0  # seconds

# Requires a running Secret Service (e.g. gnome-keyring); unavailable on headless
# hosts/containers without D-Bus, where use_named_store('sample', {...}) would be needed instead.
keyring.use_named_store('secret-service', {})


class Key(BaseModel):
    encrypted_key: Annotated[bytes, AfterValidator(validate_32_bytes)] | None = Field(default=None)
    digest:        Annotated[bytes, AfterValidator(validate_32_bytes)] | None = Field(default=None)
    create_time:   PositiveFloat                                              = Field(default_factory=time)
    expire_time:   PositiveFloat                                              = Field(default_factory=time)
    objuuid:       str | None                                                 = Field(default_factory=get_uuid_str)
    coluuid:       str | None                                                 = Field(default=None)

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
        key = self.keys.get_object(objuuid)

        decrypted_key = sha256(passphrase.encode()).digest()[:32]

        key.object.create_time = create_time = time()
        key.object.expire_time = create_time + EXPIRATION_DURATION

        hasher = key.object.hasher()
        hasher.update(self.master_key)
        intermediate_key = hasher.digest()

        key.object.encrypted_key = AES.new(intermediate_key, AES.MODE_ECB).encrypt(decrypted_key)
        key.object.digest = sha256(decrypted_key).digest()
        key.commit()

    def decrypt_key(self, objuuid: str) -> bytes:
        key = self.keys.get_object(objuuid)

        hasher = key.object.hasher()
        hasher.update(self.master_key)
        intermediate_key = hasher.digest()

        cipher = AES.new(intermediate_key, AES.MODE_ECB)
        decrypted_key = cipher.decrypt(key.object.encrypted_key)

        if sha256(decrypted_key).digest() != key.object.digest:
            raise KeyError(f"Decrypted key digest mismatch for key id '{objuuid}'")

        return decrypted_key


km = KeyManager()
km.create_user_key('test_key', 'test_passphrase')
print(km.decrypt_key('test_key'))
