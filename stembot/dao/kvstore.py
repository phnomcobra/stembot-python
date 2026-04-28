"""Key-value storage abstraction backed by persistent collection storage.

This module provides a simple dictionary-like interface for storing and retrieving
arbitrary values by name. All data is persisted to disk automatically, making it
suitable for application state, configuration, and caching use cases.

Features:
- Simple get/commit/delete operations for named values
- Automatic initialization of missing keys with default values
- Support for storing any Python object via Pydantic serialization
- Bulk retrieval of all stored key-value pairs
- UUID tracking for internal reference management
"""

from typing import Any, Dict
from pydantic import BaseModel, Field

from stembot.dao import Collection


class KeyValuePair(BaseModel):
    """A key-value pair with metadata for persistent storage.

    Attributes:
        name: The unique name/key for this value.
        value: The stored value (any Python type supported by Pydantic).
        objuuid: Optional internal object UUID for DAO tracking.
        coluuid: Optional internal collection UUID for DAO tracking.
    """
    name:    str        = Field()
    value:   Any | None = Field(default=None)
    objuuid: str | None = Field(default=None)
    coluuid: str | None = Field(default=None)


def get(name: str, default: Any=None) -> Any:
    """Retrieve a value by name from the key-value store.

    Returns the stored value if it exists. If the key doesn't exist, stores the
    default value and returns it, automatically initializing new keys.

    Args:
        name: The name/key to retrieve.
        default: The value to return and store if the key doesn't exist (default: None).

    Returns:
        The stored value, or the default value if the key was not found.
    """
    keys = Collection[KeyValuePair]('kvstore')
    try:
        key = keys.find(name=name)[0]
        return key.object.value
    except IndexError:
        keys.build_object(name=name, value=default)
        return default


def commit(name: str, value: Any) -> None:
    """Store or update a value by name in the key-value store.

    Creates a new key-value pair if the name doesn't exist, or updates the
    value if the key already exists. Changes are persisted to disk.

    Args:
        name: The name/key to store the value under.
        value: The value to store (any Python type).
    """
    keys = Collection[KeyValuePair]('kvstore')
    try:
        key = keys.find(name=name)[0]
        key.object.value = value
        key.commit()
    except IndexError:
        keys.build_object(name=name, value=value)


def delete(name: str) -> None:
    """Delete a key-value pair by name from the store.

    Removes the key and its associated value from persistent storage.
    If the key doesn't exist, this operation is a no-op.

    Args:
        name: The name/key to delete.
    """
    Collection[KeyValuePair]('kvstore').pop(name=name)


def get_all() -> Dict[str, Any]:
    """Retrieve all stored key-value pairs.

    Returns:
        A dictionary mapping all names to their stored values.
    """
    result = {}
    for key in Collection[KeyValuePair]('kvstore').find():
        result[key.object.name] = key.object.value
    return result


Collection('kvstore').create_attribute('name', "/name")
