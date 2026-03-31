from enum import StrEnum, auto


class UpperCaseStrEnum(StrEnum):
    """A string enum that converts to uppercase string representation."""
    def __str__(self) -> str:
        return str(self.value).upper()


class ControlFormType(UpperCaseStrEnum):
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


class NetworkMessageType(UpperCaseStrEnum):
    ADVERTISEMENT         = auto()
    MESSAGES_REQUEST      = auto()
    MESSAGES_RESPONSE     = auto()
    TICKET_REQUEST        = auto()
    TICKET_RESPONSE       = auto()
    TICKET_TRACE_RESPONSE = auto()
    PING                  = auto()
    ACKNOWLEDGEMENT       = auto()
