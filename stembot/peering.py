"""Peer and route management for network topology discovery and maintenance.

This module handles the complete lifecycle of peers and routes in the stembot network:
- Peer discovery, creation, and lifecycle management with TTL and polling support
- Route creation and aging to maintain optimal paths through the network
- Route advertisement processing to discover new network paths
- Network topology cleanup and pruning of expired entries

Peers represent known agents in the network, with optional direct URLs for communication
and polling flags to enable message polling instead of pull-based requests. Routes represent
paths to reach other agents either directly or through gateway peers, with weights indicating
path cost. All peer and route data is maintained in both persistent storage and in-memory
caches for fast lookups during message routing.

Key functions:
- touch_peer(): Refresh or create peer entry
- create_peer(): Register a new peer with optional TTL and polling
- process_route_advertisement(): Handle incoming route information from peers
- create_route_advertisement(): Build advertisements to share local topology
- prune(): Clean up expired and invalid peers and routes
"""

from time import time
from typing import List

from stembot.dao import Collection
from stembot.models.config import CONFIG
from stembot.models.network import Advertisement
from stembot.models.routing import Peer, Route

def touch_peer(agtuuid: str) -> None:
    """Touch a peer to refresh its timestamps or create it if not present.

    Updates the refresh time for an existing peer with a valid URL. If the peer
    doesn't exist or has expired (no URL and refresh time exceeded), creates it
    with the configured peer timeout value.

    Args:
        agtuuid: The agent UUID of the peer to touch.
    """
    peers = Collection[Peer]('peers', in_memory=True).find(agtuuid=agtuuid)

    if len(peers) == 0:
        create_peer(agtuuid, ttl=CONFIG.peer_timeout_secs)
    else:
        if (
            not peers[0].object.url and
            peers[0].object.refresh_time and
            peers[0].object.refresh_time < time()
        ):
            create_peer(agtuuid, ttl=CONFIG.peer_timeout_secs)


def delete_peer(agtuuid: str) -> None:
    """Delete a peer from both in-memory and persistent storage.

    Removes all instances of a peer identified by its agent UUID from both
    the in-memory and persistent peer collections.

    Args:
        agtuuid: The agent UUID of the peer to delete.
    """
    for peer in Collection[Peer]('peers', in_memory=True).find(agtuuid=agtuuid):
        peer.destroy()

    for peer in Collection[Peer]('peers').find(agtuuid=agtuuid):
        peer.destroy()


def delete_peers() -> None:
    """Delete all peers from both in-memory and persistent storage.

    Clears the entire peer collection, removing all peers from both the
    in-memory cache and persistent storage.
    """
    peers = Collection[Peer]('peers')

    for peer in peers.find():
        peer.destroy()

    peers = Collection[Peer]('peers', in_memory=True)

    for peer in peers.find():
        peer.destroy()


def create_peer(agtuuid: str, url: str | None = None, ttl: int | None = None, polling: bool = False) -> object:
    """Create or update a peer in both in-memory and persistent storage.

    Creates a new peer or updates an existing one with the specified parameters.
    If a TTL (time-to-live) value is provided, sets destroy and refresh times based
    on the configured peer timeout and refresh intervals. Maintains the peer in both
    in-memory and persistent collections.

    Args:
        agtuuid: The agent UUID of the peer.
        url: Optional URL for direct communication with the peer.
        ttl: Optional time-to-live in seconds. If provided, sets expiration times.
        polling: Whether to enable polling mode for this peer (default: False).

    Returns:
        The peer object from the in-memory collection.
    """
    peer_collection = Collection[Peer]('peers')

    peers = peer_collection.find(agtuuid=agtuuid)

    if len(peers) == 1:
        peer = peers[0]
    else:
        peer = peer_collection.get_object()

    peer.object.agtuuid = agtuuid
    peer.object.url     = url
    peer.object.polling = polling

    if ttl:
        peer.object.destroy_time = time() + ttl
        peer.object.refresh_time = time() + CONFIG.peer_refresh_secs
    else:
        peer.object.destroy_time = None
        peer.object.refresh_time = None

    peer.commit()

    peer_collection_in_memory = Collection[Peer]('peers', in_memory=True)

    peers = peer_collection_in_memory.find(agtuuid=agtuuid)

    if len(peers) == 1:
        peer = peers[0]
    else:
        peer = peer_collection_in_memory.get_object()

    peer.object.agtuuid = agtuuid
    peer.object.url     = url
    peer.object.polling = polling

    if ttl:
        peer.object.destroy_time = time() + ttl
        peer.object.refresh_time = time() + CONFIG.peer_refresh_secs
    else:
        peer.object.destroy_time = None
        peer.object.refresh_time = None

    peer.commit()

    return peer


def delete_route(agtuuid: str, gtwuuid: str) -> None:
    """Delete a specific route from the in-memory route collection.

    Removes a route identified by its destination agent UUID and gateway UUID
    from the in-memory route cache.

    Args:
        agtuuid: The destination agent UUID of the route.
        gtwuuid: The gateway agent UUID of the route.
    """
    routes = Collection[Route]('routes', in_memory=True)
    for route in routes.find(agtuuid=agtuuid, gtwuuid=gtwuuid):
        route.destroy()


def age_routes(v: int) -> None:
    """Increase the weight of all routes by a value and remove those exceeding max weight.

    Implements route aging by incrementing the weight of all routes by the specified
    value. Routes that exceed the configured maximum weight are removed from the
    collection, effectively aging them out of the system.

    Args:
        v: The amount to increment each route's weight by.
    """
    for route in Collection[Route]('routes', in_memory=True).find():
        if route.object.weight > CONFIG.max_weight:
            route.destroy()
        else:
            route.object.weight = route.object.weight + v
            route.commit()


