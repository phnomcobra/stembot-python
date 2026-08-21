"""Master/user key lifecycle management: derivation, storage, expiration, and rotation.

Bootstraps a local master key in the OS keyring and uses it to wrap per-key material at
rest (AES-EAX). Manages two kinds of keys:
- User keys: derived deterministically from a passphrase shared out-of-band with a peer
  (e.g. an ESP32 provisioned over its serial console), so independent agents can arrive
  at the same key without ever exchanging it over the network.
- Auto keys: locally generated random keys used as a fallback once all user keys are
  deprecated.

A scheduled rotate() task periodically deletes expired keys and generates a new auto key
once no recently created key remains.
"""
import logging
from hashlib import pbkdf2_hmac
import secrets
from time import time

from Crypto.Cipher import AES
import rust_native_keyring as keyring

from stembot.dao.collection import Collection
from stembot.enums import KeyType
from stembot.models.crypto import Key
from stembot.scheduling import scheduled

# PBKDF2-HMAC-SHA256 rounds for passphrase-based user key derivation. Must stay
# identical across the Python, Rust, and ESP32 agents, and bounded by the
# slowest of them (ESP32) to keep bootstrap latency acceptable.
KDF_ITERATIONS               = 200_000
KDF_SALT_VERSION             = 'v1'
SERVICE_NAME                 = 'stembot'
MASTER_KEY_NAME              = 'master_key'
USER_KEY_EXPIRATION_DURATION = 600        # seconds
AUTO_KEY_EXPIRATION_DURATION = 86400 * 90 # days
DIST_KEY_EXPIRATION_DURATION = 86400 * 90 # days
KEY_DEPRECATION_DURATION     = 86400 * 30 # days
KEY_INDEX_ATTRIBUTES         = {
    'create_time': '/create_time',
    'expire_time': '/expire_time',
    'type':        '/type'
}

# Requires a running Secret Service (e.g. gnome-keyring); unavailable on headless
# hosts/containers without D-Bus, where use_named_store('sample', {...}) would be needed instead.
keyring.use_named_store('secret-service', {})


def derive_user_key(passphrase: str, objuuid: str) -> bytes:
    """Deterministically derives a volatile user key from a shared passphrase so that
    independent agents (Python, Rust, ESP32) arrive at the same key without exchanging
    a salt."""
    salt = f'stembot:user-key:{KDF_SALT_VERSION}:{objuuid}'.encode()
    return pbkdf2_hmac('sha256', passphrase.encode(), salt, KDF_ITERATIONS, dklen=32)


