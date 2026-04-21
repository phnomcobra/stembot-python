"""This module implements the Object class."""
import json
from typing import Generic, Optional, TypeVar

import pydantic

from stembot.dao.utils import synchronized

from .document import DEFAULT_CONNECTION_STR, Document

T = TypeVar('T', bound=pydantic.BaseModel)

class _ObjectTyped(Generic[T]):
    """Internal wrapper to preserve type information when Object[T] is subscripted."""
    def __init__(self, model_class: T):
        self.model_class = model_class

    def __call__(self, coluuid: str, objuuid: str,
                 connection_str: str=DEFAULT_CONNECTION_STR):
        """Create an Object instance with the captured model type."""
        return Object(coluuid, objuuid, connection_str=connection_str,
                     model=self.model_class)

class Object(Document, Generic[T]):
    """This class encapsulates a collection object and implements methods
    for construction, loading, setting, and destroying collection objects."""

    def __class_getitem__(cls, item: T) -> _ObjectTyped:
        """Override subscripting to capture and preserve generic type parameter.

        This ensures that Object[KeyValuePair](...) will have access to
        the KeyValuePair type information at runtime.

        Args:
            item: The model class (e.g., KeyValuePair)

        Returns:
            An _ObjectTyped wrapper that preserves the type information.
        """
        return _ObjectTyped(item)

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

    @synchronized
    def commit(self):
        """Commit the object's state to the database."""
        if self.model:
            Document.commit_object(
                self, self.coluuid, self.objuuid, self.model.model_validate(self.object))
        else:
            Document.commit_object(self, self.coluuid, self.objuuid, self.object)

    @synchronized
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
