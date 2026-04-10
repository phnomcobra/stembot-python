"""This module implements the schema for networkmessages."""
from time import time
from typing import List, Literal, Union

from pydantic import BaseModel, Field, ConfigDict

from stembot.dao.utils import get_uuid_str
from stembot.enums import NetworkMessageType
from stembot.models.config import CONFIG
from stembot.models.control import CreatePeer, DiscoverPeer, GetConfig, GetPeers
from stembot.models.control import GetRoutes, LoadFile, SyncProcess, WriteFile
from stembot.models.routing import Route


class NetworkMessage(BaseModel):
    """Base class for all network messages passed between agents.

    This is the foundational message type for all inter-agent communication.
    All network messages share these core properties for routing and tracking.

    Attributes:
        type: The type of network message (PING, ADVERTISEMENT, TICKET_REQUEST, etc.).
        dest: UUID of the destination agent (None means broadcast).
        src: UUID of the source agent that originated the message.
        isrc: UUID of the immediate sender (for tracking through hops).
        timestamp: Unix timestamp when the message was created.
        objuuid: Optional object UUID for data object association.
        coluuid: Optional collection UUID for data collection association.
    """
    model_config = ConfigDict(extra='allow')

    type:      NetworkMessageType = Field()
    dest:      str | None         = Field(default=None)
    src:       str                = Field(default=CONFIG.agtuuid)
    isrc:      str | None         = Field(default=None)
    timestamp: float | None       = Field(default_factory=time)
    objuuid:   str | None         = Field(default=None)
    coluuid:   str | None         = Field(default=None)


class Ping(NetworkMessage):
    """A simple network ping message to test connectivity.

    Used to verify that a peer agent is reachable and responsive.
    The response is typically an Acknowledgement message.

    Attributes:
        type: Always set to NetworkMessageType.PING.
    """
    type: NetworkMessageType = Field(default=NetworkMessageType.PING)


class NetworkMessagesRequest(NetworkMessage):
    """Request to retrieve pending messages from an agent.

    Polls a peer agent for any messages that are waiting to be delivered.
    The response contains a NetworkMessagesResponse with a list of messages.

    Attributes:
        type: Always set to NetworkMessageType.MESSAGES_REQUEST.
    """
    type: NetworkMessageType = Field(default=NetworkMessageType.MESSAGES_REQUEST)


class Acknowledgement(NetworkMessage):
    """Acknowledgement of a received message.

    Confirms receipt of a message and optionally reports status or errors.
    Used for both successful processing and error reporting.

    Attributes:
        ack_type: The type of the original message being acknowledged.
        forwarded: UUID of agent that forwarded this acknowledgement (if any).
        error: Optional error message if processing failed.
        type: Always set to NetworkMessageType.ACKNOWLEDGEMENT.
    """
    ack_type:  NetworkMessageType = Field()
    forwarded: str | None         = Field(default=None)
    error:     str | None         = Field(default=None)
    type:      NetworkMessageType = Field(default=NetworkMessageType.ACKNOWLEDGEMENT)


class Advertisement(NetworkMessage):
    """Advertisement of routes known by an agent.

    Broadcasts routing information to peers to help establish network paths.
    Contains a list of routes the agent knows about.

    Attributes:
        routes: List of Route objects the agent is advertising.
        agtuuid: UUID of the advertising agent.
        type: Always set to NetworkMessageType.ADVERTISEMENT.
    """
    routes:  List[Route]        = Field(default=[])
    agtuuid: str                = Field()
    type:    NetworkMessageType = Field(default=NetworkMessageType.ADVERTISEMENT)


class NetworkMessagesResponse(NetworkMessage):
    """Response to a NetworkMessagesRequest containing pending messages.

    Returns a list of messages that were waiting to be delivered to the requester.

    Attributes:
        messages: List of pending NetworkMessage objects.
        type: Always set to NetworkMessageType.MESSAGES_RESPONSE.
    """
    messages: List[NetworkMessage] = Field(default=[])
    type:     NetworkMessageType   = Field(default=NetworkMessageType.MESSAGES_RESPONSE)


class TicketTraceResponse(NetworkMessage):
    """Response indicating a ticket has been traced through the network.

    Reports that a ticket passed through an agent on its way to the destination.
    Used for tracking ticket routing through peers.

    Attributes:
        tckuuid: UUID of the ticket being traced.
        hop_time: Timestamp when this hop was recorded.
        network_ticket_type: Type of the original network ticket.
        type: Always set to NetworkMessageType.TICKET_TRACE_RESPONSE.
    """
    tckuuid:             str                = Field()
    hop_time:            float              = Field(default_factory=time)
    network_ticket_type: NetworkMessageType = Field()
    type:                NetworkMessageType = Field(default=NetworkMessageType.TICKET_TRACE_RESPONSE)


class NetworkTicket(NetworkMessage):
    """A ticket for asynchronous message delivery across the network.

    Wraps a control form with network metadata for delivery to peers.
    Supports tracing the path through multiple agents.

    Attributes:
        tckuuid: Unique ticket UUID for identification and tracking.
        error: Optional error message if processing failed.
        create_time: Timestamp when the ticket was created.
        service_time: Time in seconds taken to service the ticket.
        tracing: Whether to record hops through the network.
        form: The wrapped control form being delivered.
        type: Ticket type (TICKET_REQUEST or TICKET_RESPONSE).
    """
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
        LoadFile,
        GetConfig
    ] = Field()

    type: Literal[
        NetworkMessageType.TICKET_REQUEST,
        NetworkMessageType.TICKET_RESPONSE
    ] = Field(default=NetworkMessageType.TICKET_REQUEST)
