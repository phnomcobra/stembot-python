#!/usr/bin/python3

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

from stembot.dao import Collection


class KeyValuePair(BaseModel):
    name:    str           = Field()
    value:   Optional[Any] = Field(default=None)
    objuuid: Optional[str] = Field(default=None)
    coluuid: Optional[str] = Field(default=None)


def get(name: str, default: Any=None) -> Any:
    keys = Collection('kvstore', model=KeyValuePair)

    try:
        key = keys.find(name=name)[0]
        return key.object.value
    except IndexError:
        keys.build_object(name=name, value=default)
        return default


def set(name: str, value: Any):
    keys = Collection('kvstore', model=KeyValuePair)

    try:
        key = keys.find(name=name)[0]
        key.object.value = value
        key.set()
    except IndexError:
        keys.build_object(name=name, value=value)


def delete(name: str):
    for key in Collection('kvstore', model=KeyValuePair).find(name=name):
        key.destroy()


def get_all() -> Dict[str, Any]:
    keys = {}
    for key in Collection('kvstore', model=KeyValuePair).find():
        keys[key.object.name] = key.object.value
    return keys

kvstore = Collection('kvstore')
kvstore.create_attribute('name', "/name")
