from base64 import b64encode, b64decode
import logging
import requests

from Crypto.Cipher import AES

from stembot.dao import kvstore
from stembot.models.control import ControlForm
from stembot.models.network import NetworkMessage

KEY     = b64decode(kvstore.get('secret_digest'))[:16]
AGTUUID = kvstore.get('agtuuid')

class ControlFormClient:
    def __init__(self, url):
        self.url = url

    def send_control_form(self, form: ControlForm) -> ControlForm:
        logging.debug('%s >> %s', form.type, self.url)
        request_cipher = AES.new(KEY, AES.MODE_EAX)

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
            KEY, AES.MODE_EAX,
            nonce=b64decode(response.headers['Nonce'].encode())
        )

        plain_text = response_cipher.decrypt(b64decode(response.content))
        response_cipher.verify(b64decode(response.headers['Tag'].encode()))
        frm = ControlForm.model_validate_json(plain_text)
        logging.debug('%s << %s', frm.type, self.url)
        return frm


class NetworkMessageClient:
    def __init__(self, url):
        self.url = url

    def send_network_message(self, message: NetworkMessage) -> NetworkMessage:
        logging.debug('%s >> %s >> %s', message.src, message.type, message.dest)

        request_cipher = AES.new(KEY, AES.MODE_EAX)

        message.isrc = AGTUUID

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
            KEY, AES.MODE_EAX,
            nonce=b64decode(response.headers['Nonce'].encode())
        )

        plain_text = response_cipher.decrypt(b64decode(response.content))
        response_cipher.verify(b64decode(response.headers['Tag'].encode()))

        msg = NetworkMessage.model_validate_json(plain_text)
        logging.debug('%s << %s << %s', msg.dest, msg.type, msg.src)
        return msg
