
from hashlib import sha256
import secrets
from time import time
from typing import Annotated

from Crypto.Cipher import AES
from pydantic import AfterValidator, BaseModel, Field
import rust_native_keyring as keyring

from stembot.dao.collection import Collection
from stembot.dao.utils import get_uuid_str
from stembot.models.config import validate_32_bytes


SERVICE_NAME = 'stembot'

# Requires a running Secret Service (e.g. gnome-keyring); unavailable on headless
# hosts/containers without D-Bus, where use_named_store('sample', {...}) would be needed instead.
keyring.use_named_store('secret-service', {})

class Key(BaseModel):
    id:            str                                                 = Field(default_factory=get_uuid_str)
    encrypted_key: Annotated[bytes, AfterValidator(validate_32_bytes)] = Field()
    digest:        Annotated[bytes, AfterValidator(validate_32_bytes)] = Field()
    volatile:      bool                                                = Field(default=False)
    create_time:   float                                               = Field(default_factory=time)
    expire_time:   float                                               = Field(default_factory=lambda: time() + 3600)

    objuuid:   str | None         = Field(default=None)
    coluuid:   str | None         = Field(default=None)


class KeyManager():
    def __init__(self):
        entry = keyring.Entry(SERVICE_NAME, 'master_key')
        try:
            self.master_key = entry.get_secret()
        except RuntimeError:
            entry.set_secret(secrets.token_bytes(32))
            self.master_key = entry.get_secret()

        self.keys = Collection[Key]('keys')
        self.keys.create_attribute('id', '/id')
        self.keys.create_attribute('create_time', '/create_time')
        self.keys.create_attribute('expire_time', '/expire_time')

    def create_user_key(self, key_id: str, passphrase: str):
        decrypted_key = sha256(passphrase.encode()).digest()[:32]

        cipher = AES.new(self.master_key, AES.MODE_ECB)

        key = Key(
            id=key_id,
            encrypted_key=cipher.encrypt(decrypted_key),
            digest=sha256(decrypted_key).digest(),
            volatile=True,
        )

        self.keys.upsert_object(key)
        return key




km = KeyManager()
