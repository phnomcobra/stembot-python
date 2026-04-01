#!/usr/bin/python3
from base64 import b64encode, b64decode
import logging
import requests

from Crypto.Cipher import AES

from stembot.dao import kvstore
from stembot.models.control import ControlForm
from stembot.models.network import NetworkMessage

class ControlFormClient:
    def __init__(self, url, secret_digest):
        self.url = url
        self.key = b64decode(secret_digest)[:16]

    def send_control_form(self, form: ControlForm) -> ControlForm:
        try:
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
        except:
            logging.error(form.type)
            logging.exception('Request at %s failed!', self.url)
            raise

        try:
            response_cipher = AES.new(
                self.key,
                AES.MODE_EAX,
                nonce=b64decode(response.headers['Nonce'].encode())
            )
        except:
            logging.error(form.type)
            logging.exception('Failed to initialize response cipher!')
            logging.debug('%s\n%s', response.headers, response.content)
            raise

        try:
            plain_text = response_cipher.decrypt(b64decode(response.content))
            response_cipher.verify(b64decode(response.headers['Tag'].encode()))
        except:
            logging.error(form.type)
            logging.exception('Failed to decode control form!')
            logging.debug('%s\n%s', response.headers, response.content)
            raise

        try:
            form = ControlForm.model_validate_json(plain_text)
            logging.debug(form.type)
            return form
        except:
            logging.error(form.type)
            logging.exception('Control form validation failed!')
            raise


class NetworkMessageClient:
    def __init__(self, url, secret_digest):
        self.url = url
        self.key = b64decode(secret_digest)[:16]

    def send_network_message(self, message: NetworkMessage) -> NetworkMessage:
        try:
            request_cipher = AES.new(self.key, AES.MODE_EAX)

            message.isrc = kvstore.get('agtuuid')

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
        except:
            logging.error('%s -> %s -> %s', message.src, message.type, message.dest)
            logging.exception('Request at %s failed!', self.url)
            raise

        try:
            response_cipher = AES.new(
                self.key,
                AES.MODE_EAX,
                nonce=b64decode(response.headers['Nonce'].encode())
            )
        except:
            logging.error('%s -> %s -> %s', message.src, message.type, message.dest)
            logging.exception('Failed to initialize response cipher!')
            logging.debug('%s\n%s', response.headers, response.content)
            raise

        try:
            plain_text = response_cipher.decrypt(b64decode(response.content))
            response_cipher.verify(b64decode(response.headers['Tag'].encode()))
        except:
            logging.error('%s -> %s -> %s', message.src, message.type, message.dest)
            logging.exception('Failed to decode network message!')
            logging.debug('%s\n%s', response.headers, response.content)
            raise

        try:
            message =  NetworkMessage.model_validate_json(plain_text)
            logging.debug('%s -> %s -> %s', message.src, message.type, message.dest)
            return message
        except:
            logging.error('%s -> %s -> %s', message.src, message.type, message.dest)
            logging.exception('Network message validation failed!')
            raise
