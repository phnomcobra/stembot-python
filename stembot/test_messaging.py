"""Unit tests for message queue filtering behavior."""
import os
import tempfile
import unittest
from unittest.mock import patch

from stembot.dao import Collection
from stembot.enums import ControlFormType, NetworkMessageType
from stembot.messaging import pull_filtered_network_messages
from stembot.models.control import SyncProcess
from stembot.models.network import NetworkMessage, NetworkMessagesRequest, NetworkTicket, Ping
from stembot.models.routing import Route


class _CollectionRouter:
    """Patchable stand-in that routes Collection[T](name) calls to prepared collections."""

    collections = {}

    def __class_getitem__(cls, _item):
        def factory(collection_name, _connection_str=None, _in_memory=False, _model=None):
            return cls.collections[collection_name]

        return factory


class TestPullNetworkMessagesWhitelist(unittest.TestCase):
    """Verify whitelist filtering and error-ticket requeueing."""

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.old_cwd = os.getcwd()
        os.chdir(self.tempdir.name)

        self.messages = Collection[NetworkMessage]("messages")
        self.messages.create_attribute("dest", "/dest")
        self.messages.create_attribute("timestamp", "/timestamp")

        self.routes = Collection[Route]("routes")

        _CollectionRouter.collections = {
            "messages": self.messages,
            "routes": self.routes,
        }
        self.collection_patch = patch("stembot.messaging.Collection", _CollectionRouter)
        self.collection_patch.start()

        self.addCleanup(self.collection_patch.stop)
        self.addCleanup(self.tempdir.cleanup)
        self.addCleanup(os.chdir, self.old_cwd)

    def tearDown(self):
        self.messages.destroy()
        self.routes.destroy()

    def _seed_routes(self):
        self.routes.upsert_object(Route(agtuuid="relay", gtwuuid="src", weight=1))

    def test_network_whitelist_filters_disallowed_ticket_and_enqueues_error(self):
        self._seed_routes()

        self.messages.upsert_object(Ping(src="origin", dest="src", isrc="origin"))
        self.messages.upsert_object(
            NetworkTicket(
                src="origin",
                dest="src",
                isrc="origin",
                form=SyncProcess(command="echo hi"),
                type=NetworkMessageType.TICKET_REQUEST,
            )
        )

        request = NetworkMessagesRequest(
            src="origin",
            isrc="src",
            network_whitelist=[NetworkMessageType.PING],
        )

        messages = pull_filtered_network_messages(request)

        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].type, NetworkMessageType.PING)

        pending = self.messages.find()
        self.assertEqual(len(pending), 1)
        response = pending[0].object
        self.assertEqual(response.type, NetworkMessageType.TICKET_RESPONSE)
        self.assertEqual(response.src, "src")
        self.assertEqual(response.dest, "origin")
        self.assertIn("not allowed by whitelist", response.error)

    def test_control_whitelist_filters_disallowed_ticket_and_enqueues_error(self):
        self._seed_routes()

        self.messages.upsert_object(
            NetworkTicket(
                src="origin",
                dest="src",
                isrc="origin",
                form=SyncProcess(command="echo hi"),
                type=NetworkMessageType.TICKET_REQUEST,
            )
        )

        request = NetworkMessagesRequest(
            src="origin",
            isrc="src",
            control_whitelist=[ControlFormType.GET_PEERS],
        )

        messages = pull_filtered_network_messages(request)

        self.assertEqual(messages, [])

        pending = self.messages.find()
        self.assertEqual(len(pending), 1)
        response = pending[0].object
        self.assertEqual(response.type, NetworkMessageType.TICKET_RESPONSE)
        self.assertEqual(response.src, "src")
        self.assertEqual(response.dest, "origin")
        self.assertIn("not allowed by whitelist", response.error)
        self.assertEqual(response.form['type'], ControlFormType.SYNC_PROCESS)
