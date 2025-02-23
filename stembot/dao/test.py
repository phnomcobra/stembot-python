"""DAO Unit Tests"""
from random import random
import hashlib
import os
import unittest

from .collection import Collection
from .datastore import File, CHUNK_SIZE
from .utils import get_uuid_str_from_str

class TestCollection(unittest.TestCase):
    """Test the Collection, object search, and search's operators."""
    def setUp(self):
        """Initialize a test collection, create object attributes, and set objects to test with."""
        test_id = random()
        self.collection = Collection(f'collection-test-{test_id}', 'file::memory:?cache=shared')

        self.collection.create_attribute('color', '/color')
        self.collection.create_attribute('size', '/size')
        self.collection.create_attribute('name', '/name')

        item = self.collection.get_object()
        item.object['size'] = 4
        item.object['name'] = 'apple'
        item.object['color'] = 'red'
        item.set()

        item = self.collection.get_object()
        item.object['size'] = 2
        item.object['name'] = 'lime'
        item.object['color'] = 'green'
        item.set()

        item = self.collection.get_object()
        item.object['size'] = 2
        item.object['name'] = 'lemon'
        item.object['color'] = 'yellow'
        item.set()

        item = self.collection.get_object()
        item.object['size'] = 1
        item.object['name'] = 'grape'
        item.object['color'] = 'green'
        item.set()

    def tearDown(self):
        """Cleanup test collection"""
        self.collection.destroy()

    def test_find_all(self):
        """Test find all"""
        self.assertEqual(len(self.collection.find()), 4)

    def test_find_op_startswith(self):
        """Test starts with operator"""
        self.assertEqual(len(self.collection.find(name='$startswith:lem')), 1)

    def test_find_op_endswith(self):
        """Test ends with operator"""
        self.assertEqual(len(self.collection.find(name='$endswith:mon')), 1)

    def test_find_op_contains(self):
        """Test contains with operator"""
        self.assertEqual(len(self.collection.find(name='$contains:emo')), 1)

    def test_find_op_inside(self):
        """Test inside operator"""
        self.assertEqual(len(self.collection.find(color='$inside:red and yellow')), 2)

    def test_find_op_regex(self):
        """Test regex operator"""
        self.assertEqual(len(self.collection.find(color='$regex:^gr.*n$')), 2)

    def test_find_op_gt(self):
        """Test greater than operator"""
        self.assertEqual(len(self.collection.find(size='$gt:2')), 1)

    def test_find_op_gte(self):
        """Test greater than equals operator"""
        self.assertEqual(len(self.collection.find(size='$gte:2')), 3)

    def test_find_op_lt(self):
        """Test less than operator"""
        self.assertEqual(len(self.collection.find(size='$lt:4')), 3)

    def test_find_op_lte(self):
        """Test less than equals operator"""
        self.assertEqual(len(self.collection.find(size='$lte:4')), 4)

    def test_find_op_eq(self):
        """Test equals operator"""
        self.assertEqual(len(self.collection.find(color='$eq:red')), 1)
        self.assertEqual(len(self.collection.find(color='red')), 1)

    def test_find_op_not_eq(self):
        """Test not equals operator"""
        self.assertEqual(len(self.collection.find(color='$!eq:red')), 3)

    def test_find_op_eq_combo(self):
        """Test combination of equality operators"""
        items = self.collection.find(
            color='green',
            size=2
        )
        self.assertEqual(len(items), 1)

    def test_find_op_invert_eq_combo(self):
        """Test inverted combination of equality operators"""
        items = self.collection.find(
            color='$!eq:green',
            size='$!eq:2'
        )
        self.assertEqual(len(items), 1)

    def test_find_op_gt_lt_combo(self):
        """Test combination of inequality operators"""
        items = self.collection.find(
            'size=$gt:1',
            'size=$lt:4'
        )
        self.assertEqual(len(items), 2)

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
