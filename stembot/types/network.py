
"""This module implements the schema for messages."""
from enum import Enum
from time import time
from typing import List, Literal, Optional

import cherrypy
from pydantic import BaseModel, Field, ConfigDict, PositiveInt

from stembot.dao.utils import get_uuid_str
from stembot.types.request import Request, Response

class Route(BaseModel):
    agtuuid: str           = Field()
    weight:  PositiveInt   = Field()
    objuuid: Optional[str] = Field(default=None)
    coluuid: Optional[str] = Field(default=None)


class NetworkMessageType(Enum):
    ADVERTISEMENT    = "ADVERTISEMENT"
    MESSAGE_REQUEST  = "MESSAGE_REQUEST"
    MESSAGE_RESPONSE = "MESSAGE_RESPONSE"
    TICKET_REQUEST   = "TICKET_REQUEST"
    TICKET_RESPONSE  = "TICKET_RESPONSE"
    CASCADE_REQUEST  = "CASCADE_REQUEST"
    CASCADE_RESPONSE = "CASCADE_RESPONSE"
    PING             = "PING"
    ACKNOWLEDGEMENT  = "ACKNOWLEDGEMENT"

    def __str__(self) -> str:
        return str(self.name)


class NetworkMessage(BaseModel):
    """Common properties"""
    model_config = ConfigDict(extra='allow')

    type:      NetworkMessageType = Field()
    dest:      str                = Field(default=None)
    src:       str                = Field(default=cherrypy.config.get('agtuuid'))
    isrc:      Optional[str]      = Field(default=None)
    timestamp: Optional[float]    = Field(default=time())
    objuuid:   Optional[str]      = Field(default=None)
    coluuid:   Optional[str]      = Field(default=None)


class Ping(NetworkMessage):
    type: NetworkMessageType = Field(default=NetworkMessageType.PING, const=True)


class NetworkMessagesRequest(NetworkMessage):
    type: NetworkMessageType = Field(default=NetworkMessageType.MESSAGE_REQUEST, const=True)


class Acknowledgement(NetworkMessage):
    ack_type:  NetworkMessageType = Field()
    forwarded: Optional[str]      = Field(default=None)
    error:     Optional[str]      = Field(default=None)
    type:      NetworkMessageType = Field(default=NetworkMessageType.ACKNOWLEDGEMENT, const=True)


class Advertisement(NetworkMessage):
    routes:  List[Route]        = Field(const=True)
    agtuuid: str                = Field(const=True)
    type:    NetworkMessageType = Field(default=NetworkMessageType.ADVERTISEMENT, const=True)


class NetworkMessages(NetworkMessage):
    messages: List[NetworkMessage] = Field(default=[])
    type:     NetworkMessageType   = Field(default=NetworkMessageType.MESSAGE_RESPONSE, const=True)


class Ticket(NetworkMessage):
    tckuuid:      str                = Field(default=get_uuid_str(), const=True)
    request:      Request            = Field(const=True)
    response:     Optional[Response] = Field(default=None)
    error:        Optional[str]      = Field(default=None)
    create_time:  float              = Field(default=None, const=True)
    service_time: Optional[float]    = Field(default=None)

    type: Literal[
        NetworkMessageType.TICKET_REQUEST,
        NetworkMessageType.TICKET_RESPONSE
    ] = Field(default=NetworkMessageType.TICKET_REQUEST)


class Cascade(NetworkMessage):
    cscuuid:      str                = Field(default=get_uuid_str(), const=True)
    request:      Request            = Field(const=True)
    response:     Optional[Response] = Field(default=None)
    create_time:  float              = Field(default=None, const=True)
    service_time: Optional[float]    = Field(default=None)
    etags:        List[str]          = Field(default=[], const=True)
    ftags:        List[str]          = Field(default=[], const=True)
    anonymous:    bool               = Field(default=False, const=True)

    type: Literal[
        NetworkMessageType.CASCADE_REQUEST,
        NetworkMessageType.CASCADE_RESPONSE
    ] = Field(default=NetworkMessageType.CASCADE_REQUEST)
