"""This module implements the schema for messages."""
from enum import Enum
from time import time
from typing import List, Literal, Optional, Union

import cherrypy
from pydantic import BaseModel, Field, PositiveFloat, PositiveInt, StrictBool, ConfigDict

from stembot.dao.utils import get_uuid_str
from stembot.types.network import Route
from stembot.types.request import Request, Response

class ControlFormType(Enum):
    CREATE_PEER    = "CREATE_PEER"
    DISCOVER_PEER  = "DISCOVER_PEER"
    DELETE_PEERS   = "DELETE_PEERS"
    GET_PEERS      = "GET_PEERS"
    GET_ROUTES     = "GET_ROUTES"
    CREATE_TICKET  = "CREATE_TICKET"
    READ_TICKET    = "READ_TICKET"
    DELETE_TICKET  = "DELETE_TICKET"
    CREATE_CASCADE = "CREATE_CASCADE"
    READ_CASCADE   = "READ_CASCADE"
    DELETE_CASCADE = "DELETE_CASCADE"

    def __str__(self) -> str:
        return str(self.name)


class ControlForm(BaseModel):
    model_config = ConfigDict(extra='allow')

    type:    ControlFormType = Field()
    error:   Optional[str]   = Field(default=None)
    objuuid: Optional[str]   = Field(default=None)
    coluuid: Optional[str]   = Field(default=None)


class CreatePeer(ControlForm):
    url:     Optional[str]                               = Field(default=None)
    ttl:     Optional[Union[PositiveInt, PositiveFloat]] = Field(default=None)
    polling: StrictBool                                  = Field(default=False)
    agtuuid: str                                         = Field()

    type: ControlFormType = Field(default=ControlFormType.CREATE_PEER, const=True)


class DiscoverPeer(ControlForm):
    agtuuid: Optional[str]                               = Field(default=None)
    url:     str                                         = Field()
    ttl:     Optional[Union[PositiveInt, PositiveFloat]] = Field(default=None)
    polling: StrictBool                                  = Field(default=False)
    error:   Optional[str]                               = Field(default=None)

    type: ControlFormType = Field(default=ControlFormType.DISCOVER_PEER, const=True)


class DeletePeers(ControlForm):
    agtuuids: Optional[List[str]] = Field(default=None)
    type:     ControlFormType     = Field(default=ControlFormType.DELETE_PEERS, const=True)


class GetPeers(ControlForm):
    agtuuids: List[str]       = Field(default=[])
    type:     ControlFormType = Field(default=ControlFormType.GET_PEERS, const=True)


class GetRoutes(ControlForm):
    routes: List[Route]     = Field(default=[])
    type:   ControlFormType = Field(default=ControlFormType.GET_ROUTES, const=True)


class Ticket(ControlForm):
    tckuuid:      str                = Field(default=get_uuid_str(), const=True)
    src:          str                = Field(default=cherrypy.config.get('agtuuid'), const=True)
    dst:          str                = Field(default=cherrypy.config.get('agtuuid'), const=True)
    request:      Request            = Field(const=True)
    response:     Optional[Response] = Field(default=None)
    create_time:  float              = Field(default=time(), const=True)
    service_time: Optional[float]    = Field(default=None)

    type: Literal[
        ControlFormType.CREATE_TICKET,
        ControlFormType.READ_TICKET,
        ControlFormType.DELETE_TICKET
    ] = Field(default=ControlFormType.CREATE_TICKET)


class Cascade(ControlForm):
    cscuuid:      str             = Field(default=get_uuid_str(), const=True)
    src:          str             = Field(default=cherrypy.config.get('agtuuid'), const=True)
    request:      Request         = Field(const=True)
    responses:    List[Response]  = Field(default=[])
    create_time:  float           = Field(default=time(), const=True)
    service_time: Optional[float] = Field(default=None)
    etags:        List[str]       = Field(default=[])
    ftags:        List[str]       = Field(default=[])
    anonymous:    bool            = Field(default=False)

    type: Literal[
        ControlFormType.CREATE_CASCADE,
        ControlFormType.READ_CASCADE,
        ControlFormType.DELETE_CASCADE
    ] = Field(default=ControlFormType.CREATE_CASCADE)
