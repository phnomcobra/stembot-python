"""DAO Unit Tests"""
from random import random
import hashlib
import os
import unittest

from .collection import Collection
from .datastore import File, CHUNK_SIZE
from .utils import get_uuid_str_from_str


class TestDatastore(unittest.TestCase):
    """Test the Datastore."""
    def setUp(self):
        """Initialize a test collection and create object attributes."""
        test_id = random()
        self.collection = Collection(f'collection-test-{test_id}', 'file::memory:?cache=shared')
        self.collection.create_attribute("type", "/type")

    def tearDown(self):
        """Cleanup test collection"""
        self.collection.destroy()

    def test_file_write_read_1m(self):
        """Generate a 1MB test file, put it into the datastore,
        read it out again, and compare both ends."""
        data_in = os.urandom(1024 * 1024)
        hash_in = hashlib.sha256()
        hash_in.update(data_in)

        sequuid = get_uuid_str_from_str('1MB Test File')

        file = File(sequuid, datastore=self.collection)
        file.write(data_in)
        file.seek(0)

        hash_out = hashlib.sha256()
        hash_out.update(file.read())

        self.assertEqual(hash_in.hexdigest(), hash_out.hexdigest())

    def test_file_write_read_16b(self):
        """Generate a 16B test file, put it into the datastore,
        read it out again, and compare both ends."""
        data_in = os.urandom(16)
        hash_in = hashlib.sha256()
        hash_in.update(data_in)

        sequuid = get_uuid_str_from_str('16B Test File')

        file = File(sequuid, datastore=self.collection)
        file.write(data_in)
        file.seek(0)

        hash_out = hashlib.sha256()
        hash_out.update(file.read())

        self.assertEqual(hash_in.hexdigest(), hash_out.hexdigest())

    def test_file_write_read_70k(self):
        """Generate a 70KB test file, put it into the datastore,
        read it out again, and compare both ends."""
        data_in = os.urandom(70 * 1024)
        hash_in = hashlib.sha256()
        hash_in.update(data_in)

        sequuid = get_uuid_str_from_str('70KB Test File')

        file = File(sequuid, datastore=self.collection)
        file.write(data_in)
        file.seek(0)

        hash_out = hashlib.sha256()
        hash_out.update(file.read())

        self.assertEqual(hash_in.hexdigest(), hash_out.hexdigest())

    def test_file_write_read_chunk_size(self):
        """Generate a test file of chunk size, put it into the datastore,
        read it out again, and compare both ends."""
        data_in = os.urandom(CHUNK_SIZE)
        hash_in = hashlib.sha256()
        hash_in.update(data_in)

        sequuid = get_uuid_str_from_str('Chunk Test File')

        file = File(sequuid, datastore=self.collection)
        file.write(data_in)
        file.seek(0)

        hash_out = hashlib.sha256()
        hash_out.update(file.read())

        self.assertEqual(hash_in.hexdigest(), hash_out.hexdigest())

    def test_file_write_read_zero(self):
        """Generate a 0B test file, put it into the datastore,
        read it out again, and compare both ends."""
        data_in = b''
        hash_in = hashlib.sha256()
        hash_in.update(data_in)

        sequuid = get_uuid_str_from_str('0B Test File')

        file = File(sequuid, datastore=self.collection)
        file.write(data_in)

        hash_out = hashlib.sha256()
        hash_out.update(file.read())

        self.assertEqual(hash_in.hexdigest(), hash_out.hexdigest())
