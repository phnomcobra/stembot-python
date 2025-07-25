"""This module implements the schema for messages."""
from enum import Enum
from time import time
from typing import List, Literal, Optional, Union

from pydantic import BaseModel, Field, ConfigDict

from stembot.dao.utils import get_uuid_str
from stembot.dao import kvstore
from stembot.types.control import CreatePeer, DiscoverPeer, GetPeers, GetRoutes, LoadFile, SyncProcess, WriteFile
from stembot.types.routing import Route

class NetworkMessageType(Enum):
    ADVERTISEMENT         = "ADVERTISEMENT"
    MESSAGES_REQUEST      = "MESSAGE_REQUEST"
    MESSAGES_RESPONSE     = "MESSAGE_RESPONSE"
    TICKET_REQUEST        = "TICKET_REQUEST"
    TICKET_RESPONSE       = "TICKET_RESPONSE"
    TICKET_TRACE_RESPONSE = "TICKET_TRACE_RESPONSE"
    PING                  = "PING"
    ACKNOWLEDGEMENT       = "ACKNOWLEDGEMENT"

    def __str__(self) -> str:
        return str(self.name)


class NetworkMessage(BaseModel):
    """Common properties"""
    model_config = ConfigDict(extra='allow')

    type:      NetworkMessageType = Field()
    dest:      Optional[str]      = Field(default=None)
    src:       str                = Field(default=kvstore.get('agtuuid'))
    isrc:      Optional[str]      = Field(default=None)
    timestamp: Optional[float]    = Field(default_factory=time)
    objuuid:   Optional[str]      = Field(default=None)
    coluuid:   Optional[str]      = Field(default=None)


class Ping(NetworkMessage):
    type: NetworkMessageType = Field(default=NetworkMessageType.PING)


class NetworkMessagesRequest(NetworkMessage):
    type: NetworkMessageType = Field(default=NetworkMessageType.MESSAGES_REQUEST)


class Acknowledgement(NetworkMessage):
    ack_type:  NetworkMessageType = Field()
    forwarded: Optional[str]      = Field(default=None)
    error:     Optional[str]      = Field(default=None)
    type:      NetworkMessageType = Field(default=NetworkMessageType.ACKNOWLEDGEMENT)


class Advertisement(NetworkMessage):
    routes:  List[Route]        = Field(default=[])
    agtuuid: str                = Field()
    type:    NetworkMessageType = Field(default=NetworkMessageType.ADVERTISEMENT)


class NetworkMessagesResponse(NetworkMessage):
    messages: List[NetworkMessage] = Field(default=[])
    type:     NetworkMessageType   = Field(default=NetworkMessageType.MESSAGES_RESPONSE)


class TicketTraceResponse(NetworkMessage):
    tckuuid:             str                = Field()
    hop_time:            float              = Field(default_factory=time)
    network_ticket_type: NetworkMessageType = Field()
    type:                NetworkMessageType = Field(default=NetworkMessageType.TICKET_TRACE_RESPONSE)


class NetworkTicket(NetworkMessage):
    tckuuid:      str             = Field(default_factory=get_uuid_str)
    error:        Optional[str]   = Field(default=None)
    create_time:  float           = Field(default=None)
    service_time: Optional[float] = Field(default=None)
    tracing:      bool            = Field(default=False)

    form: Union[
        CreatePeer,
        DiscoverPeer,
        GetPeers,
        GetRoutes,
        SyncProcess,
        WriteFile,
        LoadFile
    ] = Field()

    type: Literal[
        NetworkMessageType.TICKET_REQUEST,
        NetworkMessageType.TICKET_RESPONSE
    ] = Field(default=NetworkMessageType.TICKET_REQUEST)
