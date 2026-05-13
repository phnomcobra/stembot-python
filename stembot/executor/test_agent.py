"""Protocol compatibility tests for AgentClient.

Tests the send_control_form and send_network_message methods, verifying that
the request Nonce/Tag headers are properly formatted strings and that the
encrypted request body contains the expected canonical JSON payload.

These tests are canonical and serve as the protocol specification for
stembot-rust: matching behavior is required for cross-language compatibility.

Protocol summary:
- All messages are AES-256 EAX encrypted with a 32-byte shared key.
- AES-EAX produces a 16-byte nonce and a 16-byte MAC tag per message.
- The HTTP request body is:  raw binary ciphertext (application/binary)
- The HTTP request headers are:
    Nonce: hex(nonce)           [plain string, decodes to 16 bytes]
    Tag:   hex(mac_tag)         [plain string, decodes to 16 bytes]
- Decrypting body using key + Nonce + verifying Tag yields plaintext JSON.
- send_network_message sets message.isrc = CONFIG.agtuuid before encryption.

Test fixtures:
    TEST_KEY     = SHA256("stembot-test-key")   [32-byte AES-256 key]
    TEST_AGTUUID = "test-agent-id-1"
"""
import hashlib
import json
import unittest
from unittest.mock import MagicMock, patch

from Crypto.Cipher import AES

from stembot.executor.agent import SESSION_POOL, AgentClient
from stembot.models.config import CONFIG
from stembot.models.control import GetConfig
from stembot.models.network import NetworkMessage, Ping

# ---------------------------------------------------------------------------
# Fixed test fixtures — must match the values used in stembot-rust tests
# ---------------------------------------------------------------------------

TEST_KEY     = hashlib.sha256(b'stembot-test-key').digest()  # 32-byte AES-256 key
TEST_AGTUUID = "test-agent-id-1"

TEST_CTRL_URL = "http://test.local:8080/control"
TEST_MPI_URL  = "http://test.local:8080/mpi"

