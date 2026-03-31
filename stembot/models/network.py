"""This module implements the schema for messages."""
from time import time
from typing import List, Literal, Union

from pydantic import BaseModel, Field, ConfigDict

from stembot.dao.utils import get_uuid_str
from stembot.dao import kvstore
from stembot.enums import NetworkMessageType
from stembot.models.control import CreatePeer, DiscoverPeer, GetPeers, GetRoutes, LoadFile, SyncProcess, WriteFile
from stembot.models.routing import Route


class NetworkMessage(BaseModel):
    """Common properties"""
    model_config = ConfigDict(extra='allow')

    type:      NetworkMessageType = Field()
    dest:      str | None         = Field(default=None)
    src:       str                = Field(default=kvstore.get('agtuuid'))
    isrc:      str | None         = Field(default=None)
    timestamp: float | None       = Field(default_factory=time)
    objuuid:   str | None         = Field(default=None)
    coluuid:   str | None         = Field(default=None)


class Ping(NetworkMessage):
    type: NetworkMessageType = Field(default=NetworkMessageType.PING)


class NetworkMessagesRequest(NetworkMessage):
    type: NetworkMessageType = Field(default=NetworkMessageType.MESSAGES_REQUEST)


class Acknowledgement(NetworkMessage):
    ack_type:  NetworkMessageType = Field()
    forwarded: str | None         = Field(default=None)
    error:     str | None         = Field(default=None)
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
    error:        str | None      = Field(default=None)
    create_time:  float | None    = Field(default=None)
    service_time: float | None    = Field(default=None)
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
