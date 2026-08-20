
import logging
from hashlib import sha256
from _hashlib import HASH
import secrets
import struct
from time import time
from typing import Annotated

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


class KeyAlreadyExistsError(KeyError):
    pass


class KeyNotFoundError(KeyError):
    pass


class KeyIntegrityError(KeyError):
    pass


class Key(BaseModel):
    id:            str                                                        = Field(default_factory=get_uuid_str)
    encrypted_key: Annotated[bytes, AfterValidator(validate_32_bytes)] | None = Field(default=None)
    digest:        Annotated[bytes, AfterValidator(validate_32_bytes)] | None = Field(default=None)
    create_time:   PositiveFloat                                              = Field(default_factory=time)
    expire_time:   PositiveFloat                                              = Field(default_factory=time)
    objuuid:       str | None                                                 = Field(default=None)
    coluuid:       str | None                                                 = Field(default=None)

    def hasher(self) -> HASH:
        hasher = sha256()
        hasher.update(str(self.id).encode())
        hasher.update(struct.pack('f', self.create_time))
        hasher.update(struct.pack('f', self.expire_time))
        return hasher


class KeyManager():
    def __init__(self):
        self.keys = Collection[Key]('keys')
        self.keys.create_attribute('id', '/id')
        self.keys.create_attribute('create_time', '/create_time')
        self.keys.create_attribute('expire_time', '/expire_time')

        entry = keyring.Entry(SERVICE_NAME, MASTER_KEY_NAME)
        try:
            self.master_key = entry.get_secret()
        except RuntimeError:
            logging.warning("Master key not found, generating a new one.")
            entry.set_secret(secrets.token_bytes(32))
            self.master_key = entry.get_secret()

    def create_user_key(self, key_id: str, passphrase: str):
        if objuuids := self.keys.find_objuuids(id=key_id):
            raise KeyAlreadyExistsError(f"Key with id '{key_id}' already exists: {objuuids}")

        decrypted_key = sha256(passphrase.encode()).digest()[:32]

        create_time = time()
        expire_time = create_time + EXPIRATION_DURATION

        key = Key(
            id=key_id,
            create_time=create_time,
            expire_time=expire_time
        )

        hasher = key.hasher()
        hasher.update(self.master_key)
        intermediate_key = hasher.digest()

        key.encrypted_key = AES.new(intermediate_key, AES.MODE_ECB).encrypt(decrypted_key)
        key.digest = sha256(decrypted_key).digest()

        self.keys.upsert_object(key)

    def decrypt_key(self, key_id: str) -> bytes:
        if results := self.keys.find(id=key_id):
            key = results[0].object
        else:
            raise KeyNotFoundError(f"Key with id '{key_id}' not found")

        hasher = key.hasher()
        hasher.update(self.master_key)
        intermediate_key = hasher.digest()

        cipher = AES.new(intermediate_key, AES.MODE_ECB)
        decrypted_key = cipher.decrypt(key.encrypted_key)

        key.digest = sha256(decrypted_key).digest()
        if sha256(decrypted_key).digest() != key.digest:
            raise KeyIntegrityError(f"Decrypted key digest mismatch for key id '{key_id}'")

        return decrypted_key


km = KeyManager()
km.create_user_key('test_key', 'test_passphrase')
print(km.decrypt_key('test_key'))
