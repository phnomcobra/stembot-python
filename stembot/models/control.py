"""This module implements the schema for control form messages."""
from time import time
from typing import List, Literal, Union
from typing_extensions import Annotated

from pydantic import AfterValidator, BaseModel, Field, HttpUrl, PositiveFloat, PositiveInt, StrictBool, ConfigDict

from stembot.dao.utils import get_uuid_str
from stembot.enums import ControlFormType
from stembot.models.config import CONFIG
from stembot.models.routing import Peer, Route


class ControlForm(BaseModel):
    """Base control form for all control form types.

    This is the root class for all control forms sent across the network.
    It defines the common properties shared by all control form subtypes.

    Attributes:
        type: The type of control form message (e.g., CREATE_PEER, SYNC_PROCESS).
        error: Optional error message if the form processing failed.
        objuuid: Optional object UUID for data object association.
        coluuid: Optional collection UUID for data collection association.
    """
    model_config = ConfigDict(extra='allow')

    type:    ControlFormType = Field()
    error:   str | None      = Field(default=None)
    objuuid: str | None      = Field(default=None)
    coluuid: str | None      = Field(default=None)


class LoadFile(ControlForm):
    """Request to load a file from the remote agent.

    Specifies a file path on the remote system and requests its contents.
    The response includes the file data, size, and MD5 checksum.

    Attributes:
        b64zlib: Base64-encoded zlib-compressed file content (in response).
        path: The file path on the remote system to load.
        error: Optional error message if the load operation failed.
        size: The size of the file in bytes.
        md5sum: MD5 checksum of the file for integrity verification.
        type: Always set to ControlFormType.LOAD_FILE.
    """
    b64zlib: str | None      = Field(default=None)
    path:    str             = Field()
    error:   str | None      = Field(default=None)
    size:    int | None      = Field(default=None)
    md5sum:  str | None      = Field(default=None)
    type:    ControlFormType = Field(default=ControlFormType.LOAD_FILE)


class WriteFile(ControlForm):
    """Request to write a file to the remote agent.

    Specifies a file path on the remote system and provides content to write.
    The response includes the size and MD5 checksum of the written file.

    Attributes:
        b64zlib: Base64-encoded zlib-compressed file content to write.
        path: The file path on the remote system where to write the file.
        error: Optional error message if the write operation failed.
        size: The size of the written file in bytes.
        md5sum: MD5 checksum of the written file for integrity verification.
        type: Always set to ControlFormType.WRITE_FILE.
    """
    b64zlib: str             = Field()
    path:    str             = Field()
    error:   str | None      = Field(default=None)
    size:    int | None      = Field(default=None)
    md5sum:  str | None      = Field(default=None)
    type:    ControlFormType = Field(default=ControlFormType.WRITE_FILE)


class SyncProcess(ControlForm):
    """Request to synchronously execute a process on the remote agent.

    Sends a command to be executed on the remote system and waits for completion.
    Returns the process output, error output, and exit status.

    Attributes:
        timeout: Maximum time in seconds to wait for process completion (default: 15).
        command: Command to execute as a string or list of arguments.
        stdout: Standard output from the process execution.
        stderr: Standard error output from the process execution.
        status: Process exit status code.
        start_time: Timestamp when the process started.
        elapsed_time: Total time in seconds the process ran.
        type: Always set to ControlFormType.SYNC_PROCESS.
    """
    timeout:      int             = Field(default=15)
    command:      str | List[str] = Field()
    stdout:       str | None      = Field(default=None)
    stderr:       str | None      = Field(default=None)
    status:       int | None      = Field(default=None)
    start_time:   float | None    = Field(default=None)
    elapsed_time: float | None    = Field(default=None)
    type:         ControlFormType = Field(default=ControlFormType.SYNC_PROCESS)


class CreatePeer(ControlForm):
    """Request to create a peer connection to another agent.

    Establishes a new peering relationship with another agent at the specified URL.
    Includes TTL for the peer relationship and optional polling capability.

    Attributes:
        url: HTTP/HTTPS URL of the remote agent to peer with.
        ttl: Time-to-live for the peer relationship in seconds.
        polling: Whether this peer should be polled for messages.
        agtuuid: UUID of the agent being peered with.
        type: Always set to ControlFormType.CREATE_PEER.
    """
    url:     Annotated[HttpUrl, AfterValidator(HttpUrl.__str__)] | None = Field(default=None)
    ttl:     PositiveInt | PositiveFloat | None                         = Field(default=None)
    polling: StrictBool                                                 = Field(default=False)
    agtuuid: str                                                        = Field()
    type:    ControlFormType                                            = Field(default=ControlFormType.CREATE_PEER)


class DiscoverPeer(ControlForm):
    """Request to discover and create a peer connection via URL.

    Discovers a peer agent by URL, retrieves its UUID, and creates a peer relationship.
    Includes TTL and optional polling configuration.

    Attributes:
        agtuuid: UUID of the discovered agent (populated in response).
        url: HTTP/HTTPS URL of the agent to discover.
        ttl: Time-to-live for the peer relationship in seconds.
        polling: Whether this peer should be polled for messages.
        error: Optional error message if discovery failed.
        type: Always set to ControlFormType.DISCOVER_PEER.
    """
    agtuuid: str | None                         = Field(default=None)
    url:     str                                = Field()
    ttl:     PositiveInt | PositiveFloat | None = Field(default=None)
    polling: StrictBool                         = Field(default=False)
    error:   str | None                         = Field(default=None)
    type:    ControlFormType                    = Field(default=ControlFormType.DISCOVER_PEER)


