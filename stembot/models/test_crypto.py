"""Unit tests for stembot.models.crypto."""
import base64
import time
import unittest

from pydantic import ValidationError

from stembot.enums import KeyType
from stembot.models.crypto import Key, KeyDistribution, KeyMetadata, validate_b64_n_bytes, validate_n_bytes


class TestValidateNBytes(unittest.TestCase):
    """Verify the validate_n_bytes validator factory."""

    def test_accepts_exact_length(self):
        validator = validate_n_bytes(4)
        self.assertEqual(validator(b'abcd'), b'abcd')

    def test_rejects_shorter_length(self):
        validator = validate_n_bytes(4)
        with self.assertRaises(ValueError):
            validator(b'abc')

    def test_rejects_longer_length(self):
        validator = validate_n_bytes(4)
        with self.assertRaises(ValueError):
            validator(b'abcde')


class TestValidateB64NBytes(unittest.TestCase):
    """Verify the validate_b64_n_bytes validator factory."""

    def test_accepts_valid_base64_of_exact_length(self):
        encoded = base64.b64encode(b'x' * 32).decode('ascii')
        validator = validate_b64_n_bytes(32)
        self.assertEqual(validator(encoded), encoded)

    def test_rejects_wrong_decoded_length(self):
        encoded = base64.b64encode(b'x' * 16).decode('ascii')
        validator = validate_b64_n_bytes(32)
        with self.assertRaises(ValueError):
            validator(encoded)

    def test_rejects_invalid_base64(self):
        validator = validate_b64_n_bytes(32)
        with self.assertRaises(ValueError):
            validator('not-valid-base64!!')


class TestKeyDistribution(unittest.TestCase):
    """Verify KeyDistribution construction, validation, and the key property."""

    def test_construct_with_b64_key(self):
        encoded = base64.b64encode(b'k' * 32).decode('ascii')
        dist = KeyDistribution(b64_key=encoded, objuuid='obj1', ttl=60.0)
        self.assertEqual(dist.b64_key, encoded)
        self.assertEqual(dist.objuuid, 'obj1')
        self.assertEqual(dist.ttl, 60.0)

    def test_construct_with_raw_key(self):
        raw = b'k' * 32
        dist = KeyDistribution(key=raw, objuuid='obj1', ttl=60.0)
        self.assertEqual(dist.b64_key, base64.b64encode(raw).decode('ascii'))

    def test_key_property_round_trips_raw_key(self):
        raw = b'z' * 32
        dist = KeyDistribution(key=raw, objuuid='obj1', ttl=60.0)
        self.assertEqual(dist.key, raw)

    def test_rejects_wrong_length_key(self):
        with self.assertRaises(ValidationError):
            KeyDistribution(key=b'short', objuuid='obj1', ttl=60.0)

    def test_rejects_non_positive_ttl(self):
        raw = b'k' * 32
        with self.assertRaises(ValidationError):
            KeyDistribution(key=raw, objuuid='obj1', ttl=0.0)


class TestKeyMetadata(unittest.TestCase):
    """Verify KeyMetadata field assignment."""

    def test_construct(self):
        metadata = KeyMetadata(objuuid='obj1', type=KeyType.USER, agtuuid='agt1', ttl=120)
        self.assertEqual(metadata.objuuid, 'obj1')
        self.assertEqual(metadata.type, KeyType.USER)
        self.assertEqual(metadata.agtuuid, 'agt1')
        self.assertEqual(metadata.ttl, 120)

    def test_agtuuid_may_be_none(self):
        metadata = KeyMetadata(objuuid='obj1', type=KeyType.AUTO, agtuuid=None, ttl=1.5)
        self.assertIsNone(metadata.agtuuid)


class TestKey(unittest.TestCase):
    """Verify Key defaults, field validation, hasher, ttl, and describe."""

    def test_defaults(self):
        key = Key()
        self.assertIsNone(key.encrypted_key)
        self.assertIsNone(key.nonce)
        self.assertIsNone(key.tag)
        self.assertEqual(key.create_time, 0.0)
        self.assertEqual(key.expire_time, 0.0)
        self.assertEqual(key.type, KeyType.UNKNOWN)
        self.assertIsNone(key.agtuuid)
        self.assertIsNotNone(key.objuuid)
        self.assertIsNone(key.coluuid)

    def test_rejects_wrong_length_encrypted_key(self):
        with self.assertRaises(ValidationError):
            Key(encrypted_key=b'short')

    def test_rejects_wrong_length_nonce(self):
        with self.assertRaises(ValidationError):
            Key(nonce=b'short')

    def test_rejects_wrong_length_tag(self):
        with self.assertRaises(ValidationError):
            Key(tag=b'short')

    def test_accepts_correct_length_fields(self):
        key = Key(encrypted_key=b'e' * 32, nonce=b'n' * 16, tag=b't' * 16)
        self.assertEqual(key.encrypted_key, b'e' * 32)
        self.assertEqual(key.nonce, b'n' * 16)
        self.assertEqual(key.tag, b't' * 16)

    def test_hasher_is_deterministic(self):
        key_a = Key(objuuid='obj1', agtuuid='agt1', type=KeyType.USER, create_time=1.0, expire_time=2.0)
        key_b = Key(objuuid='obj1', agtuuid='agt1', type=KeyType.USER, create_time=1.0, expire_time=2.0)
        self.assertEqual(key_a.hasher().hexdigest(), key_b.hasher().hexdigest())

    def test_hasher_differs_on_different_fields(self):
        key_a = Key(objuuid='obj1', agtuuid='agt1', type=KeyType.USER, create_time=1.0, expire_time=2.0)
        key_b = Key(objuuid='obj2', agtuuid='agt1', type=KeyType.USER, create_time=1.0, expire_time=2.0)
        self.assertNotEqual(key_a.hasher().hexdigest(), key_b.hasher().hexdigest())

    def test_ttl_reflects_remaining_lifetime(self):
        key = Key(expire_time=time.time() + 100)
        self.assertAlmostEqual(key.ttl, 100, delta=2)

    def test_ttl_is_negative_when_expired(self):
        key = Key(expire_time=time.time() - 100)
        self.assertLess(key.ttl, 0)

    def test_describe(self):
        key = Key(objuuid='obj1', agtuuid='agt1', type=KeyType.USER, expire_time=time.time() + 100)
        metadata = key.describe()
        self.assertIsInstance(metadata, KeyMetadata)
        self.assertEqual(metadata.objuuid, 'obj1')
        self.assertEqual(metadata.agtuuid, 'agt1')
        self.assertEqual(metadata.type, KeyType.USER)
        self.assertAlmostEqual(metadata.ttl, 100, delta=2)


if __name__ == '__main__':
    unittest.main()
