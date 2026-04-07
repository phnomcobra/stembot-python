from base64 import b64encode, b64decode
from typing import TypeVar
import logging
import requests

from Crypto.Cipher import AES

from stembot.models.config import CONFIG
from stembot.models.control import ControlForm
from stembot.models.network import NetworkMessage

# Generic type variable bound to ControlForm
T = TypeVar('T', bound=ControlForm)


class ControlFormClient:
    def __init__(self, url):
        self.url = url

    def send_control_form(self, form: T) -> T:
        """Send a control form and receive the same typed response.

        The endpoint called will always respond with the same Pydantic model
        that the request was made from. This method preserves type information
        through the request/response cycle.

        Args:
            form: A ControlForm subclass instance (e.g., GetConfig, DiscoverPeer, etc.)

        Returns:
            The same type as the input form, populated with the response data
        """
        request_cipher = AES.new(CONFIG.key, AES.MODE_EAX)

        cipher_text, tag = request_cipher.encrypt_and_digest(form.model_dump_json().encode())

        headers = {
            'Nonce': b64encode(request_cipher.nonce).decode(),
            'Tag': b64encode(tag).decode()
        }

        response = requests.post(
            self.url,
            data=b64encode(cipher_text),
            headers=headers,
            timeout=5.0
        )

        response_cipher = AES.new(
            CONFIG.key, AES.MODE_EAX,
            nonce=b64decode(response.headers['Nonce'].encode())
        )

        plain_text = response_cipher.decrypt(b64decode(response.content))
        response_cipher.verify(b64decode(response.headers['Tag'].encode()))

        # Return the response as the same type as the request
        return type(form).model_validate_json(plain_text)


class NetworkMessageClient:
    def __init__(self, url):
        self.url = url

    def send_network_message(self, message: NetworkMessage) -> NetworkMessage:
        logging.debug('%s -> %s', message.type, message.dest)

        request_cipher = AES.new(CONFIG.key, AES.MODE_EAX)

        message.isrc = CONFIG.agtuuid

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

        response_cipher = AES.new(
            CONFIG.key, AES.MODE_EAX,
            nonce=b64decode(response.headers['Nonce'].encode())
        )

        plain_text = response_cipher.decrypt(b64decode(response.content))
        response_cipher.verify(b64decode(response.headers['Tag'].encode()))

        return NetworkMessage.model_validate_json(plain_text)
