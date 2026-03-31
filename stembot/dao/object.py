"""This module implements the Object class."""
import json
from typing import Generic, Optional, TypeVar, get_args

import pydantic

from .document import DEFAULT_CONNECTION_STR, Document

T = TypeVar('T', bound=pydantic.BaseModel)

class Object(Document, Generic[T]):
    """This class encapsulates a collection object and implements methods
    for construction, loading, setting, and destroying collection objects."""
    def __init__(
            self, coluuid: str, objuuid: str,
            connection_str: str=DEFAULT_CONNECTION_STR,
            model: Optional[T]=None
        ):
        """This function initializes an instance of a collection object. It
        initializes a document instance and loads the object from it.

        Args:
            coluuid:
                The collection UUID.

            objuuid:
                The object UUID.

            connection_str:
                The sqlite connection string the document instance will use.

            model:
                Pydantic model to enforce.
            """
        Document.__init__(self, connection_str=connection_str)
        self.objuuid             = objuuid
        self.coluuid             = coluuid

        # If no model provided, try to extract from generic type parameter
        if model is None and hasattr(self, '__orig_class__'):
            type_args = get_args(self.__orig_class__) # pylint: disable=no-member
            if type_args and type_args[0] is not type(None):
                model = type_args[0]

        self.model:  Optional[T] = model
        self.object: T
        self.load()

    def load(self):
        """Load an existing or create a new object and load."""
        try:
            if self.model:
                self.object = self.model.model_validate(
                    Document.get_object(self, self.objuuid))
            else:
                self.object = Document.get_object(self, self.objuuid)
        except IndexError:
            Document.create_object(self, self.coluuid, self.objuuid)
            if self.model:
                self.object = self.model.model_validate(
                    Document.get_object(self, self.objuuid))
            else:
                self.object = Document.get_object(self, self.objuuid)

    def set(self):
        """Commit the object's state to the database."""
        if self.model:
            Document.set_object(
                self, self.coluuid, self.objuuid, self.model.model_validate(self.object))
        else:
            Document.set_object(self, self.coluuid, self.objuuid, self.object)

    def destroy(self):
        """Remove the object from the database."""
        Document.delete_object(self, self.objuuid)
        self.object = None

    def __str__(self):
        """Implements str for pretty printing an object"""
        try:
            return json.dumps(self.object, indent=4)
        except TypeError:
            return self.object.model_dump_json(indent=4)
        except: # pylint: disable=bare-except
            return str(self.object)
