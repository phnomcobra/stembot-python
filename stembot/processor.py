"""This module implements the core processing logic for the Stembot agent, including handling control forms,
routing network messages, and managing background workers for message replay, peer polling, and route advertisement.
The module defines FastAPI endpoints for receiving control forms and network messages, processes them according to
their types, and ensures secure communication through encryption. It also includes functions for creating network
tickets from control forms, routing messages to their destinations, and processing messages based on their types.
Background workers are implemented to handle periodic tasks such as replaying undelivered messages, polling peers
for new messages, and advertising routes to maintain network topology information."""
from base64 import b64encode, b64decode
from threading import Thread
from itertools import islice
import traceback
import logging

from fastapi import FastAPI, Request, Response
from Crypto.Cipher import AES

from stembot.executor.agent import AgentClient
from stembot.executor.file import load_file_to_form, write_file_from_form
from stembot.executor.process import sync_process
from stembot.logger import init_logger
from stembot.models.config import CONFIG
from stembot.ticketing import close_ticket, dedup_trace, read_ticket, service_ticket, trace_ticket
from stembot.dao import Collection
from stembot.messaging import forward_network_message, pop_network_messages, pull_network_messages
from stembot.peering import touch_peer
from stembot.peering import process_route_advertisement
from stembot.peering import age_routes
from stembot.peering import create_route_advertisement
from stembot.peering import create_peer, delete_peer, delete_peers, get_peers, get_routes
from stembot.scheduling import scheduled
from stembot.models.control import ControlForm, ControlFormType, CreatePeer, DeletePeers, DiscoverPeer, GetConfig
from stembot.models.control import GetRoutes, ControlFormTicket, LoadFile, SyncProcess, WriteFile, GetPeers
from stembot.models.network import Acknowledgement, Advertisement, NetworkMessage, NetworkMessageType, Ping
from stembot.models.network import NetworkMessagesRequest, NetworkMessagesResponse, NetworkTicket, TicketTraceResponse
from stembot.models.routing import Peer

# Initialize the logger when the module is imported
# Worker threads use this module as an entry point,
# so we need to ensure the logger is initialized at the module level to cover worker threads
init_logger()

# Create FastAPI app instance
app = FastAPI()


@app.post("/control")
async def control_handler(request: Request) -> Response:
    """Control form handler for processing incoming control forms. This endpoint receives encrypted control forms,
    decrypts them, processes the contained form, and returns an encrypted response. The request and response cycle
    preserves type information through the use of Pydantic models, allowing for structured data exchange between
    agents. The processing logic is handled in the `process_control_form` function, which matches on the form type
    and executes the corresponding action. This endpoint will always return the same type of control form that was
    sent in the request, populated with the response data or error information if an exception occurred.

    Args:
        request: The incoming HTTP request containing the encrypted control form.

    Returns:
        An HTTP response containing the encrypted control form response.
    """
    cipher_b64     = await request.body()
    cipher_text    = b64decode(cipher_b64)
    nonce          = b64decode(request.headers['Nonce'].encode())
    tag            = b64decode(request.headers['Tag'].encode())
    request_cipher = AES.new(CONFIG.key, AES.MODE_EAX, nonce=nonce)
    raw_message    = request_cipher.decrypt(cipher_text)

    request_cipher.verify(tag)

    form = ControlForm.model_validate_json(raw_message.decode())

    try:
        logging.debug(form.type)
        raw_message = process_control_form(form).model_dump_json().encode()
    except Exception as exception: # pylint: disable=broad-except
        logging.error(exception)
        form.error  = str(exception)
        raw_message = form.model_dump_json().encode()

    response_cipher = AES.new(CONFIG.key, AES.MODE_EAX)

    cipher_text, tag = response_cipher.encrypt_and_digest(raw_message)

    cipher_b64 = b64encode(cipher_text)

    return Response(
        content=cipher_b64,
        headers={
            'Nonce': b64encode(response_cipher.nonce).decode(),
            'Tag': b64encode(tag).decode()
        }
    )


@app.post("/mpi")
async def mpi_handler(request: Request) -> Response:
    """Network message handler for processing incoming network messages. This endpoint receives encrypted network
    messages, decrypts them, processes the contained message, and returns an encrypted response. The processing
    logic is handled in the `route_network_message` function, which determines how to handle the message based on
    its type and destination. If the message is destined for the current agent, it will be processed directly;
    otherwise, it will be forwarded to the appropriate peer. The response is typically an acknowledgement of
    receipt or an error message if processing fails. This endpoint ensures secure communication between agents
    by encrypting all messages in transit.

    Args:
        request: The incoming HTTP request containing the encrypted network message.

    Returns:
        An HTTP response containing the encrypted network message response, typically an acknowledgement.
    """
    cipher_b64     = await request.body()
    cipher_text    = b64decode(cipher_b64)
    nonce          = b64decode(request.headers['Nonce'].encode())
    tag            = b64decode(request.headers['Tag'].encode())
    request_cipher = AES.new(CONFIG.key, AES.MODE_EAX, nonce=nonce)
    raw_message    = request_cipher.decrypt(cipher_text)

    request_cipher.verify(tag)

    message = NetworkMessage.model_validate_json(raw_message.decode())

    if isrc := message.isrc:
        touch_peer(isrc)

    if message.dest is None:
        message.dest = CONFIG.agtuuid

    raw_message = route_network_message(message).model_dump_json().encode()

    response_cipher = AES.new(CONFIG.key, AES.MODE_EAX)

    cipher_text, tag = response_cipher.encrypt_and_digest(raw_message)

    cipher_b64 = b64encode(cipher_text)

    return Response(
        content=cipher_b64,
        headers={
            'Nonce': b64encode(response_cipher.nonce).decode(),
            'Tag': b64encode(tag).decode()
        }
    )


