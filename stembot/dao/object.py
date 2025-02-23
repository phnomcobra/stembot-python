"""This module implements the Object class."""
import json

from .document import DEFAULT_CONNECTION_STR, Document

class Object(Document):
    """This class encapsulates a collection object and implements methods
    for construction, loading, setting, and destroying collection objects."""
    def __init__(self, coluuid: str, objuuid: str, connection_str: str = DEFAULT_CONNECTION_STR):
        """This function initilizes an instance of a collection object. It
        initializes a document instance and loads the object from it.

        Args:
            coluuid:
                The collection UUID.

            objuuid:
                The object UUID.

            connection_str:
                The sqlite connection string the document instance will use."""
        Document.__init__(self, connection_str=connection_str)
        self.objuuid = objuuid
        self.coluuid = coluuid
        self.object = None
        self.load()

    def load(self):
        """Load an existing or create a new object and load."""
        try:
            self.object = Document.get_object(self, self.objuuid)
        except IndexError:
            Document.create_object(self, self.coluuid, self.objuuid)
            self.object = Document.get_object(self, self.objuuid)

    def set(self):
        """Commit the object's state to the database."""
        Document.set_object(self, self.coluuid, self.objuuid, self.object)

    def destroy(self):
        """Remove the object from the database."""
        Document.delete_object(self, self.objuuid)
        self.object = None

    def __str__(self):
        """Implements str for pretty printing an object"""
        return json.dumps(self.object, indent=4)