class KeyManager():
    """Owns the local master key and the lifecycle of derived/generated keys.

    Attributes:
        master_key: The local, OS-keyring-backed master key used to wrap all stored keys.
        keys:       The underlying Key collection, indexed by create_time and expire_time.
    """
    def __init__(self):
        """Loads or bootstraps the local master key and opens the key collection.

        Generates and stores a new master key if none exists yet in the OS keyring,
        discarding any keys wrapped under a previous master key since they can no
        longer be unwrapped. Also seeds an auto key if the collection is empty.
        """
        entry = keyring.Entry(SERVICE_NAME, MASTER_KEY_NAME)
        try:
            self.master_key = entry.get_secret()
        except RuntimeError:
            logging.warning("Master key not found, generating a new one.")
            entry.set_secret(secrets.token_bytes(32))
            self.master_key = entry.get_secret()
            Collection('keys').destroy()

        self.keys = Collection[Key]('keys')
        attributes = self.keys.list_attributes(self.keys.coluuid)
        for attr, path in KEY_INDEX_ATTRIBUTES.items():
            if attr not in attributes:
                self.keys.create_attribute(attr, path)

        if not self.keys.list_objuuids():
            logging.warning("No keys found, generating a new auto key.")
            self.create_auto_key()

    def create_user_key(self, objuuid: str, passphrase: str):
        """Derives and stores a passphrase-based key for objuuid.

        Args:
            objuuid:    The UUID identifying this key within the keys collection.
            passphrase: The shared secret used to deterministically derive the key.
        """
        logging.info("Creating a new user key with objuuid: %s", objuuid)

        decrypted_key = derive_user_key(passphrase, objuuid)

        key = self.keys.get_object(objuuid)
        key.object.create_time = create_time = time()
        key.object.expire_time = create_time + USER_KEY_EXPIRATION_DURATION
        key.object.type        = KeyType.USER

        hasher = key.object.hasher()
        hasher.update(self.master_key)
        intermediate_key = hasher.digest()

        cipher = AES.new(intermediate_key, AES.MODE_EAX)
        key.object.encrypted_key, key.object.tag = cipher.encrypt_and_digest(decrypted_key)
        key.object.nonce = cipher.nonce
        key.commit()

    def create_dist_key(self, objuuid: str, key_bytes: bytes):
        """Stores a distributed key for objuuid.

        Args:
            objuuid:    The UUID identifying this key within the keys collection.
            key_bytes:  The raw bytes of the distributed key to store.
        """
        logging.info("Creating a new distributed key with objuuid: %s", objuuid)

        key = self.keys.get_object(objuuid)
        key.object.create_time = create_time = time()
        key.object.expire_time = create_time + DIST_KEY_EXPIRATION_DURATION
        key.object.type        = KeyType.DIST

        hasher = key.object.hasher()
        hasher.update(self.master_key)
        intermediate_key = hasher.digest()

        cipher = AES.new(intermediate_key, AES.MODE_EAX)
        key.object.encrypted_key, key.object.tag = cipher.encrypt_and_digest(key_bytes)
        key.object.nonce = cipher.nonce
        key.commit()

    def create_auto_key(self):
        """Generates and stores a new random key that isn't tied to any passphrase.

        Used as a fallback once all user keys are deprecated (see all_keys_deprecated).
        """
        logging.info("Creating a new auto key.")

        key = self.keys.get_object()
        key.object.create_time = create_time = time()
        key.object.expire_time = create_time + AUTO_KEY_EXPIRATION_DURATION
        key.object.type        = KeyType.AUTO

        hasher = key.object.hasher()
        hasher.update(self.master_key)
        intermediate_key = hasher.digest()

        cipher = AES.new(intermediate_key, AES.MODE_EAX)
        decrypted_key = secrets.token_bytes(32)
        key.object.encrypted_key, key.object.tag = cipher.encrypt_and_digest(decrypted_key)
        key.object.nonce = cipher.nonce
        key.commit()

    def decrypt_key(self, objuuid: str) -> bytes:
        """Unwraps and returns the raw key material for objuuid.

        Args:
            objuuid: The UUID identifying the key to decrypt.

        Returns:
            The decrypted key bytes.

        Raises:
            KeyError: If the key has expired (it is destroyed as a side effect) or
                fails integrity verification.
        """
        key = self.keys.get_object(objuuid)

        if time() >= key.object.expire_time:
            key.destroy()
            raise KeyError(f"Key '{objuuid}' has expired")

        hasher = key.object.hasher()
        hasher.update(self.master_key)
        intermediate_key = hasher.digest()

        cipher = AES.new(intermediate_key, AES.MODE_EAX, nonce=key.object.nonce)
        try:
            decrypted_key = cipher.decrypt_and_verify(key.object.encrypted_key, key.object.tag)
        except ValueError as exc:
            raise KeyError(f"Decrypted key integrity check failed for key id '{objuuid}'") from exc

        return decrypted_key

    def get_latest_auto_key_objuuid(self) -> str | None:
        """Finds the key with the furthest-out expire_time.

        Returns:
            The latest key's objuuid, or None if no keys exist.
        """
        latest_key: Key | None = None
        for key in self.keys.find(type=KeyType.AUTO):
            if key.object.expire_time > (latest_key.object.expire_time if latest_key else 0):
                latest_key = key
        return latest_key.object.objuuid if latest_key else None

    def delete_expired_keys(self) -> None:
        """Destroys all keys whose expire_time has already passed."""
        for key in self.keys.find(expire_time=f'$lte:{time()}'):
            logging.info("Deleting expired key: %s", key.object.objuuid)
            key.destroy()

    def all_auto_keys_deprecated(self) -> bool:
        """Checks whether every auto key was created more than KEY_DEPRECATION_DURATION ago.

        Returns:
            True if no key has been created within the deprecation window.
        """
        if self.keys.find_objuuids(create_time=f'$gte:{time()-KEY_DEPRECATION_DURATION}', type=KeyType.AUTO):
            return False
        return True


@scheduled(every_secs=60)
def rotate() -> None:
    """Scheduled task that prunes expired keys and refreshes the auto key when needed."""
    manager = KeyManager()
    manager.delete_expired_keys()
    if manager.all_auto_keys_deprecated():
        manager.create_auto_key()
