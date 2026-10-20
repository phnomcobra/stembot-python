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

from stembot.executor.agent import SESSION_POOL, AgentClient, resolve_agent_key
from stembot.models.config import CONFIG
from stembot.models.control import GetConfig
from stembot.models.network import NetworkMessage, Ping

# ---------------------------------------------------------------------------
# Fixed test fixtures — must match the values used in stembot-rust tests
# ---------------------------------------------------------------------------

TEST_KEY      = hashlib.sha256(b'stembot-test-key').digest()  # 32-byte AES-256 key
TEST_KEYUUID  = "test-key-uuid-1"
TEST_AGTUUID  = "test-agent-id-1"
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
        self._resolve_patch = patch(
            'stembot.executor.agent.resolve_agent_key',
            return_value=(TEST_KEYUUID, TEST_KEY),
        )
        self._agtuuid_patch = patch.object(CONFIG, 'agtuuid', TEST_AGTUUID)
        self._resolve_patch.start()
        self._agtuuid_patch.start()
        SESSION_POOL.pop(TEST_CTRL_URL, None)
        self.client = AgentClient(url=TEST_CTRL_URL)
        self.mock_resp = _make_encrypted_response(
            TEST_KEY,
            EXPECTED_GET_CONFIG_JSON.encode(),
        )

    def tearDown(self):
        self._resolve_patch.stop()
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
        self._resolve_patch = patch(
            'stembot.executor.agent.resolve_agent_key',
            return_value=(TEST_KEYUUID, TEST_KEY),
        )
        self._agtuuid_patch = patch.object(CONFIG, 'agtuuid', TEST_AGTUUID)
        self._resolve_patch.start()
        self._agtuuid_patch.start()
        SESSION_POOL.pop(TEST_MPI_URL, None)
        self.client = AgentClient(url=TEST_MPI_URL)
        self.mock_resp = _make_encrypted_response(
            TEST_KEY,
            EXPECTED_PING_JSON.encode(),
        )

    def tearDown(self):
        self._resolve_patch.stop()
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


# ---------------------------------------------------------------------------
# resolve_agent_key tests
# ---------------------------------------------------------------------------

