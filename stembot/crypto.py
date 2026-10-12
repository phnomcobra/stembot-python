"""Master/user key lifecycle management: derivation, storage, expiration, and rotation.
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
import platform
import secrets
from time import time
from typing import List

from Crypto.Cipher import AES
import rust_native_keyring as keyring

from stembot.dao.collection import Collection
from stembot.enums import KeyType
from stembot.models.crypto import Key, KeyDistribution, KeyMetadata

# PBKDF2-HMAC-SHA256 rounds for passphrase-based user key derivation. Must stay
# identical across the Python, Rust, and ESP32 agents, and bounded by the
# slowest of them (ESP32) to keep bootstrap latency acceptable.
KDF_ITERATIONS               = 200_000
KDF_SALT_VERSION             = 'v1'
SERVICE_NAME                 = 'stembot'
MASTER_KEY_NAME              = 'master_key'
USER_KEY_EXPIRATION_DURATION = 600        # seconds
AUTO_KEY_EXPIRATION_DURATION = 86400 * 90 # days
KEY_DEPRECATION_DURATION     = 86400 * 30 # days
KEY_INDEX_ATTRIBUTES         = {
    'create_time': '/create_time',
    'expire_time': '/expire_time',
    'agtuuid':     '/agtuuid',
    'type':        '/type'
}
# Lower values are preferred by resolve_keys() when choosing among candidate keys.
KEY_TYPE_PRIORITY = {
    KeyType.DIST: 0,
    KeyType.USER: 1,
    KeyType.AUTO: 2,
}

# Maps platform.system() to the rust_native_keyring store backend that can actually
# back the OS-native credential store on that platform. Linux's 'secret-service' requires
# a running Secret Service (e.g. gnome-keyring) and is unavailable on headless hosts/containers
# without D-Bus, in which case _use_native_keyring_store() falls back to KEYRING_STORE_BACKING_FILE.
KEYRING_STORE_BY_PLATFORM = {
    'Darwin':  'keychain',
    'Linux':   'secret-service',
    'Windows': 'windows',
}
# Portable, file-backed keyring store used as a fallback when no OS-native
# credential store is reachable (e.g. containers without D-Bus/Secret Service).
KEYRING_STORE_BACKING_FILE = 'keyring.ron'


def _use_native_keyring_store() -> None:
    """Configures rust_native_keyring to use the OS-native store for the current platform.

    Falls back to the portable, file-backed 'sample' store if the OS-native backend
    fails to initialize, which is expected in containers/headless hosts lacking a
    D-Bus session or Secret Service (e.g. no DBUS_SESSION_BUS_ADDRESS).

    Raises:
        RuntimeError: If the current platform has no known native store backend.
    """
    system = platform.system()
    store_name = KEYRING_STORE_BY_PLATFORM.get(system)
    if store_name is None:
        raise RuntimeError(
            f"No supported OS keyring backend is known for platform '{system}'"
        )

    try:
        keyring.use_named_store(store_name, {})
    except RuntimeError as exc:
        logging.warning(
            "Failed to initialize the '%s' OS keyring backend on %s (%s); "
            "falling back to the portable file-backed store at '%s'.",
            store_name, system, exc, KEYRING_STORE_BACKING_FILE
        )
        keyring.use_named_store('sample', {'backing-file': KEYRING_STORE_BACKING_FILE})



_use_native_keyring_store()


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

        self.kc = Collection[Key]('keys')
        attributes = self.kc.list_attributes(self.kc.coluuid)
        for attr, path in KEY_INDEX_ATTRIBUTES.items():
            if attr not in attributes:
                self.kc.create_attribute(attr, path)

        if not self.kc.list_objuuids():
            logging.warning("No keys found, generating a new auto key.")
            self.create_auto_key()

    def create_user_key(self, objuuid: str, passphrase: str, agtuuid: str | None = None):
        """Derives and stores a passphrase-based key for objuuid.

        Args:
            objuuid:    The UUID identifying this key within the keys collection.
            passphrase: The shared secret used to deterministically derive the key.
            agtuuid:    The agent UUID associated with this key, if any.
        """
        logging.info("Creating a new user key with objuuid: %s", objuuid)

        decrypted_key = derive_user_key(passphrase, objuuid)

        key = self.kc.get_object(objuuid)
        key.object.create_time = create_time = time()
        key.object.expire_time = create_time + USER_KEY_EXPIRATION_DURATION
        key.object.type        = KeyType.USER
        key.object.agtuuid     = agtuuid

        hasher = key.object.hasher()
        hasher.update(self.master_key)
        intermediate_key = hasher.digest()

        cipher = AES.new(intermediate_key, AES.MODE_EAX)
        key.object.encrypted_key, key.object.tag = cipher.encrypt_and_digest(decrypted_key)
        key.object.nonce = cipher.nonce
        key.commit()

    def create_dist_key(self, objuuid: str, key_bytes: bytes, agtuuid: str, ttl: float):
        """Stores a distributed key for objuuid.

        Args:
            objuuid:   The UUID identifying this key within the keys collection.
            key_bytes: The raw bytes of the distributed key to store.
            agtuuid:   The agent UUID associated with this key.
            ttl:       The time-to-live (TTL) in seconds for which this key is valid.
        """
        logging.info("Creating a new distributed key with objuuid: %s", objuuid)

        key = self.kc.get_object(objuuid)
        key.object.create_time = create_time = time()
        key.object.expire_time = create_time + ttl
        key.object.type        = KeyType.DIST
        key.object.agtuuid     = agtuuid

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

        key = self.kc.get_object()
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
        key = self.kc.get_object(objuuid)

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
            key.destroy()
            raise KeyError(f"Decrypted key integrity check failed for key id '{objuuid}'") from exc

        return decrypted_key

    def resolve_key_objuuid(self, agtuuid: str | None=None) -> str | None:
        """Resolves the key associated with the given agent UUID.

        Args:
            agtuuid: The agent UUID for which to resolve the key.

        Returns:
            The UUID of the resolved key, or None if no key could be resolved.
        """
        keys: list[Key] = []

        for key in self.kc.find(agtuuid=agtuuid):
            keys.append(key)

        # agt-control will need this when talking to a local agent and peering new agents
        for key in self.kc.find(agtuuid=None):
            keys.append(key)

        if not keys:
            return None

        keys.sort(key=lambda key: (KEY_TYPE_PRIORITY[key.object.type], -key.object.expire_time))

        return keys[0].object.objuuid

    def delete_expired_keys(self) -> None:
        """Destroys all keys whose expire_time has already passed."""
        for key in self.kc.find(expire_time=f'$lte:{time()}'):
            logging.info("Deleting expired key: %s", key.object.objuuid)
            key.destroy()

    def create_key_distributions(self) -> list[KeyDistribution]:
        """Creates key distribution records for all relevant auto keys that have not expired.

        Returns:
            A list of KeyDistribution objects.
        """
        distributions = []
        for key in self.kc.find(type=KeyType.AUTO, expire_time=f'$gte:{time()}'):
            try:
                distributions.append(
                    KeyDistribution(
                        key=self.decrypt_key(objuuid=key.object.objuuid),
                        objuuid=key.object.objuuid,
                        ttl=key.object.expire_time - time()
                    )
                )
            except KeyError as exc:
                logging.warning("Failed to create key distribution for key id '%s': %s", key.object.objuuid, exc)
        return distributions

    def process_key_distributions(self, distributions: list[KeyDistribution], agtuuid: str) -> None:
        """Processes a received key distribution record by storing the distributed key.

        Args:
            distributions: A list of KeyDistribution objects to process.
            agtuuid:       The agent UUID associated with the received key distributions.
        """
        for distribution in distributions:
            self.create_dist_key(
                agtuuid=agtuuid,
                objuuid=distribution.objuuid,
                key_bytes=distribution.key,
                ttl=distribution.ttl
            )

    def describe(self) -> List[KeyMetadata]:
        """Provides a list of metadata for all keys.

        Returns:
            A list of KeyMetadata objects describing each key.
        """
        return [key.object.describe() for key in self.kc.find()]

    @property
    def all_auto_keys_deprecated(self) -> bool:
        """Checks whether every auto key was created more than KEY_DEPRECATION_DURATION ago.

        Returns:
            True if no key has been created within the deprecation window.
        """
        if self.kc.find_objuuids(create_time=f'$gte:{time()-KEY_DEPRECATION_DURATION}', type=KeyType.AUTO):
            return False
        return True
