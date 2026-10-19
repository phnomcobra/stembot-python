"""Unit tests for stembot.crypto (master/user key lifecycle management).

These tests mock the OS keyring (rust_native_keyring) with an in-memory fake so
that no real OS credential store is touched and every test is isolated. Each
test runs inside its own temporary directory so that the 'keys' sqlite-backed
collection never collides across tests or with developer state.

The derive_user_key test embeds a hardcoded PBKDF2-HMAC-SHA256 reference vector;
this value (and the salt format: 'stembot:user-key:v1:{objuuid}') must be
reproduced byte-for-byte by any port of this module (e.g. stembot-rust).
"""
import os
import tempfile
import unittest
from unittest.mock import patch

import stembot.crypto as crypto_module
from stembot.crypto import (
    AUTO_KEY_EXPIRATION_DURATION,
    KEYRING_STORE_BACKING_FILE,
    MASTER_KEY_NAME,
    SERVICE_NAME,
    USER_KEY_EXPIRATION_DURATION,
    KeyManager,
    configure_keyring_store,
    derive_user_key,
)
from stembot.enums import KeyType
from stembot.models.crypto import KeyDistribution


class _FakeEntry:
    """Fake stand-in for rust_native_keyring.Entry, backed by a plain dict."""

    def __init__(self, store: dict, service: str, username: str):
        self._store = store
        self._key = (service, username)

    def get_secret(self) -> bytes:
        if self._key not in self._store:
            raise RuntimeError(f"no secret found for {self._key}")
        return self._store[self._key]

    def set_secret(self, secret: bytes) -> None:
        self._store[self._key] = secret


class _FakeKeyring:
    """Fake stand-in for the rust_native_keyring module.

    Backed by a single dict representing "whatever store is currently active",
    which is sufficient to exercise KeyManager's bootstrap logic without ever
    touching a real OS credential store.
    """

    def __init__(self):
        self.store = {}
        self.use_named_store_calls = []
        self.release_store_calls = 0
        self.fail_use_named_store_for = set()

    def Entry(self, service: str, username: str) -> _FakeEntry:  # pylint: disable=invalid-name
        return _FakeEntry(self.store, service, username)

    def use_named_store(self, name: str, config: dict) -> None:
        self.use_named_store_calls.append((name, config))
        if name in self.fail_use_named_store_for:
            raise RuntimeError(f"store '{name}' unavailable")

    def release_store(self) -> None:
        self.release_store_calls += 1


class KeyManagerTestCase(unittest.TestCase):
    """Base test case providing an isolated tempdir and a fake keyring."""

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.old_cwd = os.getcwd()
        os.chdir(self.tempdir.name)

        self.fake_keyring = _FakeKeyring()
        self.keyring_patch = patch('stembot.crypto.keyring', self.fake_keyring)
        # Exercise the file-backed branch, matching the containerized deployment path.
        self.backing_file_patch = patch('stembot.crypto.KEYRING_STORE_BACKING_FILE_IN_USE', True)
        self.keyring_patch.start()
        self.backing_file_patch.start()

        self.addCleanup(self.keyring_patch.stop)
        self.addCleanup(self.backing_file_patch.stop)
        self.addCleanup(os.chdir, self.old_cwd)
        self.addCleanup(self.tempdir.cleanup)


# ---------------------------------------------------------------------------
# derive_user_key
# ---------------------------------------------------------------------------

