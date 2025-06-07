"""This module implements the schema for messages."""
from enum import Enum
from time import time
from typing import List, Literal, Optional, Union

from pydantic import BaseModel, Field, PositiveFloat, PositiveInt, StrictBool, ConfigDict

from stembot.dao.utils import get_uuid_str
from stembot.dao import kvstore
from stembot.types.routing import Peer, Route

class ControlFormType(Enum):
    CREATE_PEER    = "CREATE_PEER"
    DISCOVER_PEER  = "DISCOVER_PEER"
    DELETE_PEERS   = "DELETE_PEERS"
    GET_PEERS      = "GET_PEERS"
    GET_ROUTES     = "GET_ROUTES"
    CREATE_TICKET  = "CREATE_TICKET"
    READ_TICKET    = "READ_TICKET"
    DELETE_TICKET  = "DELETE_TICKET"
    CLOSE_TICKET   = "CLOSE_TICKET"
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

    type: ControlFormType = Field(default=ControlFormType.CREATE_PEER)


class DiscoverPeer(ControlForm):
    agtuuid: Optional[str]                               = Field(default=None)
    url:     str                                         = Field()
    ttl:     Optional[Union[PositiveInt, PositiveFloat]] = Field(default=None)
    polling: StrictBool                                  = Field(default=False)
    error:   Optional[str]                               = Field(default=None)

    type: ControlFormType = Field(default=ControlFormType.DISCOVER_PEER)


class DeletePeers(ControlForm):
    agtuuids: Optional[List[str]] = Field(default=None)
    type:     ControlFormType     = Field(default=ControlFormType.DELETE_PEERS)


class GetPeers(ControlForm):
    peers: List[Peer]      = Field(default=[])
    type:  ControlFormType = Field(default=ControlFormType.GET_PEERS)


class GetRoutes(ControlForm):
    routes: List[Route]     = Field(default=[])
    type:   ControlFormType = Field(default=ControlFormType.GET_ROUTES)


class Hop(BaseModel):
    agtuuid:  str   = Field()
    hop_time: float = Field()


class ControlFormTicket(ControlForm):
    model_config = ConfigDict(extra='allow')

    tckuuid:      str                     = Field(default_factory=get_uuid_str)
    src:          str                     = Field(default=kvstore.get('agtuuid'))
    dst:          str                     = Field(default=kvstore.get('agtuuid'))
    create_time:  float                   = Field(default=time())
    service_time: Optional[float]         = Field(default=None)
    tracing:      bool                    = Field(default=False)
    hops:         List[Hop]               = Field(default=[])

    form: Union[
        CreatePeer,
        DiscoverPeer,
        DeletePeers,
        GetPeers,
        GetRoutes,
        "ControlFormCascade"
    ] = Field()

    type: Literal[
        ControlFormType.CREATE_TICKET,
        ControlFormType.READ_TICKET,
        ControlFormType.DELETE_TICKET,
        ControlFormType.CLOSE_TICKET,
    ] = Field(default=ControlFormType.CREATE_TICKET)


class ControlFormCascade(ControlForm):
    cscuuid:      str               = Field(default_factory=get_uuid_str)
    src:          str               = Field(default=kvstore.get('agtuuid'))
    create_time:  float             = Field(default_factory=time)
    service_time: Optional[float]   = Field(default=None)
    etags:        List[str]         = Field(default=[])
    ftags:        List[str]         = Field(default=[])
    anonymous:    bool              = Field(default=False)

    request: Union[
        CreatePeer,
        DiscoverPeer,
        DeletePeers,
        GetPeers,
        GetRoutes,
        "ControlFormTicket"
    ] = Field()

    responses: List[
        Union[
            CreatePeer,
            DiscoverPeer,
            DeletePeers,
            GetPeers,
            GetRoutes,
            "ControlFormTicket"
        ]
     ] = Field(default=[])

    type: Literal[
        ControlFormType.CREATE_CASCADE,
        ControlFormType.READ_CASCADE,
        ControlFormType.DELETE_CASCADE
    ] = Field(default=ControlFormType.CREATE_CASCADE)
