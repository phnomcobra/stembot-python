"""This module implements the schema for tickets."""
from enum import Enum

from pydantic import BaseModel, Field, ConfigDict

from stembot.types.control import ControlForm

class RequestType(Enum):
    CONTROL = "CONTROL"


class Request(BaseModel):
    """Common properties"""
    model_config = ConfigDict(extra='allow')

    type: RequestType = Field()


class ControlRequest(Request):
    message: ControlForm


class ResponseType(Enum):
    CONTROL = "CONTROL"


class Response(BaseModel):
    """Common properties"""
    model_config = ConfigDict(extra='allow')

    type: ResponseType = Field()


class ControlResponse(Response):
    message: ControlForm
