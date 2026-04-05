from base64 import b64encode, b64decode
import logging
import requests

from Crypto.Cipher import AES

from stembot.models.config import CONFIG
from stembot.models.control import ControlForm
from stembot.models.network import NetworkMessage


class ControlFormClient:
    def __init__(self, url):
        self.url = url

    def send_control_form(self, send: ControlForm) -> ControlForm:
        logging.debug('%s -> %s', send.type, self.url)
        request_cipher = AES.new(CONFIG.key, AES.MODE_EAX)

        ciphertext, tag = request_cipher.encrypt_and_digest(send.model_dump_json().encode())

        headers = {
            'Nonce': b64encode(request_cipher.nonce).decode(),
            'Tag': b64encode(tag).decode()
        }

        response = requests.post(
            self.url,
            data=b64encode(ciphertext),
            headers=headers,
            timeout=5.0
        )

        response_cipher = AES.new(
            CONFIG.key, AES.MODE_EAX,
            nonce=b64decode(response.headers['Nonce'].encode())
        )

        plain_text = response_cipher.decrypt(b64decode(response.content))
        response_cipher.verify(b64decode(response.headers['Tag'].encode()))
        recv = ControlForm.model_validate_json(plain_text)
        logging.debug('%s <- %s', recv.type, self.url)
        return recv


class NetworkMessageClient:
    def __init__(self, url):
        self.url = url

    def send_network_message(self, send: NetworkMessage) -> NetworkMessage:
        logging.debug('%s -> %s', send.type, send.dest)

        request_cipher = AES.new(CONFIG.key, AES.MODE_EAX)

        send.isrc = CONFIG.agtuuid

        ciphertext, tag = request_cipher.encrypt_and_digest(send.model_dump_json().encode())

        headers = {
            'Nonce': b64encode(request_cipher.nonce).decode(),
            'Tag': b64encode(tag).decode()
        }

        response = requests.post(
            self.url,
            data=b64encode(ciphertext),
            headers=headers,
            timeout=5.0
        )

        response_cipher = AES.new(
            CONFIG.key, AES.MODE_EAX,
            nonce=b64decode(response.headers['Nonce'].encode())
        )

        plain_text = response_cipher.decrypt(b64decode(response.content))
        response_cipher.verify(b64decode(response.headers['Tag'].encode()))

        recv = NetworkMessage.model_validate_json(plain_text)
        logging.debug('%s <- %s', recv.type, recv.src)
        return recv