class TestDeriveUserKey(unittest.TestCase):
    """Verify deterministic passphrase-based key derivation.

    Reference vector (must match stembot-rust byte-for-byte):
        passphrase = 'correct horse battery staple'
        objuuid    = 'peer-mesh-01'
        salt       = b'stembot:user-key:v1:peer-mesh-01'
        iterations = 200_000
        dklen      = 32
    """

    REFERENCE_PASSPHRASE = 'correct horse battery staple'
    REFERENCE_OBJUUID = 'peer-mesh-01'
    REFERENCE_HEX = '698a94e2fdec5200113e6ed8d89e8a7b9a4ef6041e0d0e063d87e9e7108ccee5'

    def test_matches_reference_vector(self):
        key = derive_user_key(self.REFERENCE_PASSPHRASE, self.REFERENCE_OBJUUID)
        self.assertEqual(key.hex(), self.REFERENCE_HEX)

    def test_is_32_bytes(self):
        key = derive_user_key('passphrase', 'obj1')
        self.assertEqual(len(key), 32)

    def test_is_deterministic(self):
        key_a = derive_user_key('passphrase', 'obj1')
        key_b = derive_user_key('passphrase', 'obj1')
        self.assertEqual(key_a, key_b)

    def test_differs_by_passphrase(self):
        key_a = derive_user_key('passphrase-a', 'obj1')
        key_b = derive_user_key('passphrase-b', 'obj1')
        self.assertNotEqual(key_a, key_b)

    def test_differs_by_objuuid(self):
        key_a = derive_user_key('passphrase', 'obj1')
        key_b = derive_user_key('passphrase', 'obj2')
        self.assertNotEqual(key_a, key_b)


# ---------------------------------------------------------------------------
# configure_keyring_store
# ---------------------------------------------------------------------------

class TestConfigureKeyringStore(unittest.TestCase):
    """Verify OS-native store selection and fallback to the file-backed store."""

    def setUp(self):
        self.fake_keyring = _FakeKeyring()
        self.keyring_patch = patch('stembot.crypto.keyring', self.fake_keyring)
        self.keyring_patch.start()
        self.addCleanup(self.keyring_patch.stop)

    def test_uses_native_store_for_known_platform(self):
        with patch('stembot.crypto.platform.system', return_value='Linux'), \
             patch('stembot.crypto.KEYRING_STORE_BACKING_FILE_IN_USE', False):
            configure_keyring_store()
        self.assertEqual(self.fake_keyring.use_named_store_calls, [('secret-service', {})])

    def test_falls_back_to_file_backed_store_on_failure(self):
        self.fake_keyring.fail_use_named_store_for.add('secret-service')
        with patch('stembot.crypto.platform.system', return_value='Linux'), \
             patch('stembot.crypto.KEYRING_STORE_BACKING_FILE_IN_USE', False):
            configure_keyring_store()
            self.assertTrue(crypto_module.KEYRING_STORE_BACKING_FILE_IN_USE)
        self.assertEqual(
            self.fake_keyring.use_named_store_calls,
            [('secret-service', {}), ('sample', {'backing-file': KEYRING_STORE_BACKING_FILE})],
        )

    def test_raises_for_unsupported_platform(self):
        with patch('stembot.crypto.platform.system', return_value='Plan9'):
            with self.assertRaises(RuntimeError):
                configure_keyring_store()
        self.assertEqual(self.fake_keyring.use_named_store_calls, [])


# ---------------------------------------------------------------------------
# KeyManager.__init__
# ---------------------------------------------------------------------------

class TestKeyManagerInit(KeyManagerTestCase):
    """Verify master key bootstrap and auto key seeding."""

    def test_generates_master_key_when_missing(self):
        km = KeyManager()
        self.assertEqual(len(km.master_key), 32)
        self.assertEqual(self.fake_keyring.store[(SERVICE_NAME, MASTER_KEY_NAME)], km.master_key)

    def test_seeds_auto_key_when_collection_empty(self):
        km = KeyManager()
        metadata = km.describe()
        self.assertEqual(len(metadata), 1)
        self.assertEqual(metadata[0].type, KeyType.AUTO)

    def test_reuses_existing_master_key_and_keys(self):
        first = KeyManager()
        first_master_key = first.master_key
        first_objuuids = set(first.kc.list_objuuids())

        second = KeyManager()

        self.assertEqual(second.master_key, first_master_key)
        self.assertEqual(set(second.kc.list_objuuids()), first_objuuids)

    def test_discards_keys_when_master_key_is_missing_on_restart(self):
        first = KeyManager()
        first.create_user_key(objuuid='k1', passphrase='pw')
        self.assertEqual(len(first.describe()), 2)

        # Simulate total loss of the master key (e.g. keyring wiped).
        self.fake_keyring.store.clear()

        second = KeyManager()
        self.assertNotEqual(second.master_key, first.master_key)
        # Old keys are unreadable under the new master key, so the collection was discarded
        # and reseeded with exactly one fresh auto key.
        self.assertEqual(len(second.describe()), 1)
        self.assertEqual(second.describe()[0].type, KeyType.AUTO)


