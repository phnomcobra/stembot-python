"""This module implements the Collection class."""
from typing import Any, Dict, List, Optional, Union

import pydantic

from .document import Document
from .object import Object
from .utils import get_uuid_str

class Collection(Document):
    """This class implements the document object collection. This is the primary
    interface for searching and accessing objects."""
    def __init__(
        self, collection_name: str, connection_str: str=None,
        in_memory: bool=False, model: Optional[pydantic.BaseModel]=None):
        """This method contructs a collection instance. A collection name and
        optionally a sqlite connection string is used for resolving or creating
        a new document collection.

        Args:
            collection_name:
                A collection's name.

            connection_str:
                A sqlite connection str.

            model:
                Pydantic model to enforce.
        """
        self.collection_name = collection_name
        self.model = model

        if connection_str is None:
            self.connection_str = f'{collection_name}.sqlite'
        else:
            self.connection_str = connection_str

        if in_memory:
            self.connection_str = 'file::memory:?cache=shared'

        Document.__init__(self, connection_str=self.connection_str)

        try:
            self.coluuid = Document.list_collections(self)[self.collection_name]
        except KeyError:
            self.coluuid = Document.create_collection(self, self.collection_name)

    def destroy(self):
        """This method deletes the collection from the database."""
        Document.delete_collection(self, self.coluuid)

    # pylint: disable=arguments-differ
    def create_attribute(self, attribute: str, path: str):
        """This method creates or updates an attribute for the collection
        to indexed on. If an attribute is updated, the existing index state for the
        attribute is deleted and then rebuilt. The key to be indexed on is expressed
        as a series of index operators:

            /key1/1/key2

        Args:
            attribute:
                Name of the attribute.

            path:
                The object path to index on."""
        attributes = Document.list_attributes(self, self.coluuid)
        if (
                (attribute in attributes and attributes[attribute] != path) or
                attribute not in attributes
            ):
            self.delete_attribute(attribute)
            Document.create_attribute(self, self.coluuid, attribute, path)

    # pylint: disable=arguments-differ
    def delete_attribute(self, attribute: str):
        """This method deletes an attribute from the collection.

        Args:
            attribute:
                Name of the attribute.
        """
        Document.delete_attribute(self, self.coluuid, attribute)

    def find(self, *params: str, **kwparams: Any) -> List[Object]:
        """This method finds and returns a list of collection objects by matching attribute
        values to the key word arguments applied to this method. The key maps to the attribute
        name and the value maps to the indexed attribute value.

        Operators:
            $eq:  Values are equal (this is selected implicitly if the expression is naked)
            $gt:  Value is greater than another value
            $gte: Value is greater than or equal to another value
            $lt:  Value is less than another value
            $lte: Value is less than or equal to another value

            $contains:   Value contains another value
            $inside:     Value in another value
            $startswith: Value starts with
            $endswith:   Value ends with

            $regex: Allows the use of regular expressions when evaluating field values

        Modifiers:
            ! Negation

        Args:
            params:
                Arguments consisting of attributes being queried and the expression
                to apply. Expressions may be simple matches:

                    `attribute=text to match`

                Expressions can be encoded operators:
                    `attribute=$eq:text to match`

                Operators may also include a modifier that modifies the logic
                    `attribute=$!eq:text to match`

            kwparams:
                Arguments consisting of attributes being queried and the expression
                to apply. Expressions may be simple matches:

                    attribute = `text to match`
                    attribute = 123

                Expressions can be encoded operators:
                    attribute = `$eq:text to match`

                Operators may also include a modifier that modifies the logic
                    attribute = `$!eq:text to match`

        Returns:
            A list of collection objects.
        """
        objuuids = []

        if len(params) == 0 and len(kwparams) == 0:
            objuuids = self.list_objuuids()
        else:
            objuuids = Document.find_objuuids(self, self.coluuid, *params, **kwparams)

        objects = []
        for objuuid in objuuids:
            objects.append(
                Object(
                    coluuid=self.coluuid,
                    objuuid=objuuid,
                    connection_str=self.connection_str,
                    model=self.model
                )
            )

        return objects

    def find_objuuids(self, *params: str, **kwparams: Any) -> List[str]:
        """This method finds and returns a list of collection object UUIDs by matching attribute
        values to the key word arguments applied to this method. The key maps to the attribute
        name and the value maps to the indexed attribute value.

        Operators:
            $eq:  Values are equal (this is selected implicitly if the expression is naked)
            $gt:  Value is greater than another value
            $gte: Value is greater than or equal to another value
            $lt:  Value is less than another value
            $lte: Value is less than or equal to another value

            $contains:   Value contains another value
            $inside:     Value in another value
            $startswith: Value starts with
            $endswith:   Value ends with

            $regex: Allows the use of regular expressions when evaluating field values

        Modifiers:
            ! Negation

        Args:
            params:
                Arguments consisting of attributes being queried and the expression
                to apply. Expressions may be simple matches:

                    `attribute=text to match`

                Expressions can be encoded operators:
                    `attribute=$eq:text to match`

                Operators may also include a modifier that modifies the logic
                    `attribute=$!eq:text to match`

            kwparams:
                Arguments consisting of attributes being queried and the expression
                to apply. Expressions may be simple matches:

                    attribute = `text to match`
                    attribute = 123

                Expressions can be encoded operators:
                    attribute = `$eq:text to match`

                Operators may also include a modifier that modifies the logic
                    attribute = `$!eq:text to match`

        Returns:
            A list of collection object UUIDs.
        """
        if len(params) == 0 and len(kwparams) == 0:
            return self.list_objuuids()

        return Document.find_objuuids(self, self.coluuid, *params, **kwparams)

    def get_object(self, objuuid: str = None) -> Object:
        """This method returns a new or existing collection object. If an object UUID is
        not specified, then a UUID is generated.

        Args:
            objuuid:
                A object UUID.

        Returns:
            A collection object.
        """
        return Object(
            self.coluuid,
            get_uuid_str() if objuuid is None else objuuid,
            connection_str=self.connection_str,
            model=self.model
        )

    def build_object(self, **kwargs) -> Object:
        """This method constructs and validates objects from keyword arguments.

        Args:
            kwargs

        Returns:
            A collection object.
        """
        return self.upsert_object(kwargs)

    def upsert_object(self, obj: Union[Dict, pydantic.BaseModel]) -> Object:
        """This method constructs and validates objects from keyword arguments.

        Args:
            kwargs

        Returns:
            A collection object.
        """
        if self.model:
            obj = self.model.model_validate(obj)
            if hasattr(obj, 'objuuid') and obj.objuuid is not None:
                objuuid = obj.objuuid
            else:
                objuuid = get_uuid_str()
        else:
            objuuid = obj['objuuid'] if 'objuuid' in obj.keys() else get_uuid_str()

        try:
            Document.get_object(self, objuuid)
        except IndexError:
            Document.create_object(self, coluuid=self.coluuid, objuuid=objuuid)

        Document.set_object(
            self,
            coluuid=self.coluuid,
            objuuid=objuuid,
            updated_object=obj
        )

        return self.get_object(objuuid)

    def list_objuuids(self) -> List[str]:
        """This method returns a list of every object UUID in the collection.

        Returns:
            A list of object UUIDs.
        """
        return Document.list_collection_objects(self, self.coluuid)
