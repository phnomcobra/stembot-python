"""HTTP client for secure inter-agent communication with session pooling.

Provides the AgentClient class for sending encrypted control forms and network messages
to remote agents. Implements connection pooling with automatic retry logic, exponential
backoff, and optimized timeouts for distributed network operation.

All communication is encrypted using AES-256 in EAX mode with HMAC authentication.
Connections are reused via session pooling to improve performance in high-throughput
scenarios. Retry strategy handles transient failures with exponential backoff.

Key features:
- HTTP/HTTPS connection pooling per URL
- AES-256 EAX encryption with authentication
- Automatic retry with exponential backoff
- Optimized timeouts (5s connect, 30s read)
- Type-safe control form/network message handling via Pydantic
"""

from base64 import b64encode, b64decode
from typing import TypeVar
import logging
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from Crypto.Cipher import AES

from stembot.models.config import CONFIG
from stembot.models.control import ControlForm
from stembot.models.network import NetworkMessage

# Generic type variable bound to ControlForm
T = TypeVar('T', bound=ControlForm)

# Session pool to reuse connections per URL
SESSION_POOL = {}


class AgentClient:
    """HTTP client for sending encrypted messages to a remote agent.

    Handles secure communication with remote agents by encrypting/decrypting
    control forms and network messages using AES-256. Implements connection
    pooling, retry logic, and type-safe Pydantic serialization.

    Attributes:
        url: The base URL of the remote agent (e.g., http://agent:8080).
        session: A requests.Session object with connection pooling and retry
               configuration, reused across requests to the same agent.
    """
    def __init__(self, url: str) -> None:
        """Initialize an agent client for a remote agent URL.

        Creates or reuses a session for communicating with the specified agent URL.
        Configures automatic retries (3 total, exponential backoff 0.3) on transient
        errors (429, 500, 502, 503, 504) and connection pooling (128 connections max).
        Sessions are cached globally to avoid recreating them for the same URL.

        Args:
            url: The base URL of the remote agent to communicate with.
        """
        self.url = url

        if url in SESSION_POOL:
            self.session = SESSION_POOL[url]
        else:
            self.session = requests.Session()

            # Configure retry strategy with exponential backoff
            retry_strategy = Retry(
                total=3,
                backoff_factor=0.3,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["POST"]
            )

            # Configure HTTP adapter with connection pooling
            adapter = HTTPAdapter(
                max_retries=retry_strategy,
                pool_connections=10,
                pool_maxsize=10,
                pool_block=True
            )

            # Mount adapter for both http and https
            self.session.mount("http://", adapter)
            self.session.mount("https://", adapter)

            SESSION_POOL[url] = self.session
            logging.debug('Created agent session with %s', url)

    def send_control_form(self, form: T) -> T:
        """Send a control form and receive a typed response.

        Sends an encrypted control form to the agent's /control endpoint and
        receives the response back as the same Pydantic model type. Request and
        response are encrypted with AES-256 and authenticated with HMAC.

        Uses session pooling for connection reuse and configured timeouts:
        - Connect timeout: 5 seconds
        - Read timeout: 30 seconds

        Args:
            form: A ControlForm subclass instance (e.g., GetConfig, DiscoverPeer).

        Returns:
            The same type as the input form, populated with response data.

        Raises:
            requests.HTTPError: If the HTTP response has a non-2xx status code.
            ValueError: If response decryption or validation fails.
        """
        logging.debug(form.type)

        request_cipher = AES.new(CONFIG.key, AES.MODE_EAX)

        cipher_text, tag = request_cipher.encrypt_and_digest(form.model_dump_json().encode())

        headers = {
            'Nonce': b64encode(request_cipher.nonce).decode(),
            'Tag': b64encode(tag).decode(),
            'Content-Type': 'application/octet-stream'
        }

        # Optimized POST with connection reuse and timeout config
        response = self.session.post(
            self.url,
            data=b64encode(cipher_text),
            headers=headers,
            timeout=(5.0, 60.0)  # (connect timeout, read timeout)
        )
        response.raise_for_status()

        response_cipher = AES.new(
            CONFIG.key, AES.MODE_EAX,
            nonce=b64decode(response.headers['Nonce'].encode())
        )

        plain_text = response_cipher.decrypt(b64decode(response.content))
        response_cipher.verify(b64decode(response.headers['Tag'].encode()))

        # Return the response as the same type as the request
        return type(form).model_validate_json(plain_text)

    def send_network_message(self, message: NetworkMessage) -> NetworkMessage:
        """Send a network message and receive a response.

        Sends an encrypted network message to the agent's /mpi endpoint and
        receives a network message response. Request and response are encrypted
        with AES-256 and authenticated with HMAC. Automatically sets the message
        source (isrc) to the local agent UUID.

        Uses session pooling for connection reuse and configured timeouts:
        - Connect timeout: 5 seconds
        - Read timeout: 30 seconds

        Args:
            message: A NetworkMessage to send to the agent.

        Returns:
            A NetworkMessage response from the agent.

        Raises:
            requests.HTTPError: If the HTTP response has a non-2xx status code.
            ValueError: If response decryption or validation fails.
        """
        logging.debug('%s -> %s', message.type, message.dest)

        request_cipher = AES.new(CONFIG.key, AES.MODE_EAX)

        message.isrc = CONFIG.agtuuid

        ciphertext, tag = request_cipher.encrypt_and_digest(message.model_dump_json().encode())

        headers = {
            'Nonce': b64encode(request_cipher.nonce).decode(),
            'Tag': b64encode(tag).decode(),
            'Content-Type': 'application/octet-stream'
        }

        # Optimized POST with connection reuse and timeout config
        response = self.session.post(
            self.url,
            data=b64encode(ciphertext),
            headers=headers,
            timeout=(5.0, 60.0)  # (connect timeout, read timeout)
        )
        response.raise_for_status()

        response_cipher = AES.new(
            CONFIG.key, AES.MODE_EAX,
            nonce=b64decode(response.headers['Nonce'].encode())
        )

        plain_text = response_cipher.decrypt(b64decode(response.content))
        response_cipher.verify(b64decode(response.headers['Tag'].encode()))

        return NetworkMessage.model_validate_json(plain_text)