# ---------------------------------------------------------------------------
# create_user_key / create_dist_key / create_auto_key / decrypt_key
# ---------------------------------------------------------------------------

class TestKeyCreationAndDecryption(KeyManagerTestCase):
    """Verify key creation, round-trip decryption, and failure handling."""

    def test_create_user_key_round_trips(self):
        km = KeyManager()
        km.create_user_key(objuuid='k1', passphrase='pw', agtuuid='agentA')

        decrypted = km.decrypt_key('k1')

        self.assertEqual(decrypted, derive_user_key('pw', 'k1'))

        metadata = next(m for m in km.describe() if m.objuuid == 'k1')
        self.assertEqual(metadata.type, KeyType.USER)
        self.assertEqual(metadata.agtuuid, 'agentA')
        self.assertLessEqual(metadata.ttl, USER_KEY_EXPIRATION_DURATION)
        self.assertGreater(metadata.ttl, 0)

    def test_create_dist_key_round_trips(self):
        km = KeyManager()
        key_bytes = b'd' * 32
        km.create_dist_key(objuuid='d1', key_bytes=key_bytes, agtuuid='agentB', ttl=120.0)

        decrypted = km.decrypt_key('d1')

        self.assertEqual(decrypted, key_bytes)
        metadata = next(m for m in km.describe() if m.objuuid == 'd1')
        self.assertEqual(metadata.type, KeyType.DIST)
        self.assertEqual(metadata.agtuuid, 'agentB')
        self.assertLessEqual(metadata.ttl, 120.0)

    def test_create_auto_key_adds_a_new_random_key(self):
        km = KeyManager()
        self.assertEqual(len(km.describe()), 1)

        km.create_auto_key()

        auto_keys = [m for m in km.describe() if m.type == KeyType.AUTO]
        self.assertEqual(len(auto_keys), 2)

    def test_decrypt_key_raises_and_destroys_on_unknown_type(self):
        km = KeyManager()
        # Create a bare key object without ever assigning a type (stays UNKNOWN).
        obj = km.kc.get_object('unk1')
        obj.object.create_time = 1.0
        obj.object.expire_time = 1.0
        obj.commit()

        with self.assertRaises(KeyError):
            km.decrypt_key('unk1')

        self.assertNotIn('unk1', km.kc.list_objuuids())

    def test_decrypt_key_raises_and_destroys_on_expiration(self):
        km = KeyManager()
        km.create_user_key(objuuid='k1', passphrase='pw')

        obj = km.kc.get_object('k1')
        obj.object.expire_time = 1.0
        obj.commit()

        with self.assertRaises(KeyError):
            km.decrypt_key('k1')

        self.assertNotIn('k1', km.kc.list_objuuids())

    def test_decrypt_key_raises_and_destroys_on_integrity_failure(self):
        km = KeyManager()
        km.create_user_key(objuuid='k1', passphrase='pw')

        obj = km.kc.get_object('k1')
        corrupted = bytes([obj.object.tag[0] ^ 0xFF]) + obj.object.tag[1:]
        obj.object.tag = corrupted
        obj.commit()

        with self.assertRaises(KeyError):
            km.decrypt_key('k1')


# ---------------------------------------------------------------------------
# resolve_key_objuuid
# ---------------------------------------------------------------------------

