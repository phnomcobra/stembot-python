#!/usr/bin/python3
"""This module implements the Document class.
The document class wraps and abstracts the database and the various SQL
driving functions. It serves as the base class with is inherited by the
Collection and Object classes."""
import pickle
import re
from threading import RLock
from typing import Any, Dict, List, Union

import sqlite3

import pydantic

from stembot import logging

from .utils import (
    Operator, get_uuid_str, read_key_at_path, coerce
)

DEFAULT_CONNECTION_STR = "default.sqlite"
DOCUMENT_LOCKS = {}

def synchronized(func):
    """Decorator function used for synchronizing document calls.
    The document's connnection string is used as the key. Each connection
    string has it's own lock.
    """
    def wrapper(*args, **kwargs):
        try:
            lock_key = args[0].get_connection_str()
        except (ValueError, AttributeError, IndexError):
            logging.exception('Resorting to default lock key')
            lock_key = 'default'

        if lock_key not in DOCUMENT_LOCKS:
            DOCUMENT_LOCKS[lock_key] = RLock()

        try:
            DOCUMENT_LOCKS[lock_key].acquire()
            result = func(*args, **kwargs)
        finally:
            DOCUMENT_LOCKS[lock_key].release()
        return result
    return wrapper

class Document:
    """This class wraps and abstracts that database and the SQL driving
    functions. The class manages objects, collections, and collection
    attributes. Additonally, there is functionality for searching and
    enumerating collections."""
    @synchronized
    def __init__(self, connection_str: str = DEFAULT_CONNECTION_STR):
        """This function instantiates a document object and initiallizes
        the database if it hasn't been initialized yet.

        Args:
            connection_str:
                A Sqlite connection string."""
        self.connection_str = connection_str
        self.connection = sqlite3.connect(self.connection_str, 300)
        self.connection.text_factory = str

        self.cursor = self.connection.cursor()
        self.cursor.execute("PRAGMA foreign_keys = ON")
        self.connection.commit()

        self.cursor.execute('''CREATE TABLE IF NOT EXISTS TBL_COLLECTIONS (
                               COLUUID VARCHAR(36),
                               NAME VARCHAR(64) UNIQUE NOT NULL,
                               PRIMARY KEY (COLUUID));''')

        # pylint: disable=line-too-long
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS TBL_OBJECTS (
                               OBJUUID VARCHAR(36),
                               COLUUID VARCHAR(36),
                               VALUE BYTEA NOT NULL,
                               PRIMARY KEY (OBJUUID),
                               FOREIGN KEY (COLUUID) REFERENCES TBL_COLLECTIONS(COLUUID) ON DELETE CASCADE);''')

        # pylint: disable=line-too-long
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS TBL_ATTRIBUTES (
                               COLUUID VARCHAR(36),
                               ATTRIBUTE VARCHAR(64),
                               PATH VARCHAR(64),
                               PRIMARY KEY (COLUUID, ATTRIBUTE),
                               FOREIGN KEY (COLUUID) REFERENCES TBL_COLLECTIONS(COLUUID) ON DELETE CASCADE);''')

        # pylint: disable=line-too-long
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS TBL_INDEX (
                               OBJUUID VARCHAR(36),
                               COLUUID VARCHAR(36),
                               ATTRIBUTE VARCHAR(64),
                               VALUE VARCHAR(64),
                               PRIMARY KEY (OBJUUID, ATTRIBUTE),
                               FOREIGN KEY (OBJUUID) REFERENCES TBL_OBJECTS(OBJUUID) ON DELETE CASCADE,
                               FOREIGN KEY (COLUUID, ATTRIBUTE) REFERENCES TBL_ATTRIBUTES(COLUUID, ATTRIBUTE) ON DELETE CASCADE);''')

        self.connection.commit()

    def get_connection_str(self) -> str:
        """This function returns the connection string.

        Returns:
            str:
                Connection String.
        """

    @synchronized
    def vacuum(self):
        """This function compacts the database."""
        self.cursor.execute("VACUUM;")
        self.connection.commit()

    @synchronized
    def create_object(self, coluuid: str, objuuid: str):
        """This function creates a new object in a collection.
        With the exception of setting the object and collection
        UUIDs, the object is empty.  Objects being
        stored are pickled and serialized.

        Args:
            coluuid:
                The collection UUID.

            objuuid:
                The object UUID.
        """
        self.cursor.execute(
            "insert into TBL_OBJECTS (COLUUID, OBJUUID, VALUE) values (?, ?, ?);",
            (coluuid, objuuid, pickle.dumps({"objuuid": objuuid, "coluuid": coluuid}))
        )
        self.connection.commit()

    @synchronized
    def set_object(
        self, coluuid: str, objuuid: str, updated_object: Union[Dict, pydantic.BaseModel]):
        """This function updates an object in a collection. The object dictionary,
        object UUID, and collection UUID are updated. In addition, previously indexed
        attributes are deleted and reset based on the updated object. Objects being
        stored are pickled and serialized.

        Args:
            coluuid:
                The collection UUID.

            objuuid:
                The object UUID.

            object:
                The object dictionary or pydantic model that will be stored.
        """
        try:
            if isinstance(updated_object, dict):
                updated_object["objuuid"] = objuuid
            else:
                updated_object.objuuid = objuuid
        except Exception as error: # pylint: disable=broad-except
            logging.warning(f'Failed to write objuuid: {objuuid}: {error}')

        try:
            if isinstance(updated_object, dict):
                updated_object["coluuid"] = coluuid
            else:
                updated_object.coluuid = coluuid
        except Exception as error: # pylint: disable=broad-except
            logging.warning(f'Failed to write coluuid: {coluuid}: {error}')

        self.cursor.execute(
            "update TBL_OBJECTS set VALUE = ? where OBJUUID = ?;",
            (pickle.dumps(updated_object), objuuid)
        )

        self.cursor.execute("delete from TBL_INDEX where OBJUUID = ?;", (objuuid,))

        for attribute, path in self.list_attributes(coluuid).items():
            try:
                self.cursor.execute(
                    "insert into TBL_INDEX (OBJUUID, COLUUID, ATTRIBUTE, VALUE)"\
                    "values (?, ?, ?, ?);",
                    (
                        objuuid,
                        coluuid,
                        attribute,
                        str(read_key_at_path(path, updated_object))
                    )
                )
            except (KeyError, IndexError, ValueError, TypeError) as error:
                logging.warning(
                    f'error encountered when indexing attribute "{attribute}" \
                    for object "{objuuid}": {error}'
                )
                continue
        self.connection.commit()

    @synchronized
    def get_object(self, objuuid: str) -> Dict:
        """Select, load, and deserialize an object. Pickle is used to deserialize and
        load the object.

        Args:
            objuuid:
                An object's UUID.

        Returns:
            A dictionary of the object.

        Raises:
            IndexError:
                This is raised when a requested object does not exist.
        """
        self.cursor.execute("select VALUE from TBL_OBJECTS where OBJUUID = ?;", (objuuid,))
        self.connection.commit()

        return pickle.loads(self.cursor.fetchall()[0][0])

    @synchronized
    def find_objuuids(self, coluuid: str, *params: str, **kwparams: Any) -> List[str]: # pylint: disable=too-many-locals,too-many-branches,too-many-statements
        """This function finds a list of object UUIDs by matching a value to an
        indexed attribute.

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
            coluuid:
                The UUID of the collection to search against.

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
            A list of UUID strings.
        """

        objuuid_lists = []

        queries = []

        # unpack params
        for param in params:
            param = str(param)

            try:
                attribute_stop_idx = param.index('=')
            except ValueError as value_error:
                error_str = f'find parameter specified without separator: {param}'
                logging.error(error_str)
                raise value_error

            expression = param[attribute_stop_idx+1:].lstrip()
            attribute = param[:attribute_stop_idx].strip()
            queries.append((attribute, expression))

        # unpack keyword params
        for attribute, expression in kwparams.items():
            queries.append((attribute, expression))

        # process queries
        for attribute, expression in queries:
            expression = str(expression)
            operator = Operator.EQ
            subject = expression

            # detect start of operator
            negation = False
            subject_start_idx = None
            if expression.startswith('$!'):
                operator_start_idx = 2
                negation = True
            elif expression.startswith('$'):
                operator_start_idx = 1
            else:
                operator_start_idx = None

            # detect end of operator
            try:
                operator_stop_idx = expression.index(':')
            except ValueError:
                operator_stop_idx = None

            # validate operator
            if operator_start_idx and operator_stop_idx:
                try:
                    operator = Operator[expression[operator_start_idx:operator_stop_idx].upper()]
                    subject_start_idx = operator_stop_idx + 1
                    subject = expression[subject_start_idx:]
                except KeyError as key_error:
                    logging.error(
                        f'invalid operator specified in find param: {attribute}="{expression}"'
                    )
                    raise key_error
            elif operator_start_idx:
                error_str = f'operator specified without separator: {attribute}="{expression}"'
                logging.error(error_str)
                raise ValueError(error_str)

            # process operator
            if operator == Operator.EQ and not negation:
                self.cursor.execute(
                    "select OBJUUID from TBL_INDEX \
                     where ATTRIBUTE = ? and VALUE = ? and COLUUID = ?;",
                    (attribute, subject, coluuid)
                )
                self.connection.commit()
                objuuid_lists.append([row[0] for row in self.cursor.fetchall()])

            elif operator == Operator.EQ and negation:
                self.cursor.execute(
                    "select OBJUUID from TBL_INDEX \
                     where ATTRIBUTE = ? and VALUE != ? and COLUUID = ?;",
                    (attribute, subject, coluuid)
                )
                self.connection.commit()
                objuuid_lists.append([row[0] for row in self.cursor.fetchall()])

            elif operator == Operator.CONTAINS and not negation:
                self.cursor.execute(
                    "select OBJUUID from TBL_INDEX \
                     where ATTRIBUTE = ? and VALUE like ? and COLUUID = ?;",
                    (attribute, f'%{subject}%', coluuid)
                )
                self.connection.commit()
                objuuid_lists.append([row[0] for row in self.cursor.fetchall()])

            elif operator == Operator.CONTAINS and negation:
                self.cursor.execute(
                    "select OBJUUID from TBL_INDEX \
                     where ATTRIBUTE = ? and VALUE not like ? and COLUUID = ?;",
                    (attribute, f'%{subject}%', coluuid)
                )
                self.connection.commit()
                objuuid_lists.append([row[0] for row in self.cursor.fetchall()])

            elif operator == Operator.STARTSWITH and not negation:
                self.cursor.execute(
                    "select OBJUUID from TBL_INDEX \
                     where ATTRIBUTE = ? and VALUE like ? and COLUUID = ?;",
                    (attribute, f'{subject}%', coluuid)
                )
                self.connection.commit()
                objuuid_lists.append([row[0] for row in self.cursor.fetchall()])

            elif operator == Operator.STARTSWITH and negation:
                self.cursor.execute(
                    "select OBJUUID from TBL_INDEX \
                     where ATTRIBUTE = ? and VALUE not like ? and COLUUID = ?;",
                    (attribute, f'{subject}%', coluuid)
                )
                self.connection.commit()
                objuuid_lists.append([row[0] for row in self.cursor.fetchall()])

            elif operator == Operator.ENDSWITH and not negation:
                self.cursor.execute(
                    "select OBJUUID from TBL_INDEX \
                     where ATTRIBUTE = ? and VALUE like ? and COLUUID = ?;",
                    (attribute, f'%{subject}', coluuid)
                )
                self.connection.commit()
                objuuid_lists.append([row[0] for row in self.cursor.fetchall()])

            elif operator == Operator.ENDSWITH and negation:
                self.cursor.execute(
                    "select OBJUUID from TBL_INDEX \
                     where ATTRIBUTE = ? and VALUE not like ? and COLUUID = ?;",
                    (attribute, f'%{subject}', coluuid)
                )
                self.connection.commit()
                objuuid_lists.append([row[0] for row in self.cursor.fetchall()])

            else:
                self.cursor.execute(
                    "select OBJUUID, VALUE from TBL_INDEX \
                     where ATTRIBUTE = ? and COLUUID = ?;",
                    (attribute, coluuid)
                )
                self.connection.commit()

                objuuids = []
                for row in self.cursor.fetchall():
                    objuuid = row[0]
                    value = row[1]
                    append = False

                    try:
                        if operator == Operator.GT:
                            append = coerce(value) > coerce(subject)
                        elif operator == Operator.GTE:
                            append = coerce(value) >= coerce(subject)
                        elif operator == Operator.LT:
                            append = coerce(value) < coerce(subject)
                        elif operator == Operator.LTE:
                            append = coerce(value) <= coerce(subject)
                        elif operator == Operator.INSIDE:
                            append = value in subject
                        elif operator == Operator.REGEX:
                            append = re.search(subject, value)
                    except Exception as error: # pylint: disable=broad-except
                        logging.warning(
                            f'compare in find failed for {attribute}:{value}={expression}: {error}'
                        )
                        continue

                    if append or (negation and not append):
                        objuuids.append(objuuid)

                objuuid_lists.append(objuuids)

        if len(objuuid_lists) == 0:
            return []

        objuuids = set(objuuid_lists[0])
        for objuuid_list in objuuid_lists[1:]:
            objuuids = objuuids & set(objuuid_list)

        return list(objuuids)

    @synchronized
    def delete_object(self, objuuid: str):
        """This function deletes an object.

        Args:
            objuuid:
                The object's UUID."""
        self.cursor.execute("delete from TBL_OBJECTS where OBJUUID = ?;", (objuuid,))
        self.connection.commit()

    @synchronized
    def create_attribute(self, coluuid: str, attribute: str, path: str):
        """This function creates a new attribute for a collection. Upon creation of
        the attribute, all of the collection's objects are indexed with the new
        attribute.

        The attribute path is one or multiple index operators used to select a key or
        index out of a dictionary.

            /inner/outer

        Args:
            coluuid:
                The collection UUID.

            attribute:
                The attribute name.

            path:
                The attribute path.
        """
        self.cursor.execute(
            "insert into TBL_ATTRIBUTES (COLUUID, ATTRIBUTE, PATH) values (?, ?, ?);",
            (coluuid, attribute, path)
        )

        self.cursor.execute(
            "select OBJUUID, VALUE from TBL_OBJECTS where COLUUID = ?;", (coluuid,)
        )

        for row in self.cursor.fetchall():
            objuuid = row[0]
            try:
                self.cursor.execute(
                    "insert into TBL_INDEX (OBJUUID, COLUUID, ATTRIBUTE, VALUE)"\
                    "values (?, ?, ?, ?);",
                    (
                        objuuid,
                        coluuid,
                        attribute,
                        str(read_key_at_path(path, pickle.loads(row[1])))
                    )
                )
            except (KeyError, ValueError, TypeError, IndexError) as error:
                logging.warning(
                    f'error encountered when indexing attribute "{attribute}" \
                      for object "{objuuid}": {error}'
                )
                continue

        self.connection.commit()

    @synchronized
    def delete_attribute(self, coluuid: str, attribute: str):
        """This function delete an attribute from a collection.

        Args:
            coluuid:
                The collection UUID.

            attribute:
                The attribute name.
        """
        self.cursor.execute(
            "delete from TBL_ATTRIBUTES where COLUUID = ? and ATTRIBUTE = ?;",
            (coluuid, attribute)
        )

        self.cursor.execute(
            "delete from TBL_INDEX where ATTRIBUTE = ? and COLUUID = ?;",
            (attribute, coluuid)
        )

        self.connection.commit()

    @synchronized
    def list_attributes(self, coluuid: str) -> Dict[str, str]:
        """This function returns a dictionary of a collection's attribute names
        and corresponding attribute paths.

        Args:
            coluuid:
                The collection's UUID.

        Returns:
            A dictionary of attribute paths keyed by their attribute names.
        """
        self.cursor.execute(
            "select ATTRIBUTE, PATH from TBL_ATTRIBUTES where COLUUID = ?;",
            (coluuid,)
        )

        self.connection.commit()

        attributes = {}
        for row in self.cursor.fetchall():
            attributes[row[0]] = row[1]
        return attributes

    @synchronized
    def create_collection(self, name: str) -> str:
        """This function creates a new collection and returns its UUID.

        Args:
            name:
                Name of the collection.

        Returns:
            coluuid:
                The collection's UUID.
        """
        coluuid = get_uuid_str()

        self.cursor.execute(
            "insert into TBL_COLLECTIONS (COLUUID, NAME) values (?, ?);",
            (coluuid, name)
        )

        self.connection.commit()

        return coluuid

    @synchronized
    def delete_collection(self, coluuid: str):
        """This function deletes a collection.

        Args:
            coluuid:
                The collection's UUID.
        """
        self.cursor.execute("delete from TBL_COLLECTIONS where COLUUID = ?;", (coluuid,))
        self.connection.commit()

    @synchronized
    def list_collections(self) -> Dict[str, str]:
        """This function returns a dictionary of the collection UUIDs
        keyed with collection names.

        Returns:
            A dictionary of names and collection UUIDs.
        """
        self.cursor.execute("select NAME, COLUUID from TBL_COLLECTIONS;")
        self.connection.commit()

        collections = {}
        for row in self.cursor.fetchall():
            collections[row[0]] = row[1]
        return collections

    @synchronized
    def list_collection_objects(self, coluuid: str) -> List[str]:
        """This function returns a list of object UUIDs present in the collection..

        Returns:
            A list of object UUIDs.
        """
        self.cursor.execute("select OBJUUID from TBL_OBJECTS where COLUUID = ?;", (coluuid,))
        self.connection.commit()
        return [row[0] for row in self.cursor.fetchall()]

    @synchronized
    def __del__(self):
        """This destructor function closes the database connection."""
        self.connection.close()
