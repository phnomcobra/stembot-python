from typing import Any, Dict
from pydantic import BaseModel, Field

from stembot.dao import Collection


class KeyValuePair(BaseModel):
    name:    str        = Field()
    value:   Any | None = Field(default=None)
    objuuid: str | None = Field(default=None)
    coluuid: str | None = Field(default=None)


def get(name: str, default: Any=None) -> Any:
    keys = Collection[KeyValuePair]('kvstore')
    try:
        key = keys.find(name=name)[0]
        return key.object.value
    except IndexError:
        keys.build_object(name=name, value=default)
        return default


def commit(name: str, value: Any):
    keys = Collection[KeyValuePair]('kvstore')
    try:
        key = keys.find(name=name)[0]
        key.object.value = value
        key.commit()
    except IndexError:
        keys.build_object(name=name, value=value)


def delete(name: str):
    for key in Collection[KeyValuePair]('kvstore').find(name=name):
        key.destroy()


def get_all() -> Dict[str, Any]:
    result = {}
    for key in Collection[KeyValuePair]('kvstore').find():
        result[key.object.name] = key.object.value
    return result


Collection('kvstore').create_attribute('name', "/name")
