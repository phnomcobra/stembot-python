#!/usr/bin/python3
import requests

from Crypto.Cipher import AES
from base64 import b64encode, b64decode

from stembot.audit import logging
import stembot.model.kvstore as kvstore
from stembot.types.control import ControlForm
from stembot.types.network import NetworkMessage

class ControlFormClient:
    def __init__(self, url, secret_digest):
        self.url = url
        self.key = b64decode(secret_digest)[:16]

    def send(self, form: ControlForm) -> ControlForm:
        request_cipher = AES.new(self.key, AES.MODE_EAX)

        ciphertext, tag = request_cipher.encrypt_and_digest(form.model_dump_json().encode())

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
            self.key,
            AES.MODE_EAX,
            nonce=b64decode(response.headers['Nonce'].encode())
        )

        plain_text = response_cipher.decrypt(b64decode(response.content))
        response_cipher.verify(b64decode(response.headers['Tag'].encode()))

        return ControlForm.model_validate_json(plain_text)


class NetworkMessageClient:
    def __init__(self, url, secret_digest):
        self.url = url
        self.key = b64decode(secret_digest)[:16]

    def send(self, message: NetworkMessage) -> NetworkMessage:
        request_cipher = AES.new(self.key, AES.MODE_EAX)

        message.isrc = kvstore.get('agtuuid')

        logging.debug(message)

        ciphertext, tag = request_cipher.encrypt_and_digest(message.model_dump_json().encode())

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

        logging.debug(response.status_code)
        logging.debug(response.headers)
        logging.debug(response.content)

        response_cipher = AES.new(
            self.key,
            AES.MODE_EAX,
            nonce=b64decode(response.headers['Nonce'].encode())
        )

        plain_text = response_cipher.decrypt(b64decode(response.content))
        response_cipher.verify(b64decode(response.headers['Tag'].encode()))

        return NetworkMessage.model_validate_json(plain_text)