def process_control_form(form: ControlForm) -> ControlForm:
    """Process a control form by matching its type and executing the appropriate handler.

    Routes control forms to specific handlers based on their type. Supported operations include
    peer discovery and management, file operations, process synchronization, ticketing, and
    configuration retrieval. Each case handles form type validation and execution logic.

    Args:
        form: The control form to process, containing type and form-specific data.

    Returns:
        The processed control form with response data populated or error information set.
    """
    logging.debug(form.type)
    match form.type:
        case ControlFormType.DISCOVER_PEER:
            form = DiscoverPeer(**form.model_dump())
            client = AgentClient(url=form.url)
            acknowledgement = client.send_network_message(Ping())
            form.agtuuid = acknowledgement.dest
            create_peer(agtuuid=form.agtuuid, url=form.url, ttl=form.ttl, polling=form.polling)
        case ControlFormType.CREATE_PEER:
            form = CreatePeer(**form.model_dump())
            create_peer(agtuuid=form.agtuuid, url=form.url, ttl=form.ttl, polling=form.polling)
        case ControlFormType.DELETE_PEERS:
            form = DeletePeers(**form.model_dump())
            if form.agtuuids:
                for agtuuid in form.agtuuids:
                    delete_peer(agtuuid)
            else:
                delete_peers()
        case ControlFormType.GET_PEERS:
            form = GetPeers(**form.model_dump())
            form.peers = get_peers()
        case ControlFormType.GET_ROUTES:
            form = GetRoutes(**form.model_dump())
            form.routes = get_routes()
        case ControlFormType.SYNC_PROCESS:
            form = sync_process(SyncProcess(**form.model_dump()))
        case ControlFormType.LOAD_FILE:
            form = load_file_to_form(LoadFile(**form.model_dump()))
        case ControlFormType.WRITE_FILE:
            form = write_file_from_form(WriteFile(**form.model_dump()))
        case ControlFormType.CREATE_TICKET:
            form = create_form_ticket(ControlFormTicket(**form.model_dump()))
        case ControlFormType.READ_TICKET:
            form = read_ticket(ControlFormTicket(**form.model_dump()))
        case ControlFormType.CLOSE_TICKET:
            close_ticket(ControlFormTicket(**form.model_dump()))
        case ControlFormType.GET_CONFIG:
            form = GetConfig(**form.model_dump())
            form.config = CONFIG.model_dump(exclude={'key'})
        case _:
            logging.warning('Unknown control form type encountered.')
    return form


def create_form_ticket(control_form_ticket: ControlFormTicket) -> ControlFormTicket:
    """Create a network ticket from a control form ticket and route it to the destination.

    Converts a control form ticket into a network ticket message and routes it through
    the network to the specified destination. The original control form ticket is stored
    in a local tickets collection for tracking and later retrieval.

    Args:
        control_form_ticket: The control form ticket containing the form and destination.

    Returns:
        The processed control form ticket stored in the tickets collection.
    """
    network_ticket = NetworkTicket(
        form=control_form_ticket.form,
        dest=control_form_ticket.dst,
        tckuuid=control_form_ticket.tckuuid,
        tracing=control_form_ticket.tracing,
        type=NetworkMessageType.TICKET_REQUEST,
        create_time=control_form_ticket.create_time
    )

    tickets = Collection[ControlFormTicket]('tickets')
    ticket = tickets.upsert_object(control_form_ticket)

    route_network_message(network_ticket)

    return ticket.object


def route_network_message(message_in: NetworkMessage) -> NetworkMessage:
    """Route a network message to its destination or forward it to an intermediate peer.

    Determines the appropriate handling for a network message based on whether it is
    destined for the current agent or should be forwarded to another peer. Handles
    ticket message deduplication and tracing. If the message is for this agent,
    processes it directly; otherwise, spawns a background thread to forward it.
    Always returns an acknowledgement unless processing generates a specific response.

    Args:
        message_in: The network message to route.

    Returns:
        An acknowledgement of receipt (or other response from processing).
    """
    if message_in.type in (
        NetworkMessageType.TICKET_REQUEST, NetworkMessageType.TICKET_RESPONSE):
        ticket = NetworkTicket(**message_in.model_dump())
        if trace_message := dedup_trace(ticket):
            if trace_message.dest == CONFIG.agtuuid:
                process_network_message(trace_message)
            else:
                Thread(target=forward_network_message, args=(trace_message,)).start()

    if message_in.dest == CONFIG.agtuuid:
        try:
            if message_out := process_network_message(message_in):
                return message_out
            else:
                return Acknowledgement(
                    ack_type=message_in.type,
                    src=message_in.src,
                    dest=message_in.dest
                )
        except: # pylint: disable=bare-except
            return Acknowledgement(
                ack_type=message_in.type,
                src=message_in.src,
                dest=message_in.dest,
                error=traceback.format_exc()
            )

    Thread(target=forward_network_message, args=(message_in,)).start()

    return Acknowledgement(
        src=message_in.src,
        ack_type=message_in.type,
        dest=message_in.dest
    )