class TestResolveKeyObjuuid(KeyManagerTestCase):
    """Verify key resolution priority: DIST > USER > AUTO, preferring longer TTL on ties."""

    def test_prefers_dist_over_user_over_auto(self):
        km = KeyManager()  # seeds one AUTO key with agtuuid=None
        km.create_user_key(objuuid='user1', passphrase='pw', agtuuid='agentA')
        km.create_dist_key(objuuid='dist1', key_bytes=b'd' * 32, agtuuid='agentA', ttl=120.0)

        resolved = km.resolve_key_objuuid('agentA')

        self.assertEqual(resolved, 'dist1')

    def test_prefers_user_over_auto(self):
        km = KeyManager()
        km.create_user_key(objuuid='user1', passphrase='pw', agtuuid='agentA')

        resolved = km.resolve_key_objuuid('agentA')

        self.assertEqual(resolved, 'user1')

    def test_falls_back_to_global_auto_key_for_unknown_agent(self):
        km = KeyManager()

        resolved = km.resolve_key_objuuid('some-unrelated-agent')

        auto_metadata = next(m for m in km.describe() if m.type == KeyType.AUTO)
        self.assertEqual(resolved, auto_metadata.objuuid)

    def test_prefers_longer_ttl_on_type_tie(self):
        km = KeyManager()
        km.create_dist_key(objuuid='dist-short', key_bytes=b'a' * 32, agtuuid='agentA', ttl=60.0)
        km.create_dist_key(objuuid='dist-long', key_bytes=b'b' * 32, agtuuid='agentA', ttl=600.0)

        resolved = km.resolve_key_objuuid('agentA')

        self.assertEqual(resolved, 'dist-long')

    def test_returns_none_when_no_keys_exist(self):
        km = KeyManager()
        for metadata in km.describe():
            km.delete_key(metadata.objuuid)

        self.assertIsNone(km.resolve_key_objuuid('agentA'))


# ---------------------------------------------------------------------------
# delete_expired_keys / delete_key / delete_dist_key
# ---------------------------------------------------------------------------

class TestKeyDeletion(KeyManagerTestCase):
    """Verify expiration sweeping and targeted deletion helpers."""

    def test_delete_expired_keys_removes_only_expired(self):
        km = KeyManager()
        km.create_user_key(objuuid='fresh', passphrase='pw')
        km.create_user_key(objuuid='stale', passphrase='pw')

        obj = km.kc.get_object('stale')
        obj.object.expire_time = 1.0
        obj.commit()

        km.delete_expired_keys()

        remaining = {m.objuuid for m in km.describe()}
        self.assertIn('fresh', remaining)
        self.assertNotIn('stale', remaining)

    def test_delete_key_removes_the_key(self):
        km = KeyManager()
        km.create_user_key(objuuid='k1', passphrase='pw')

        km.delete_key('k1')

        self.assertNotIn('k1', {m.objuuid for m in km.describe()})

    def test_delete_key_on_missing_key_does_not_raise(self):
        km = KeyManager()
        km.delete_key('does-not-exist')  # should log a warning, not raise

    def test_delete_dist_key_removes_only_dist_type(self):
        km = KeyManager()
        km.create_dist_key(objuuid='d1', key_bytes=b'a' * 32, agtuuid='agentA', ttl=120.0)
        km.create_user_key(objuuid='u1', passphrase='pw')

        km.delete_dist_key('d1')
        km.delete_dist_key('u1')  # not a DIST key, must be left alone

        remaining = {m.objuuid for m in km.describe()}
        self.assertNotIn('d1', remaining)
        self.assertIn('u1', remaining)

    def test_delete_dist_key_on_missing_key_does_not_raise(self):
        km = KeyManager()
        km.delete_dist_key('does-not-exist')  # should log a warning, not raise


# ---------------------------------------------------------------------------
# create_key_distributions / process_key_distributions
# ---------------------------------------------------------------------------

