#!/usr/bin/python3
from base64 import b64encode, b64decode
from random import random
from threading import Thread
import traceback
import logging

from fastapi import FastAPI, Request, Response
from Crypto.Cipher import AES

from stembot.executor.agent import AgentClient
from stembot.executor.file import load_file_to_form, write_file_from_form
from stembot.executor.process import sync_process
from stembot.models.config import CONFIG
from stembot.ticketing import close_ticket, dedup_trace, read_ticket, service_ticket, trace_ticket
from stembot.dao import Collection
from stembot.messaging import forward_network_message, pop_network_messages, pull_network_messages
from stembot.peering import touch_peer
from stembot.peering import process_route_advertisement
from stembot.peering import age_routes
from stembot.peering import create_route_advertisement
from stembot.peering import create_peer, delete_peer, delete_peers, get_peers, get_routes
from stembot.scheduling import register_timer
from stembot.models.control import ControlForm, ControlFormType, CreatePeer, DeletePeers, DiscoverPeer, GetConfig
from stembot.models.control import GetRoutes, ControlFormTicket, LoadFile, SyncProcess, WriteFile, GetPeers
from stembot.models.network import Acknowledgement, Advertisement, NetworkMessage, NetworkMessageType, Ping
from stembot.models.network import NetworkMessagesRequest, NetworkMessagesResponse, NetworkTicket, TicketTraceResponse
from stembot.models.routing import Peer


async def control_handler(request: Request) -> Response:
    cipher_b64  = await request.body()
    cipher_text = b64decode(cipher_b64)

    nonce          = b64decode(request.headers['Nonce'].encode())
    tag            = b64decode(request.headers['Tag'].encode())
    request_cipher = AES.new(CONFIG.key, AES.MODE_EAX, nonce=nonce)

    raw_message = request_cipher.decrypt(cipher_text)
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


async def mpi_handler(request: Request) -> Response:
    cipher_b64  = await request.body()
    cipher_text = b64decode(cipher_b64)

    nonce          = b64decode(request.headers['Nonce'].encode())
    tag            = b64decode(request.headers['Tag'].encode())
    request_cipher = AES.new(CONFIG.key, AES.MODE_EAX, nonce=nonce)

    raw_message = request_cipher.decrypt(cipher_text)
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


def setup_routes(app: FastAPI):
    """Setup FastAPI routes for the application."""
    app.add_route("/control", control_handler, methods=["POST"])
    app.add_route("/mpi", mpi_handler, methods=["POST"])


def create_form_ticket(control_form_ticket: ControlFormTicket):
    network_ticket = NetworkTicket(
        form=control_form_ticket.form,
        dest=control_form_ticket.dst,
        tckuuid=control_form_ticket.tckuuid,
        tracing=control_form_ticket.tracing,
        type=NetworkMessageType.TICKET_REQUEST,
        create_time=control_form_ticket.create_time
    )

    tickets = Collection[ControlFormTicket]('tickets', in_memory=True)
    ticket = tickets.upsert_object(control_form_ticket)

    route_network_message(network_ticket)

    return ticket.object


def route_network_message(message_in: NetworkMessage) -> NetworkMessage:
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


def replay_worker():
    register_timer(
        name='replay_worker',
        target=replay_worker,
        timeout=1.0
    ).start()

    for message in pop_network_messages(dest='$!eq:None'):
        Thread(target=route_network_message, args=(message,)).start()


def poll_peer(peer: Peer):
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


def poll_worker():
    register_timer(
        name='poll_worker',
        target=poll_worker,
        timeout=1.0
    ).start()

    for peer in Collection[Peer]('peers', in_memory=True).find(url='$!eq:None', polling=True):
        Thread(target=poll_peer, args=(peer.object,)).start()


def advertise(peer):
    advertisement = create_route_advertisement()
    advertisement.dest = peer.agtuuid
    route_network_message(advertisement)


def ad_worker():
    rt = int(random() * 10.0 + 5.0)

    register_timer(
        name='ad_worker',
        target=ad_worker,
        timeout=rt
    ).start()

    age_routes(rt)

    for peer in Collection[Peer]('peers', in_memory=True).find():
        Thread(target=advertise, args=(peer.object,)).start()


Thread(target=ad_worker).start()
Thread(target=poll_worker).start()
Thread(target=replay_worker).start()
