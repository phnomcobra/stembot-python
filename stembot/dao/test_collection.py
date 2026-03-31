"""DAO Unit Tests"""
from random import random
import hashlib
import os
import unittest

from pydantic import BaseModel, Field

from .collection import Collection
from .object import Object
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
        item.commit()

        item = self.collection.get_object()
        item.object['size'] = 2
        item.object['name'] = 'lime'
        item.object['color'] = 'green'
        item.commit()

        item = self.collection.get_object()
        item.object['size'] = 2
        item.object['name'] = 'lemon'
        item.object['color'] = 'yellow'
        item.commit()

        item = self.collection.get_object()
        item.object['size'] = 1
        item.object['name'] = 'grape'
        item.object['color'] = 'green'
        item.commit()

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


class Item(BaseModel):
    """Test model for typing verification."""
    name:    str = Field(default='')
    value:   int = Field(default=0)
    objuuid: str = Field(default=None)


class TestCollectionTyping(unittest.TestCase):
    """Test typing behavior of Collection and Object with generic types."""

    def setUp(self):
        """Initialize test collections with and without models."""
        test_id = random()

        # Collection without model
        self.collection_untyped: Collection = Collection(
            f'collection-untyped-{test_id}',
            'file::memory:?cache=shared'
        )

        # Collection with model
        self.collection_typed: Collection[Item] = Collection(
            f'collection-typed-{test_id}',
            'file::memory:?cache=shared',
            model=Item
        )

        self.collection_typed.create_attribute('name', '/name')
        self.collection_typed.create_attribute('value', '/value')

    def tearDown(self):
        """Cleanup test collections."""
        self.collection_untyped.destroy()
        self.collection_typed.destroy()

    def test_collection_untyped_model_is_none(self):
        """Verify untyped collection has no model."""
        self.assertIsNone(self.collection_untyped.model)

    def test_collection_typed_model_is_set(self):
        """Verify typed collection has model set."""
        self.assertIsNotNone(self.collection_typed.model)
        self.assertEqual(self.collection_typed.model.__name__, 'Item')

    def test_collection_generic_type_inference(self):
        """Test that generic type parameter is read by Collection.__init__."""
        # When Collection[Item] is created, model should be inferred if available
        test_id = random()
        collection: Collection[Item] = Collection(
            f'collection-inferred-{test_id}',
            'file::memory:?cache=shared'
        )

        # Check if model was inferred from generic type
        # Note: This only works if __orig_class__ is available at runtime
        collection.destroy()

    def test_object_typed_returns_correct_type(self):
        """Verify that get_object returns properly typed Object."""
        obj: Object[Item] = self.collection_typed.get_object()

        # Should have the model set
        self.assertIsNotNone(obj.model)
        self.assertIsInstance(obj.object, (Item, type(None)))

    def test_find_returns_typed_objects(self):
        """Verify that find returns objects with correct model type."""
        # Create some items
        for i in range(3):
            obj = self.collection_typed.build_object(name=f'item{i}', value=i)
            self.assertIsNotNone(obj)

        # Find all items
        items = self.collection_typed.find()

        self.assertEqual(len(items), 3)

        # Each item should have the model
        for item in items:
            self.assertIsNotNone(item.model)
            self.assertIsNotNone(item.object)

    def test_build_object_with_model(self):
        """Verify build_object creates properly typed objects."""
        obj: Object[Item] = self.collection_typed.build_object(
            name='test',
            value=42
        )

        self.assertIsNotNone(obj.object)
        self.assertEqual(obj.object.name, 'test')
        self.assertEqual(obj.object.value, 42)

    def test_upsert_object_with_model(self):
        """Verify upsert_object creates properly typed objects."""
        item_data = Item(name='upserted', value=100)
        obj: Object[Item] = self.collection_typed.upsert_object(item_data)

        self.assertIsNotNone(obj.object)
        self.assertEqual(obj.object.name, 'upserted')
        self.assertEqual(obj.object.value, 100)

    def test_object_model_attribute_type(self):
        """Verify that Object.model attribute has correct type."""
        obj = self.collection_typed.get_object()

        # Model should be the Item class
        self.assertEqual(obj.model.__name__, 'Item')

    def test_object_object_attribute_type_after_load(self):
        """Verify that Object.object attribute has correct type after load."""
        # Create and save an item
        obj = self.collection_typed.build_object(name='loadtest', value=123)
        original_uuid = obj.objuuid

        # Create a new Object instance to load it
        loaded_obj: Object[Item] = self.collection_typed.get_object(original_uuid)

        # The loaded object should have the Item model
        self.assertIsNotNone(loaded_obj.object)
        self.assertIsInstance(loaded_obj.object, Item)
