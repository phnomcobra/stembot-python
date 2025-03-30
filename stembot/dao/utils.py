#!/usr/bin/python3
"""This module implements a wrapper around a UUID generator."""
from copy import deepcopy
from hashlib import sha256
from typing import Any
from uuid import uuid4
from enum import Enum, auto

from stembot.audit import logging

class Operator(Enum):
    """Valid Operators to decode from find parameters"""
    EQ = auto()
    GT = auto()
    GTE = auto()
    LT = auto()
    LTE = auto()
    INSIDE = auto()
    CONTAINS = auto()
    STARTSWITH = auto()
    ENDSWITH = auto()
    REGEX = auto()

def get_uuid_str() -> str:
    """This function generates a UUID string.

    Returns:
        A UUID as a string.
    """
    return str(uuid4())

def get_uuid_str_from_str(seed: str) -> str:
    """This function generates a UUID from a string.

    Args:
        seed:
            String to be digested.

    Returns:
        A UUID as a string.
    """
    _hash = sha256()
    _hash.update(seed.encode())
    digest = _hash.hexdigest()
    return f'{digest[0:8]}-{digest[8:12]}-{digest[12:16]}-{digest[16:20]}-{digest[20:32]}'

def read_key_at_path(path: str, object_to_inspect: Any) -> Any:
    """This function reads a key at a specified path string. The first character
    of the path string indicates the delimiter being used.

    Path strings are typically formated as "/keyA/1/keyB" where "keyA" and "keyB"
    are passed through directly as tokens while "1" is coerced to an integer. The
    leading character "/" is the delimiter in use for this path.

    Args:
        path:
            The string of the path to tokenize and travel on.

        object_to_inspect:
            The list or dictionary being travelled.

    Returns:
        value of the key or index being arrived at.

    Raises:
        IndexError, KeyError, TypeError
    """
    delimeter = path[0]
    tokens = path[1:].split(delimeter)

    # Coerce tokens to integers
    for token_id in range(len(tokens)): # pylint: disable=consider-using-enumerate
        try:
            tokens[token_id] = int(tokens[token_id])
        except ValueError:
            continue

    if hasattr(object_to_inspect, 'model_dump'):
        current_object = object_to_inspect.model_dump()
    else:
        current_object = deepcopy(object_to_inspect)

    for token in tokens:
        current_object = current_object[token]
    return current_object

def coerce(item: Any) -> Any:
    """This is a type coercion function for coercing a type for an item.

    The coercer favors an integer, then a float, and finally a string.

    Args:
        item: Item being coerced.

    Returns:
        type coerced item.
    """

    try:
        return int(item)
    except ValueError:
        pass

    try:
        return float(item)
    except ValueError:
        pass

    return str(item)
