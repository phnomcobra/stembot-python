"""KVStore Unit Tests

Tests for the kvstore module, which provides key-value storage functionality
using the Collection class with KeyValuePair models.
"""
import unittest
from random import random, randint

from stembot.dao import kvstore

class TestKVStore(unittest.TestCase):
    """Test basic kvstore operations: get, commit, delete, get_all."""

    def setUp(self):
        self.key = f'test_key_{random()}'

    def tearDown(self):
        """Clean up kvstore after each test."""
        kvstore.delete(self.key)

    def test_commit_and_get_string(self):
        """Test committing and retrieving a string value."""
        value = f'test_value_{random()}'
        kvstore.commit(self.key, value)
        result = kvstore.get(self.key)
        self.assertEqual(result, value)

    def test_commit_and_get_int(self):
        """Test committing and retrieving an int value."""
        value = randint(0, 65536)
        kvstore.commit(self.key, value)
        result = kvstore.get(self.key)
        self.assertEqual(result, value)

    def test_commit_and_get_float(self):
        """Test committing and retrieving a float value."""
        value = random() * 65556.0
        kvstore.commit(self.key, value)
        result = kvstore.get(self.key)
        self.assertEqual(result, value)

    def test_commit_and_get_none(self):
        """Test committing and retrieving a None value."""
        value = None
        kvstore.commit(self.key, value)
        result = kvstore.get(self.key)
        self.assertEqual(result, value)

    def test_default_value_on_get(self):
        """Test that get returns default value when key does not exist."""
        default_value = f'default_{random()}'
        kvstore.delete(self.key)  # Ensure key does not exist
        result = kvstore.get(self.key, default=default_value)
        self.assertEqual(result, default_value)

    def test_default_ignored_on_existing_key(self):
        """Test that get ignores default value when key exists."""
        value = f'existing_{random()}'
        default_value = f'default_{random()}'
        kvstore.commit(self.key, value)
        result = kvstore.get(self.key, default=default_value)
        self.assertEqual(result, value)
