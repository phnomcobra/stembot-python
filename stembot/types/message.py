"""This module implements the schema for messages."""
from enum import Enum
from typing import Dict, List, Optional, Union

import cherrypy
from pydantic import BaseModel, Field, PositiveFloat, PositiveInt, StrictBool, ConfigDict

from stembot.dao.utils import get_uuid_str

# remove me later
# cherrypy.config.update({ 'agtuuid': 'agtuuid' })


class Peer(BaseModel):
    agtuuid: str           = Field()
    polling: StrictBool    = Field(default=False)
    url:     Optional[str] = Field(default=None)

class Route(BaseModel):
    agtuuid: str        = Field()
    weight: PositiveInt = Field()


class RequestType(Enum):
    CREATE_PEER      = "CREATE_PEER"
    DISCOVER_PEER    = "DISCOVER_PEER"
    DELETE_PEER      = "DELETE_PEER"
    DELETE_PEERS     = "DELETE_PEERS"
    GET_PEERS        = "GET_PEERS"
    GET_ROUTES       = "GET_ROUTES"

class Request(BaseModel):
    """Common properties"""
    model_config = ConfigDict(extra='allow')

    type: RequestType = Field()

class CreatePeerRequest(Request):
    peer: Peer = Field()

class DiscoverPeerRequest(Request):
    peer: Peer = Field()

class DeletePeerRequest(Request):
    agtuuid: str = Field()


class ResponseType(Enum):
    CREATED_PEER    = "CREATED_PEER"
    DISCOVERED_PEER = "DISCOVERED_PEER"
    DELETED_PEER    = "DELETED_PEER"
    DELETED_PEERS   = "DELETED_PEERS"
    GOT_ROUTES      = "GOT_ROUTES"
    GOT_PEERS       = "GOT_PEERS"

class Response(BaseModel):
    """Common properties"""
    model_config = ConfigDict(extra='allow')

    type: ResponseType = Field()

class CreatedPeerResponse(Response):
    peer: Peer = Field()

class DiscoveredPeerResponse(Response):
    peer: Peer = Field()

class DeletedPeerResponse(Response):
    peer: Peer = Field()

class DeletedPeersResponse(Response):
    peer: List[Peer] = Field()

class GotPeersResponse(Response):
    peer: List[Peer] = Field()

class GotRoutesResponse(Response):
    peer: List[Route] = Field()



class MessageType(Enum):
    CREATE_PEER      = "CREATE_PEER"
    DISCOVER_PEER    = "DISCOVER_PEER"
    DELETE_PEER      = "DELETE_PEER"
    DELETE_PEERS     = "DELETE_PEERS"
    GET_PEERS        = "GET_PEERS"
    GET_ROUTES       = "GET_ROUTES"
    ADVERTISEMENT    = "ADVERTISEMENT"
    PING             = "PING"
    PULL_MESSAGES    = "PULL_MESSAGES"
    TICKET_REQUEST   = "TICKET_REQUEST"
    TICKET_RESPONSE  = "TICKET_RESPONSE"
    CASCADE_REQUEST  = "CASCADE_REQUEST"
    CASCADE_RESPONSE = "CASCADE_RESPONSE"
    CREATE_TICKET    = "CREATE_TICKET"
    READ_TICKET      = "READ_TICKET"
    DELETE_TICKET    = "DELETE_TICKET"

    def __str__(self) -> str:
        return str(self.name)


class Message(BaseModel):
    """Common properties"""
    model_config = ConfigDict(extra='allow')

    dest:      str             = Field(default=cherrypy.config.get('agtuuid'))
    type:      MessageType     = Field()
    isrc:      Optional[str]   = Field(default=None)
    timestamp: Optional[float] = Field(default=None)





class CreatePeer(Message):
    url:     Optional[str]                               = Field(default=None)
    ttl:     Optional[Union[PositiveInt, PositiveFloat]] = Field(default=None)
    polling: StrictBool                                  = Field(default=False)
    agtuuid: str


class DiscoverPeer(Message):
    url:     str                                         = Field()
    ttl:     Optional[Union[PositiveInt, PositiveFloat]] = Field(default=None)
    polling: StrictBool                                  = Field(default=False)


class DeletePeer(Message):
    agtuuid: str = Field()

class DeletedPeer(Message):
    peer: Peer = Field()


class DeletePeers(Message):
    pass

class DeletedPeers(Message):
    peer: List[Peer] = Field()

class GetPeers(Message):
    pass

class GotPeers(Message):
    peer: List[Peer] = Field()

class GetRoutes(Message):
    pass

class GotRoutes(Message):
    peer: List[Route] = Field()


class Advertisement(Message):
    routes: List[Route] = Field()
    agtuuid: str        = Field()


class Ping(Message):
    create_time: float = Field()


class GetCounters(Message):
    pass

class GotCounters(Message):
    counters: Dict[str, int] = Field()

class PullMessages(Message):
    pass

class PulledMessages(Message):
    messages: List[Message] = Field()

class Ticket(Message):
    tckuuid:      str                = Field(default=get_uuid_str())
    src:          str                = Field(default=cherrypy.config.get('agtuuid'))
    request:      Request            = Field()
    response:     Optional[Response] = Field(default=None)
    create_time:  Optional[float]    = Field(default=None)
    service_time: Optional[float]    = Field(default=None)

class TicketRequest(Ticket):
    pass

class TicketResponse(Ticket):
    pass

class CreateTicket(Ticket):
    pass

class ReadTicket(Message):
    tckuuid: str = Field()

class DeleteTicket(Message):
    tckuuid: str = Field()

class Cascade(Message):
    cscuuid:      str             = Field(default=get_uuid_str())
    src:          str             = Field(default=cherrypy.config.get('agtuuid'))
    request:      Request         = Field()
    responses:    List[Response]  = Field(default=[])
    create_time:  Optional[float] = Field(default=None)
    service_time: Optional[float] = Field(default=None)
    etags:        List[str]       = Field(default=[])
    ftags:        List[str]       = Field(default=[])
    anonymous:    bool            = Field(default=False)

class CascadeRequest(Cascade):
    pass

class CascadeResponse(Cascade):
    pass




item = """{
    "type": "CREATE_PEER",
    "agtuuid": "test peer"
}"""

msg = CreatePeer(type=MessageType.CREATE_PEER, agtuuid="test peer")
j = msg.model_dump_json()

message = Message.model_validate_json(j)
message = Message.model_validate_json(item)

match message.type:
    case MessageType.CREATE_PEER:
        c = CreatePeer.model_validate(message.model_extra)
        print(c)
    case _:
        pass

# peer = CreatePeer(**msg.dict())
# print(peer)
# print(peer.json())
