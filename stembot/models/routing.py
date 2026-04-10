"""This module implements the schema for routing information."""
from pydantic import BaseModel, Field, StrictBool

class Route(BaseModel):
    """A route to another agent through a gateway.

    Represents a known path to reach another agent in the network through
    an intermediate gateway agent. Routes are used for routing decisions
    when sending messages across the network.

    Attributes:
        agtuuid: UUID of the destination agent that this route leads to.
        gtwuuid: UUID of the gateway agent to route through.
        weight: Route weight/cost for path selection (lower is better).
        objuuid: Optional object UUID for data object association.
        coluuid: Optional collection UUID for data collection association.
    """
    agtuuid: str        = Field()
    gtwuuid: str        = Field()
    weight:  int        = Field()
    objuuid: str | None = Field(default=None)
    coluuid: str | None = Field(default=None)


class Peer(BaseModel):
    """A peering relationship with another agent.

    Represents an established connection and information about another agent
    in the network that this agent can communicate with directly.

    Attributes:
        agtuuid: UUID of the peer agent.
        polling: Whether to poll this peer periodically for messages.
        destroy_time: Timestamp when this peer should be destroyed/removed.
        refresh_time: Timestamp when this peer's information should be refreshed.
        url: HTTP/HTTPS URL to reach the peer agent.
        objuuid: Optional object UUID for data object association.
        coluuid: Optional collection UUID for data collection association.
    """
    agtuuid:      str | None   = Field(default=None)
    polling:      StrictBool   = Field(default=False)
    destroy_time: float | None = Field(default=None)
    refresh_time: float | None = Field(default=None)
    url:          str | None   = Field(default=None)
    objuuid:      str | None   = Field(default=None)
    coluuid:      str | None   = Field(default=None)