class TestKeyDistributions(KeyManagerTestCase):
    """Verify distribution export/import of auto keys between agents."""

    def test_create_key_distributions_includes_only_unexpired_auto_keys(self):
        km = KeyManager()  # seeds one AUTO key
        km.create_user_key(objuuid='u1', passphrase='pw')  # must be excluded

        distributions = km.create_key_distributions()

        self.assertEqual(len(distributions), 1)
        self.assertIsInstance(distributions[0], KeyDistribution)
        self.assertEqual(distributions[0].key, km.decrypt_key(distributions[0].objuuid))
        self.assertLessEqual(distributions[0].ttl, AUTO_KEY_EXPIRATION_DURATION)

    def test_create_key_distributions_excludes_expired_auto_key(self):
        km = KeyManager()
        auto_objuuid = km.describe()[0].objuuid

        obj = km.kc.get_object(auto_objuuid)
        obj.object.expire_time = 1.0
        obj.commit()

        distributions = km.create_key_distributions()

        self.assertEqual(distributions, [])

    def test_create_key_distributions_skips_and_logs_on_decrypt_failure(self):
        km = KeyManager()
        km.create_auto_key()
        auto_objuuids = [m.objuuid for m in km.describe() if m.type == KeyType.AUTO]
        self.assertEqual(len(auto_objuuids), 2)

        # Corrupt one key's tag so decrypt_key() fails integrity verification.
        broken_obj = km.kc.get_object(auto_objuuids[0])
        corrupted = bytes([broken_obj.object.tag[0] ^ 0xFF]) + broken_obj.object.tag[1:]
        broken_obj.object.tag = corrupted
        broken_obj.commit()

        distributions = km.create_key_distributions()

        self.assertEqual(len(distributions), 1)
        self.assertEqual(distributions[0].objuuid, auto_objuuids[1])

    def test_process_key_distributions_creates_dist_keys(self):
        producer = KeyManager()
        distributions = producer.create_key_distributions()

        consumer_dir = tempfile.TemporaryDirectory()
        self.addCleanup(consumer_dir.cleanup)
        os.chdir(consumer_dir.name)
        consumer = KeyManager()

        consumer.process_key_distributions(distributions, agtuuid='producer-agent')

        metadata = next(m for m in consumer.describe() if m.objuuid == distributions[0].objuuid)
        self.assertEqual(metadata.type, KeyType.DIST)
        self.assertEqual(metadata.agtuuid, 'producer-agent')
        self.assertEqual(consumer.decrypt_key(distributions[0].objuuid), distributions[0].key)


# ---------------------------------------------------------------------------
# describe
# ---------------------------------------------------------------------------

class TestDescribe(KeyManagerTestCase):
    """Verify describe() reports metadata for every stored key."""

    def test_describe_reports_all_keys(self):
        km = KeyManager()  # 1 auto key
        km.create_user_key(objuuid='u1', passphrase='pw')
        km.create_dist_key(objuuid='d1', key_bytes=b'a' * 32, agtuuid='agentA', ttl=60.0)

        types = sorted(str(m.type) for m in km.describe())

        self.assertEqual(types, sorted([str(KeyType.AUTO), str(KeyType.USER), str(KeyType.DIST)]))


# ---------------------------------------------------------------------------
# all_auto_keys_deprecated
# ---------------------------------------------------------------------------

class TestAllAutoKeysDeprecated(KeyManagerTestCase):
    """Verify the deprecation-window check used to trigger auto key rotation."""

    def test_false_immediately_after_seeding(self):
        km = KeyManager()
        self.assertFalse(km.all_auto_keys_deprecated)

    def test_true_once_every_auto_key_is_older_than_the_deprecation_window(self):
        km = KeyManager()
        auto_objuuid = km.describe()[0].objuuid

        obj = km.kc.get_object(auto_objuuid)
        obj.object.create_time = 1.0
        obj.commit()

        self.assertTrue(km.all_auto_keys_deprecated)

    def test_false_again_once_a_fresh_auto_key_exists(self):
        km = KeyManager()
        auto_objuuid = km.describe()[0].objuuid

        obj = km.kc.get_object(auto_objuuid)
        obj.object.create_time = 1.0
        obj.commit()
        self.assertTrue(km.all_auto_keys_deprecated)

        km.create_auto_key()

        self.assertFalse(km.all_auto_keys_deprecated)


if __name__ == '__main__':
    unittest.main()
