from pydantic import BaseModel, Field, StrictBool

class Route(BaseModel):
    agtuuid: str        = Field()
    gtwuuid: str        = Field()
    weight:  int        = Field()
    objuuid: str | None = Field(default=None)
    coluuid: str | None = Field(default=None)


class Peer(BaseModel):
    agtuuid:      str | None   = Field(default=None)
    polling:      StrictBool   = Field(default=False)
    destroy_time: float | None = Field(default=None)
    refresh_time: float | None = Field(default=None)
    url:          str | None   = Field(default=None)
    objuuid:      str | None   = Field(default=None)
    coluuid:      str | None   = Field(default=None)