def create_route(agtuuid: str, gtwuuid: str, weight: int) -> None:
    """Create or update a route in the in-memory route collection.

    Creates a new route or updates an existing one with better (lower) weight.
    If multiple routes exist for the same agtuuid/gtwuuid pair, removes duplicates
    and creates a single route. Routes are stored in the in-memory collection only.

    Args:
        agtuuid: The destination agent UUID of the route.
        gtwuuid: The gateway agent UUID through which to reach the destination.
        weight: The weight/cost of the route (lower is better).
    """
    routes = Collection[Route]('routes', in_memory=True)

    matches = routes.find(agtuuid=agtuuid, gtwuuid=gtwuuid)

    if len(matches) > 1:
        # Shouldn't be more the 1 route agtuuid/gtwuuid
        # If so, empty the collection and create a new route
        for route in matches:
            route.destroy()

        routes.build_object(
            gtwuuid=gtwuuid,
            agtuuid=agtuuid,
            weight=weight
        )
    elif len(matches) == 1:
        # Already have this route but at a higher weight
        # Set the weight to the lower, incoming weight
        route = matches[0]
        if route.object.weight > weight:
            route.object.weight = weight
            route.commit()
    else:
        # Never seen this agtuuid/gtwuuid combination before
        # So create the route.
        routes.build_object(
            gtwuuid=gtwuuid,
            agtuuid=agtuuid,
            weight=weight
        )


def process_route_advertisement(advertisement: Advertisement) -> None:
    """Process a route advertisement and create routes for advertised destinations.

    Extracts routes from an advertisement received from another agent and creates
    local routes to those destinations through the advertising agent as a gateway.
    Ignores routes to self and already-known peers. Increments advertised weights
    by 1 to account for the additional hop through this agent.

    Args:
        advertisement: The route advertisement from a peer.
    """
    peers = Collection[Peer]('peers', in_memory=True)

    ignored_agtuuids = [CONFIG.agtuuid] + [peer.object.agtuuid for peer in peers.find()]

    for route in [r for r in advertisement.routes if r.agtuuid not in ignored_agtuuids]:
        create_route(
            route.agtuuid,
            advertisement.agtuuid,
            route.weight + 1
        )

    prune()


def get_peers() -> List[Peer]:
    """Get all peers from the in-memory peer collection.

    Returns:
        A list of all peer objects currently in the in-memory collection.
    """
    return [
        item.object for item
        in Collection[Peer]('peers', in_memory=True).find()
    ]


def get_routes() -> List[Route]:
    """Get all routes from the in-memory route collection.

    Returns:
        A list of all route objects currently in the in-memory collection.
    """
    return [
        item.object for item
        in Collection[Route]('routes', in_memory=True).find()
    ]


def prune() -> None:
    """Remove expired peers and routes with invalid gateways from collections.

    Cleans up the in-memory collections by removing deceased peers (whose destroy_time
    has passed) and routes that point to non-existent or locally-originated gateways.
    Helps maintain consistency in the network topology state.
    """
    routes       = Collection[Route]('routes', in_memory=True)
    peers_in_ram = Collection[Peer]('peers', in_memory=True)
    peers        = Collection[Peer]('peers')

    peer_agtuuids = []

    for peer in peers.find() + peers_in_ram.find():
        if peer.object.destroy_time and peer.object.destroy_time < time():
            peer.destroy()
            continue
        peer_agtuuids.append(peer.object.agtuuid)

    for route in routes.find():
        if (
            route.object.gtwuuid not in peer_agtuuids or
            len(peers_in_ram.find_objuuids(agtuuid=route.object.agtuuid)) > 0 or
            route.object.agtuuid == CONFIG.agtuuid
        ):
            route.destroy()


# pylint: disable=no-member
def create_route_advertisement() -> Advertisement:
    """Create a route advertisement with current routes and directly-known peers.

    Builds an advertisement message containing all routes in the in-memory collection
    and routes to all known peers with no direct URL. This advertisement can be sent
    to peers to help them discover network topology.

    Returns:
        An Advertisement object containing current routes and peer information.
    """
    prune()

    routes = Collection[Route]('routes', in_memory=True)
    peers = Collection[Peer]('peers', in_memory=True)

    advertisement = Advertisement(agtuuid=CONFIG.agtuuid)

    for route in routes.find():
        route.object.gtwuuid = CONFIG.agtuuid
        advertisement.routes.append(route.object)

    for peer in peers.find(agtuuid="$!eq:None"):
        route = Route(agtuuid=peer.object.agtuuid, weight=0,gtwuuid=CONFIG.agtuuid)
        advertisement.routes.append(route)

    return advertisement


def init_peers() -> None:
    """Initialize in-memory peer collection from persistent storage.

    Loads all peers from the persistent peer collection into the in-memory cache.
    Called at module startup to populate the in-memory peer state.
    """
    ram_peers = Collection[Peer]('peers', in_memory=True)
    peers = Collection[Peer]('peers')
    for peer in peers.find():
        ram_peers.upsert_object(peer.object)


collection = Collection[Peer]('peers')
collection.create_attribute('agtuuid', "/agtuuid")
collection.create_attribute('polling', "/polling")
collection.create_attribute('url', "/url")

collection = Collection[Peer]('peers', in_memory=True)
collection.create_attribute('agtuuid', "/agtuuid")
collection.create_attribute('polling', "/polling")
collection.create_attribute('url', "/url")

collection = Collection[Route]('routes', in_memory=True)
collection.create_attribute('agtuuid', "/agtuuid")
collection.create_attribute('gtwuuid', "/gtwuuid")
collection.create_attribute('weight', "/weight")

init_peers()