class TestResolveAgentKey(unittest.TestCase):
    """Verify resolve_agent_key's peer/key resolution logic.

    Covers:
    - Matching a peer by hostname:port and resolving its agent UUID
    - The $contains filter passed to peers.find includes/omits the port
    - Falling back to CONFIG.agtuuid for localhost/127.0.0.1/::1/0.0.0.0,
      overriding any matched peer
    - Returning the (keyuuid, key) tuple from KeyManager.resolve_key_objuuid/decrypt_key
    - Raising ValueError when no key UUID can be resolved
    """

    def _make_mocks(self, matched_peers=None, resolved_keyuuid=TEST_KEYUUID, decrypted_key=TEST_KEY):
        """Build mock Collection/KeyManager classes for patching resolve_agent_key's dependencies.

        Returns a tuple of (mock_collection_class, mock_peers_instance, mock_km_class, mock_km_instance).
        """
        mock_peers_instance = MagicMock()
        mock_peers_instance.find.return_value = matched_peers or []

        mock_collection_class = MagicMock()
        mock_collection_class.__getitem__.return_value = MagicMock(return_value=mock_peers_instance)

        mock_km_instance = MagicMock()
        mock_km_instance.resolve_key_objuuid.return_value = resolved_keyuuid
        mock_km_instance.decrypt_key.return_value = decrypted_key
        mock_km_class = MagicMock(return_value=mock_km_instance)

        return mock_collection_class, mock_peers_instance, mock_km_class, mock_km_instance

    def test_resolves_agtuuid_from_matched_peer(self):
        """Resolves the agent UUID from a peer matched by hostname:port."""
        matched = MagicMock()
        matched.object.agtuuid = 'peer-agent-uuid'
        mock_collection_class, _, mock_km_class, mock_km = self._make_mocks(matched_peers=[matched])

        with patch('stembot.executor.agent.Collection', mock_collection_class), \
             patch('stembot.executor.agent.KeyManager', mock_km_class):
            resolve_agent_key('http://remote.local:8080')

        mock_km.resolve_key_objuuid.assert_called_once_with('peer-agent-uuid')

    def test_find_filter_includes_hostname_and_port(self):
        """peers.find is queried with a $contains filter of hostname:port."""
        mock_collection_class, mock_peers, mock_km_class, _ = self._make_mocks()

        with patch('stembot.executor.agent.Collection', mock_collection_class), \
             patch('stembot.executor.agent.KeyManager', mock_km_class):
            resolve_agent_key('http://remote.local:8080')

        mock_peers.find.assert_called_once_with(url='$contains:remote.local:8080')

    def test_find_filter_omits_port_when_absent(self):
        """peers.find's $contains filter omits the port suffix when the URL has no port."""
        mock_collection_class, mock_peers, mock_km_class, _ = self._make_mocks()

        with patch('stembot.executor.agent.Collection', mock_collection_class), \
             patch('stembot.executor.agent.KeyManager', mock_km_class):
            resolve_agent_key('http://remote.local')

        mock_peers.find.assert_called_once_with(url='$contains:remote.local')

    def test_falls_back_to_local_agtuuid_for_localhost(self):
        """Hostname 'localhost' resolves to CONFIG.agtuuid, overriding any matched peer."""
        matched = MagicMock()
        matched.object.agtuuid = 'peer-agent-uuid'
        mock_collection_class, _, mock_km_class, mock_km = self._make_mocks(matched_peers=[matched])

        with patch('stembot.executor.agent.Collection', mock_collection_class), \
             patch('stembot.executor.agent.KeyManager', mock_km_class), \
             patch.object(CONFIG, 'agtuuid', TEST_AGTUUID):
            resolve_agent_key('http://localhost:8080')

        mock_km.resolve_key_objuuid.assert_called_once_with(TEST_AGTUUID)

    def test_falls_back_to_local_agtuuid_for_127_0_0_1(self):
        """Hostname '127.0.0.1' resolves to CONFIG.agtuuid."""
        mock_collection_class, _, mock_km_class, mock_km = self._make_mocks()

        with patch('stembot.executor.agent.Collection', mock_collection_class), \
             patch('stembot.executor.agent.KeyManager', mock_km_class), \
             patch.object(CONFIG, 'agtuuid', TEST_AGTUUID):
            resolve_agent_key('http://127.0.0.1:8080')

        mock_km.resolve_key_objuuid.assert_called_once_with(TEST_AGTUUID)

    def test_falls_back_to_local_agtuuid_for_ipv6_loopback(self):
        """Hostname '::1' resolves to CONFIG.agtuuid."""
        mock_collection_class, _, mock_km_class, mock_km = self._make_mocks()

        with patch('stembot.executor.agent.Collection', mock_collection_class), \
             patch('stembot.executor.agent.KeyManager', mock_km_class), \
             patch.object(CONFIG, 'agtuuid', TEST_AGTUUID):
            resolve_agent_key('http://[::1]:8080')

        mock_km.resolve_key_objuuid.assert_called_once_with(TEST_AGTUUID)

    def test_falls_back_to_local_agtuuid_for_0_0_0_0(self):
        """Hostname '0.0.0.0' resolves to CONFIG.agtuuid."""
        mock_collection_class, _, mock_km_class, mock_km = self._make_mocks()

        with patch('stembot.executor.agent.Collection', mock_collection_class), \
             patch('stembot.executor.agent.KeyManager', mock_km_class), \
             patch.object(CONFIG, 'agtuuid', TEST_AGTUUID):
            resolve_agent_key('http://0.0.0.0:8080')

        mock_km.resolve_key_objuuid.assert_called_once_with(TEST_AGTUUID)

    def test_returns_keyuuid_and_decrypted_key_tuple(self):
        """Returns the (keyuuid, key) tuple from KeyManager.resolve_key_objuuid/decrypt_key."""
        mock_collection_class, _, mock_km_class, mock_km = self._make_mocks(
            resolved_keyuuid=TEST_KEYUUID, decrypted_key=TEST_KEY,
        )

        with patch('stembot.executor.agent.Collection', mock_collection_class), \
             patch('stembot.executor.agent.KeyManager', mock_km_class):
            result = resolve_agent_key('http://remote.local:8080')

        self.assertEqual(result, (TEST_KEYUUID, TEST_KEY))
        mock_km.decrypt_key.assert_called_once_with(TEST_KEYUUID)

    def test_raises_value_error_when_keyuuid_unresolved(self):
        """Raises ValueError when KeyManager cannot resolve a key UUID for the agent."""
        mock_collection_class, _, mock_km_class, mock_km = self._make_mocks(resolved_keyuuid=None)

        with patch('stembot.executor.agent.Collection', mock_collection_class), \
             patch('stembot.executor.agent.KeyManager', mock_km_class):
            with self.assertRaises(ValueError):
                resolve_agent_key('http://remote.local:8080')

        mock_km.decrypt_key.assert_not_called()

    def test_raises_value_error_when_decrypt_key_fails(self):
        """Wraps a KeyError from KeyManager.decrypt_key (e.g. expired key) as a ValueError."""
        mock_collection_class, _, mock_km_class, mock_km = self._make_mocks()
        mock_km.decrypt_key.side_effect = KeyError("Key 'k1' has expired")

        with patch('stembot.executor.agent.Collection', mock_collection_class), \
             patch('stembot.executor.agent.KeyManager', mock_km_class):
            with self.assertRaises(ValueError):
                resolve_agent_key('http://remote.local:8080')


if __name__ == '__main__':
    unittest.main()
