"""This module implements the schema for messages."""
from time import time
from typing import List, Literal, Union
from typing_extensions import Annotated

from pydantic import AfterValidator, BaseModel, Field, HttpUrl, PositiveFloat, PositiveInt, StrictBool, ConfigDict

from stembot.dao.utils import get_uuid_str
from stembot.enums import ControlFormType
from stembot.models.config import CONFIG
from stembot.models.routing import Peer, Route


class ControlForm(BaseModel):
    model_config = ConfigDict(extra='allow')

    type:    ControlFormType = Field()
    error:   str | None      = Field(default=None)
    objuuid: str | None      = Field(default=None)
    coluuid: str | None      = Field(default=None)


class LoadFile(ControlForm):
    b64zlib: str | None      = Field(default=None)
    path:    str             = Field()
    error:   str | None      = Field(default=None)
    size:    int | None      = Field(default=None)
    md5sum:  str | None      = Field(default=None)
    type:    ControlFormType = Field(default=ControlFormType.LOAD_FILE)


class WriteFile(ControlForm):
    b64zlib: str             = Field()
    path:    str             = Field()
    error:   str | None      = Field(default=None)
    size:    int | None      = Field(default=None)
    md5sum:  str | None      = Field(default=None)
    type:    ControlFormType = Field(default=ControlFormType.WRITE_FILE)


class SyncProcess(ControlForm):
    timeout:      int             = Field(default=15)
    command:      str | List[str] = Field()
    stdout:       str | None      = Field(default=None)
    stderr:       str | None      = Field(default=None)
    status:       int | None      = Field(default=None)
    start_time:   float | None    = Field(default=None)
    elapsed_time: float | None    = Field(default=None)
    type:         ControlFormType = Field(default=ControlFormType.SYNC_PROCESS)


class CreatePeer(ControlForm):
    url:     Annotated[HttpUrl, AfterValidator(HttpUrl.__str__)] | None = Field(default=None)
    ttl:     PositiveInt | PositiveFloat | None                         = Field(default=None)
    polling: StrictBool                                                 = Field(default=False)
    agtuuid: str                                                        = Field()
    type:    ControlFormType                                            = Field(default=ControlFormType.CREATE_PEER)


class DiscoverPeer(ControlForm):
    agtuuid: str | None                         = Field(default=None)
    url:     str                                = Field()
    ttl:     PositiveInt | PositiveFloat | None = Field(default=None)
    polling: StrictBool                         = Field(default=False)
    error:   str | None                         = Field(default=None)
    type:    ControlFormType                    = Field(default=ControlFormType.DISCOVER_PEER)


class DeletePeers(ControlForm):
    agtuuids: list[str] | None = Field(default=None)
    type:     ControlFormType  = Field(default=ControlFormType.DELETE_PEERS)


class GetPeers(ControlForm):
    peers: List[Peer]      = Field(default=[])
    type:  ControlFormType = Field(default=ControlFormType.GET_PEERS)


class GetRoutes(ControlForm):
    routes: List[Route]     = Field(default=[])
    type:   ControlFormType = Field(default=ControlFormType.GET_ROUTES)


class Hop(BaseModel):
    agtuuid:  str   = Field()
    hop_time: float = Field()
    type_str: str   = Field()


class ControlFormTicket(ControlForm):
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
        SyncProcess,
        WriteFile,
        LoadFile
    ] = Field()

    type: Literal[
        ControlFormType.CREATE_TICKET,
        ControlFormType.READ_TICKET,
        ControlFormType.DELETE_TICKET,
        ControlFormType.CLOSE_TICKET,
    ] = Field(default=ControlFormType.CREATE_TICKET)
