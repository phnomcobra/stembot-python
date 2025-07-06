from typing import Optional
from pydantic import BaseModel, Field, StrictBool

class Route(BaseModel):
    agtuuid: str           = Field()
    gtwuuid: str           = Field()
    weight:  int           = Field()
    objuuid: Optional[str] = Field(default=None)
    coluuid: Optional[str] = Field(default=None)


class Peer(BaseModel):
    agtuuid:      Optional[str]   = Field(default=None)
    polling:      StrictBool      = Field(default=False)
    destroy_time: Optional[float] = Field(default=None)
    refresh_time: Optional[float] = Field(default=None)
    url:          Optional[str]   = Field(default=None)
    objuuid:      Optional[str]   = Field(default=None)
    coluuid:      Optional[str]   = Field(default=None)