class DeletePeers(ControlForm):
    """Request to delete one or more peers.

    Removes peer relationships with specified agents or all peers if none specified.

    Attributes:
        agtuuids: List of peer UUIDs to delete. If None, deletes all peers.
        type: Always set to ControlFormType.DELETE_PEERS.
    """
    agtuuids: list[str] | None = Field(default=None)
    type:     ControlFormType  = Field(default=ControlFormType.DELETE_PEERS)


class GetPeers(ControlForm):
    """Request to retrieve a list of all current peer connections.

    Queries the agent for information about its established peer relationships.

    Attributes:
        peers: List of Peer objects representing current peer connections.
        type: Always set to ControlFormType.GET_PEERS.
    """
    peers: List[Peer]      = Field(default=[])
    type:  ControlFormType = Field(default=ControlFormType.GET_PEERS)


class GetRoutes(ControlForm):
    """Request to retrieve the agent's routing table.

    Queries the agent for its known routes to other agents in the network.

    Attributes:
        routes: List of Route objects representing known routes.
        type: Always set to ControlFormType.GET_ROUTES.
    """
    routes: List[Route]     = Field(default=[])
    type:   ControlFormType = Field(default=ControlFormType.GET_ROUTES)


class GetConfig(ControlForm):
    """Request to retrieve the agent's configuration.

    Queries the agent for its current configuration settings (excluding secrets).

    Attributes:
        config: Dictionary of configuration key-value pairs.
        type: Always set to ControlFormType.GET_CONFIG.
    """
    config: dict | None     = Field(default=None)
    type:   ControlFormType = Field(default=ControlFormType.GET_CONFIG)


class Benchmark(ControlForm):
    """Request to run a benchmark test on the remote agent.

    Attributes:
        outbound_size: Size in bytes of the payload sent to the remote agent.
        inbound_size: Size in bytes of the payload received from the remote agent.
        payload: Optional string payload depending on the inbound/outbound size for testing.
        type: Always set to ControlFormType.BENCHMARK.
    """
    outbound_size: PositiveInt | None = Field()
    inbound_size:  PositiveInt | None = Field()
    payload:       str | None         = Field(default=None)
    type:          ControlFormType    = Field(default=ControlFormType.BENCHMARK)


class Hop(BaseModel):
    """Represents a single hop in a ticket trace through the network.

    Records when a ticket passed through an agent and the type of message.

    Attributes:
        agtuuid: UUID of the agent that processed this hop.
        hop_time: Timestamp when the hop was recorded.
        type_str: String representation of the message type at this hop.
    """
    agtuuid:  str   = Field()
    hop_time: float = Field()
    type_str: str   = Field()


class ControlFormTicket(ControlForm):
    """A ticket for asynchronous control form delivery and tracking.

    Wraps a control form with ticket metadata for delivery across the network
    with the ability to trace the path and measure service times.

    Attributes:
        tckuuid: Unique ticket UUID for tracking.
        src: UUID of the source agent that created the ticket.
        dst: UUID of the destination agent for the ticket.
        create_time: Timestamp when the ticket was created.
        service_time: Time in seconds the ticket took to service (if completed).
        tracing: Whether to trace the ticket's path through the network.
        hops: List of Hop objects showing the ticket's route.
        form: The wrapped control form to be delivered.
        type: Ticket type (CREATE_TICKET, READ_TICKET).
    """
    model_config = ConfigDict(extra='allow')

    tckuuid:      str          = Field(default_factory=get_uuid_str)
    src:          str          = Field(default=CONFIG.agtuuid)
    dst:          str          = Field(default=CONFIG.agtuuid)
    create_time:  float        = Field(default_factory=time)
    service_time: float | None = Field(default=None)
    tracing:      bool         = Field(default=False)
    hops:         List[Hop]    = Field(default=[])

    form: Union[
        CreatePeer,
        DiscoverPeer,
        DeletePeers,
        GetPeers,
        GetRoutes,
        GetConfig,
        SyncProcess,
        WriteFile,
        LoadFile,
        Benchmark
    ] = Field()

    type: Literal[
        ControlFormType.CREATE_TICKET,
        ControlFormType.READ_TICKET,
    ] = Field(default=ControlFormType.CREATE_TICKET)


class CheckTicket(ControlForm):
    """Response form for a ticket check operation.

    Returned when querying the status of an existing ticket. Includes timing
    information to indicate whether the ticket has been serviced.

    Attributes:
        tckuuid: UUID of the ticket being checked.
        create_time: Timestamp when the ticket was originally created.
        service_time: Time in seconds the ticket took to service, or None if not yet complete.
        type: Always set to ControlFormType.CHECK_TICKET.
    """
    tckuuid:      str             = Field()
    create_time:  float | None    = Field(default=None)
    service_time: float | None    = Field(default=None)
    type:         ControlFormType = Field(default=ControlFormType.CHECK_TICKET)


class CloseTicket(ControlForm):
    """Request to close an existing ticket.

    Signals that the ticket result has been acknowledged and the ticket can be
    removed from the system.

    Attributes:
        tckuuid: UUID of the ticket to close.
        type: Always set to ControlFormType.CLOSE_TICKET.
    """
    tckuuid:      str             = Field()
    type:         ControlFormType = Field(default=ControlFormType.CLOSE_TICKET)
