"""Enumeration types for control forms and network messages.

Defines string-based enumerations that represent the types of control forms
and network messages used in inter-agent communication. All enum values are
automatically converted to uppercase in their string representation.
"""

from enum import StrEnum, auto


class UpperCaseStrEnum(StrEnum):
    """A string enum that converts to uppercase string representation.

    Extends StrEnum to automatically convert all enum values to uppercase when
    converted to string. Useful for protocol messages that expect uppercase type names.
    """
    def __str__(self) -> str:
        return str(self.value).upper()


class ControlFormType(UpperCaseStrEnum):
    """Control form operation types for inter-agent requests and responses.

    Defines the different types of control operations that can be requested
    through the control form protocol, including peer management, file operations,
    process execution, and ticketing.

    Attributes:
        CREATE_PEER: Create a new peer relationship with known URL.
        DISCOVER_PEER: Discover and create a peer via ping discovery.
        DELETE_PEERS: Delete one or more peers by UUID.
        GET_PEERS: Retrieve the list of known peers.
        GET_ROUTES: Retrieve the current routing table.
        SYNC_PROCESS: Synchronize and execute a remote process.
        WRITE_FILE: Write data to a file on the remote agent.
        LOAD_FILE: Load and retrieve file data from the remote agent.
        CREATE_TICKET: Create a new ticket for routed messages.
        READ_TICKET: Read the contents of a ticket.
        DELETE_TICKET: Delete a ticket (deprecated).
        CLOSE_TICKET: Close and remove a ticket.
        GET_CONFIG: Retrieve the agent's current configuration.
    """
    CREATE_PEER    = auto()
    DISCOVER_PEER  = auto()
    DELETE_PEERS   = auto()
    GET_PEERS      = auto()
    GET_ROUTES     = auto()
    SYNC_PROCESS   = auto()
    WRITE_FILE     = auto()
    LOAD_FILE      = auto()
    CREATE_TICKET  = auto()
    READ_TICKET    = auto()
    DELETE_TICKET  = auto()
    CLOSE_TICKET   = auto()
    GET_CONFIG     = auto()


class NetworkMessageType(UpperCaseStrEnum):
    """Network message types for inter-agent communication.

    Defines the different message types used in the network message protocol,
    including route advertisements, message delivery, ticket exchanges, and
    acknowledgements. Messages flow through the network via the MPI endpoint.

    Attributes:
        ADVERTISEMENT: Route advertisement from a peer.
        MESSAGES_REQUEST: Request to retrieve pending messages from a peer.
        MESSAGES_RESPONSE: Response containing pending messages for requester.
        TICKET_REQUEST: Request to execute a control form via ticket mechanism.
        TICKET_RESPONSE: Response with ticket execution results.
        TICKET_TRACE_RESPONSE: Trace response for multi-hop ticket delivery.
        PING: Simple connectivity check message.
        ACKNOWLEDGEMENT: Generic acknowledgement of message receipt.
    """
    ADVERTISEMENT         = auto()
    MESSAGES_REQUEST      = auto()
    MESSAGES_RESPONSE     = auto()
    TICKET_REQUEST        = auto()
    TICKET_RESPONSE       = auto()
    TICKET_TRACE_RESPONSE = auto()
    PING                  = auto()
    ACKNOWLEDGEMENT       = auto()
