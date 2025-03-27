#!/usr/bin/python3

import cherrypy
import traceback

from Crypto.Cipher import AES
from base64 import b64encode, b64decode

from stembot.adapter.agent import NetworkMessageClient
from stembot.audit import logging
from stembot.model.peer import create_peer, delete_peer, delete_peers, get_peers, get_routes
from stembot.types.control import ControlForm, ControlFormType, CreatePeer, DeletePeers, DiscoverPeer, GetPeers, GetRoutes, Ticket
from stembot.types.network import Ping, Route

class Control(object):
    @cherrypy.expose
    def default(self):
        cl = cherrypy.request.headers['Content-Length']
        cipher_b64 = cherrypy.request.body.read(int(cl))
        cipher_text = b64decode(cipher_b64)

        nonce = b64decode(cherrypy.request.headers['Nonce'].encode())
        tag = b64decode(cherrypy.request.headers['Tag'].encode())
        key = b64decode(cherrypy.config.get('server.secret_digest'))[:16]
        request_cipher = AES.new(key, AES.MODE_EAX, nonce=nonce)

        raw_message = request_cipher.decrypt(cipher_text)
        request_cipher.verify(tag)

        form = ControlForm.model_validate_json(raw_message.decode())

        try:
            form = process(form)
        except: # pylint: disable=bare-except
            form.error = traceback.format_exc()
            logging.exception(form.type)

        raw_message = form.model_dump_json().encode()

        response_cipher = AES.new(key, AES.MODE_EAX)

        cipher_text, tag = response_cipher.encrypt_and_digest(raw_message)

        cipher_b64 = b64encode(cipher_text)

        cherrypy.response.headers['Nonce'] = b64encode(response_cipher.nonce).decode()
        cherrypy.response.headers['Tag'] = b64encode(tag).decode()

        return cipher_b64

    default.exposed = True


def process(form: ControlForm) -> ControlForm:
    logging.info(form.type)
    match form.type:
        case ControlFormType.DISCOVER_PEER:
            form = DiscoverPeer.model_validate(form.model_extra)
            client = NetworkMessageClient(
                url=form.url,
                secret_digest=cherrypy.config.get('server.secret_digest')
            )
            acknowledgement = client.send(Ping())
            form.agtuuid = acknowledgement.dest
            create_peer(agtuuid=form.agtuuid, url=form.url, ttl=form.ttl, polling=form.polling)
        case ControlFormType.CREATE_PEER:
            form = CreatePeer.model_validate(form.model_extra)
            create_peer(agtuuid=form.agtuuid, url=form.url, ttl=form.ttl, polling=form.polling)
        case ControlFormType.DELETE_PEERS:
            form = DeletePeers.model_validate(form.model_extra)
            if form.agtuuids:
                for agtuuid in form.agtuuids:
                    delete_peer(agtuuid)
            else:
                delete_peers()
        case ControlFormType.GET_PEERS:
            form = GetPeers.model_validate(form.model_extra)
            form.agtuuids = [x.get('agtuuid') for x in get_peers()]
        case ControlFormType.GET_ROUTES:
            form = GetRoutes.model_validate(form.model_extra)
            form.routes = [Route(**x) for x in get_routes()]
        case ControlFormType.CREATE_TICKET:
            form = Ticket.model_validate(form.model_extra)




    return form