# Canonical JSON payloads (expected wire format after decryption)
EXPECTED_GET_CONFIG_JSON = (
    '{"type":"get_config","error":null,"objuuid":null,"coluuid":null,"config":null}'
)
EXPECTED_PING_JSON = (
    '{"type":"ping","dest":null,"src":"test-agent-id-1","isrc":"test-agent-id-1",'
    '"timestamp":1000.0,"objuuid":null,"coluuid":null}'
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_encrypted_response(key: bytes, plaintext: bytes) -> MagicMock:
    """Build a mock HTTP response whose body is raw binary AES-EAX ciphertext.

    Mirrors the response structure produced by the stembot server endpoints
    (/control and /mpi): raw binary body, hex Nonce and Tag headers.
    """
    cipher = AES.new(key, AES.MODE_EAX)
    ct, tag = cipher.encrypt_and_digest(plaintext)
    mock_resp = MagicMock()
    mock_resp.content = ct
    mock_resp.headers = {
        'Nonce': cipher.nonce.hex(),
        'Tag':   tag.hex(),
    }
    return mock_resp


def _decrypt_request(key: bytes, headers: dict, body: bytes) -> bytes:
    """Decrypt a raw binary request body using the hex Nonce/Tag headers and key.

    Raises ValueError if the MAC tag does not verify.
    """
    nonce      = bytes.fromhex(headers['Nonce'])
    tag        = bytes.fromhex(headers['Tag'])
    ciphertext = body
    cipher     = AES.new(key, AES.MODE_EAX, nonce=nonce)
    plaintext  = cipher.decrypt(ciphertext)
    cipher.verify(tag)
    return plaintext


# ---------------------------------------------------------------------------
# send_control_form tests
# ---------------------------------------------------------------------------

class TestSendControlForm(unittest.TestCase):
    """Verify the protocol structure of AgentClient.send_control_form.

    Covers:
    - Nonce/Tag headers are plain strings
    - Nonce/Tag each decode to exactly 16 bytes
    - Request body decrypts (with Nonce/Tag) to the canonical GetConfig JSON
    - MAC verification passes (HMAC integrity)
    - Return value is a correctly typed GetConfig instance
    """

    def setUp(self):
        self._key_patch     = patch.object(CONFIG, 'key',     TEST_KEY)
        self._agtuuid_patch = patch.object(CONFIG, 'agtuuid', TEST_AGTUUID)
        self._key_patch.start()
        self._agtuuid_patch.start()
        SESSION_POOL.pop(TEST_CTRL_URL, None)
        self.client   = AgentClient(url=TEST_CTRL_URL)
        self.mock_resp = _make_encrypted_response(
            TEST_KEY,
            EXPECTED_GET_CONFIG_JSON.encode(),
        )

    def tearDown(self):
        self._key_patch.stop()
        self._agtuuid_patch.stop()
        SESSION_POOL.pop(TEST_CTRL_URL, None)

    def test_nonce_header_is_string(self):
        """Nonce request header must be a plain string (not bytes)."""
        with patch.object(self.client.session, 'post') as mock_post:
            mock_post.return_value = self.mock_resp
            self.client.send_control_form(GetConfig())
            headers = mock_post.call_args.kwargs['headers']
            self.assertIsInstance(headers['Nonce'], str)

    def test_tag_header_is_string(self):
        """Tag request header must be a plain string (not bytes)."""
        with patch.object(self.client.session, 'post') as mock_post:
            mock_post.return_value = self.mock_resp
            self.client.send_control_form(GetConfig())
            headers = mock_post.call_args.kwargs['headers']
            self.assertIsInstance(headers['Tag'], str)

    def test_nonce_header_decodes_to_16_bytes(self):
        """Nonce header must hex-decode to exactly 16 bytes (AES-EAX nonce size)."""
        with patch.object(self.client.session, 'post') as mock_post:
            mock_post.return_value = self.mock_resp
            self.client.send_control_form(GetConfig())
            headers = mock_post.call_args.kwargs['headers']
            self.assertEqual(len(bytes.fromhex(headers['Nonce'])), 16)

    def test_tag_header_decodes_to_16_bytes(self):
        """Tag header must hex-decode to exactly 16 bytes (AES-EAX MAC tag size)."""
        with patch.object(self.client.session, 'post') as mock_post:
            mock_post.return_value = self.mock_resp
            self.client.send_control_form(GetConfig())
            headers = mock_post.call_args.kwargs['headers']
            self.assertEqual(len(bytes.fromhex(headers['Tag'])), 16)

    def test_body_decrypts_to_get_config_json(self):
        """Request body must decrypt via Nonce/Tag to the canonical GetConfig JSON."""
        with patch.object(self.client.session, 'post') as mock_post:
            mock_post.return_value = self.mock_resp
            self.client.send_control_form(GetConfig())
            headers  = mock_post.call_args.kwargs['headers']
            body     = mock_post.call_args.kwargs['data']
            plaintext = _decrypt_request(TEST_KEY, headers, body)
            self.assertEqual(json.loads(plaintext.decode()), json.loads(EXPECTED_GET_CONFIG_JSON))

    def test_body_mac_verifies(self):
        """Decryption with the Nonce header must pass the AES-EAX MAC check (Tag header)."""
        with patch.object(self.client.session, 'post') as mock_post:
            mock_post.return_value = self.mock_resp
            self.client.send_control_form(GetConfig())
            headers = mock_post.call_args.kwargs['headers']
            body    = mock_post.call_args.kwargs['data']
            # _decrypt_request raises ValueError on MAC failure; no exception = pass
            _decrypt_request(TEST_KEY, headers, body)

    def test_response_is_get_config_instance(self):
        """Return value must be a GetConfig instance."""
        with patch.object(self.client.session, 'post') as mock_post:
            mock_post.return_value = self.mock_resp
            result = self.client.send_control_form(GetConfig())
            self.assertIsInstance(result, GetConfig)

    def test_response_matches_decrypted_content(self):
        """Return value must equal the form parsed from the decrypted response body."""
        with patch.object(self.client.session, 'post') as mock_post:
            mock_post.return_value = self.mock_resp
            result = self.client.send_control_form(GetConfig())
            self.assertEqual(result, GetConfig())


# ---------------------------------------------------------------------------
# send_network_message tests
# ---------------------------------------------------------------------------

class TestSendNetworkMessage(unittest.TestCase):
    """Verify the protocol structure of AgentClient.send_network_message.

    Covers:
    - Nonce/Tag headers are plain strings
    - Nonce/Tag each decode to exactly 16 bytes
    - send_network_message sets message.isrc = CONFIG.agtuuid before encryption
    - Request body decrypts to the canonical Ping JSON (including isrc)
    - MAC verification passes
    - Return value is a NetworkMessage instance
    """

    def setUp(self):
        self._key_patch     = patch.object(CONFIG, 'key',     TEST_KEY)
        self._agtuuid_patch = patch.object(CONFIG, 'agtuuid', TEST_AGTUUID)
        self._key_patch.start()
        self._agtuuid_patch.start()
        SESSION_POOL.pop(TEST_MPI_URL, None)
        self.client   = AgentClient(url=TEST_MPI_URL)
        self.mock_resp = _make_encrypted_response(
            TEST_KEY,
            EXPECTED_PING_JSON.encode(),
        )

    def tearDown(self):
        self._key_patch.stop()
        self._agtuuid_patch.stop()
        SESSION_POOL.pop(TEST_MPI_URL, None)

    def test_nonce_header_is_string(self):
        """Nonce request header must be a plain string (not bytes)."""
        with patch.object(self.client.session, 'post') as mock_post:
            mock_post.return_value = self.mock_resp
            self.client.send_network_message(Ping(src=TEST_AGTUUID, timestamp=1000.0))
            headers = mock_post.call_args.kwargs['headers']
            self.assertIsInstance(headers['Nonce'], str)

    def test_tag_header_is_string(self):
        """Tag request header must be a plain string (not bytes)."""
        with patch.object(self.client.session, 'post') as mock_post:
            mock_post.return_value = self.mock_resp
            self.client.send_network_message(Ping(src=TEST_AGTUUID, timestamp=1000.0))
            headers = mock_post.call_args.kwargs['headers']
            self.assertIsInstance(headers['Tag'], str)

    def test_nonce_header_decodes_to_16_bytes(self):
        """Nonce header must hex-decode to exactly 16 bytes (AES-EAX nonce size)."""
        with patch.object(self.client.session, 'post') as mock_post:
            mock_post.return_value = self.mock_resp
            self.client.send_network_message(Ping(src=TEST_AGTUUID, timestamp=1000.0))
            headers = mock_post.call_args.kwargs['headers']
            self.assertEqual(len(bytes.fromhex(headers['Nonce'])), 16)

    def test_tag_header_decodes_to_16_bytes(self):
        """Tag header must hex-decode to exactly 16 bytes (AES-EAX MAC tag size)."""
        with patch.object(self.client.session, 'post') as mock_post:
            mock_post.return_value = self.mock_resp
            self.client.send_network_message(Ping(src=TEST_AGTUUID, timestamp=1000.0))
            headers = mock_post.call_args.kwargs['headers']
            self.assertEqual(len(bytes.fromhex(headers['Tag'])), 16)

    def test_body_decrypts_to_ping_json_with_isrc(self):
        """Request body must decrypt to Ping JSON with isrc = CONFIG.agtuuid.

        send_network_message sets message.isrc = CONFIG.agtuuid before encryption,
        so the decrypted body must contain \"isrc\":\"test-agent-id-1\".
        """
        with patch.object(self.client.session, 'post') as mock_post:
            mock_post.return_value = self.mock_resp
            self.client.send_network_message(Ping(src=TEST_AGTUUID, timestamp=1000.0))
            headers   = mock_post.call_args.kwargs['headers']
            body      = mock_post.call_args.kwargs['data']
            plaintext = _decrypt_request(TEST_KEY, headers, body)
            self.assertEqual(json.loads(plaintext.decode()), json.loads(EXPECTED_PING_JSON))

    def test_body_mac_verifies(self):
        """Decryption with the Nonce header must pass the AES-EAX MAC check (Tag header)."""
        with patch.object(self.client.session, 'post') as mock_post:
            mock_post.return_value = self.mock_resp
            self.client.send_network_message(Ping(src=TEST_AGTUUID, timestamp=1000.0))
            headers = mock_post.call_args.kwargs['headers']
            body    = mock_post.call_args.kwargs['data']
            # _decrypt_request raises ValueError on MAC failure; no exception = pass
            _decrypt_request(TEST_KEY, headers, body)

    def test_response_is_network_message_instance(self):
        """Return value must be a NetworkMessage instance."""
        with patch.object(self.client.session, 'post') as mock_post:
            mock_post.return_value = self.mock_resp
            result = self.client.send_network_message(Ping(src=TEST_AGTUUID, timestamp=1000.0))
            self.assertIsInstance(result, NetworkMessage)


if __name__ == '__main__':
    unittest.main()