def process_network_message(message: NetworkMessage) -> NetworkMessage | None:
    """Process a network message based on its type and generate an appropriate response.

    Handles different network message types including pings, advertisements, ticket
    exchanges, and message requests. For ticket requests, processes the embedded
    control form and routes the response back. For messages requests, retrieves pending
    messages for the requesting agent. Returns None for simple acknowledgement cases.

    Args:
        message: The network message to process.

    Returns:
        A network message response (e.g., MESSAGES_RESPONSE) or None for acknowledge-only cases.
    """
    logging.debug(message.type)
    match message.type:
        case NetworkMessageType.PING:
            pass
        case NetworkMessageType.ADVERTISEMENT:
            process_route_advertisement(Advertisement.model_validate(message.model_extra))
        case NetworkMessageType.TICKET_REQUEST:
            ticket = NetworkTicket(**message.model_dump())
            try:
                ticket.form = process_control_form(ticket.form)
            except Exception as exception: # pylint: disable=broad-except
                ticket.form.error = str(exception)
                logging.error('Encountered exception with ticket %s: %s', ticket.tckuuid, exception)

            ticket.src, ticket.dest = ticket.dest, ticket.src
            ticket.type = NetworkMessageType.TICKET_RESPONSE
            route_network_message(ticket)
        case NetworkMessageType.TICKET_RESPONSE:
            service_ticket(NetworkTicket(**message.model_dump()))
        case NetworkMessageType.TICKET_TRACE_RESPONSE:
            trace_ticket(TicketTraceResponse(**message.model_dump()))
        case NetworkMessageType.MESSAGES_REQUEST:
            messages = NetworkMessagesRequest(
                messages=pull_network_messages(message.isrc),
                type=NetworkMessageType.MESSAGES_RESPONSE,
                dest=message.isrc
            )
            return messages
        case _:
            logging.warning('Unknown network message type encountered')


@scheduled(every_secs=1)
def replay():
    """Replay pending network messages that have no specific destination.

    Background worker that runs on a 1-second timer. Retrieves all stored network
    messages with a null destination and routes them through the network. Each message
    is routed in a separate background thread to avoid blocking.
    """
    for message in islice(pop_network_messages(dest='$!eq:None'), 10):
        Thread(target=route_network_message, args=(message,)).start()


def poll(peer: Peer):
    """Poll a peer for pending network messages via the MESSAGES_REQUEST protocol.

    Sends a MESSAGES_REQUEST to the specified peer and processes the response.
    If messages are returned, each is routed locally in a separate background thread.
    If an error is received, logs it for debugging.

    Args:
        peer: The peer to poll for messages.
    """
    client = AgentClient(url=peer.url)

    network_message = client.send_network_message(NetworkMessagesRequest())

    match network_message.type:
        case NetworkMessageType.MESSAGES_RESPONSE:
            network_messages = NetworkMessagesResponse.model_validate(network_message.model_extra)
            for network_message in network_messages.messages:
                Thread(target=route_network_message, args=(network_message,)).start()
        case NetworkMessageType.ACKNOWLEDGEMENT:
            acknowledment = Acknowledgement.model_validate(network_message.model_extra)
            if acknowledment.error:
                logging.error(acknowledment.error)


@scheduled(every_secs=1)
def polling():
    """Poll all peers configured for polling in search of pending messages.

    Background worker that runs on a 1-second timer. Finds all peers with polling
    enabled and spawns a background thread to poll each one for pending messages.
    Responses are processed and routed locally.
    """

    for peer in Collection[Peer]('peers').find(url='$!eq:None', polling=True):
        Thread(target=poll, args=(peer.object,)).start()


def advertise(peer: Peer):
    """Send a route advertisement to a specific peer.

    Creates a route advertisement containing the current agent's routes and
    sends it to the specified peer. Used by ad_worker to periodically share
    network topology information.

    Args:
        peer: The peer to send the advertisement to.
    """
    advertisement = create_route_advertisement()
    advertisement.dest = peer.agtuuid
    route_network_message(advertisement)


@scheduled(every_secs=10)
def advertizing():
    """Background worker for route advertisement and aging.

    Runs periodically age routes and
    advertise the current agent's routes to all known peers. Helps maintain
    network topology information and clean up stale routes.
    """

    age_routes(1)
    for peer in Collection[Peer]('peers').find():
        Thread(target=advertise, args=(peer.object,)).start()
