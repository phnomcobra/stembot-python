"""Serialization and deserialization tests for NetworkMessage variants.

These tests serve as a protocol contract between stembot-python and stembot-rust.
Both implementations must produce and consume identical JSON strings.
"""
import json
import unittest

from stembot.enums import NetworkMessageType
from stembot.models.control import SyncProcess
from stembot.models.network import (
    Acknowledgement,
    Advertisement,
    NetworkMessagesRequest,
    NetworkMessagesResponse,
    NetworkTicket,
    Ping,
    TicketTraceResponse,
)
from stembot.models.routing import Route


class TestNetworkMessageSerialization(unittest.TestCase):
    """Verify that model instances serialize to the expected canonical JSON."""

    def assertJsonEqual(self, instance, expected_json: str):
        self.assertEqual(json.loads(instance.model_dump_json()), json.loads(expected_json))

    # -- Ping --

    def test_ping(self):
        msg = Ping(src="a1", timestamp=1000.0)
        self.assertJsonEqual(
            msg,
            '{"type":"ping","dest":null,"src":"a1","isrc":null,"timestamp":1000.0,'
            '"objuuid":null,"coluuid":null}',
        )

    # -- NetworkMessagesRequest --

    def test_network_messages_request(self):
        msg = NetworkMessagesRequest(src="a1", timestamp=1000.0)
        self.assertJsonEqual(
            msg,
            '{"type":"messages_request","dest":null,"src":"a1","isrc":null,"timestamp":1000.0,'
            '"objuuid":null,"coluuid":null}',
        )

    # -- Acknowledgement --

    def test_acknowledgement_ping(self):
        msg = Acknowledgement(ack_type=NetworkMessageType.PING, src="a1", timestamp=1000.0)
        self.assertJsonEqual(
            msg,
            '{"type":"acknowledgement","dest":null,"src":"a1","isrc":null,"timestamp":1000.0,'
            '"objuuid":null,"coluuid":null,"ack_type":"ping","forwarded":null,"error":null}',
        )

    def test_acknowledgement_with_error(self):
        msg = Acknowledgement(
            ack_type=NetworkMessageType.TICKET_REQUEST,
            src="a1",
            timestamp=1000.0,
            error="timeout",
        )
        self.assertJsonEqual(
            msg,
            '{"type":"acknowledgement","dest":null,"src":"a1","isrc":null,"timestamp":1000.0,'
            '"objuuid":null,"coluuid":null,"ack_type":"ticket_request","forwarded":null,'
            '"error":"timeout"}',
        )

    def test_acknowledgement_forwarded(self):
        msg = Acknowledgement(
            ack_type=NetworkMessageType.PING,
            src="a1",
            timestamp=1000.0,
            forwarded="a2",
        )
        self.assertJsonEqual(
            msg,
            '{"type":"acknowledgement","dest":null,"src":"a1","isrc":null,"timestamp":1000.0,'
            '"objuuid":null,"coluuid":null,"ack_type":"ping","forwarded":"a2","error":null}',
        )

    # -- Advertisement --

    def test_advertisement_empty_routes(self):
        msg = Advertisement(agtuuid="a1", src="a1", timestamp=1000.0, routes=[])
        self.assertJsonEqual(
            msg,
            '{"type":"advertisement","dest":null,"src":"a1","isrc":null,"timestamp":1000.0,'
            '"objuuid":null,"coluuid":null,"routes":[],"agtuuid":"a1"}',
        )

    def test_advertisement_with_routes(self):
        msg = Advertisement(
            agtuuid="a1",
            src="a1",
            timestamp=1000.0,
            routes=[Route(agtuuid="a2", gtwuuid="a1", weight=1)],
        )
        self.assertJsonEqual(
            msg,
            '{"type":"advertisement","dest":null,"src":"a1","isrc":null,"timestamp":1000.0,'
            '"objuuid":null,"coluuid":null,'
            '"routes":[{"agtuuid":"a2","gtwuuid":"a1","weight":1,"objuuid":null,"coluuid":null}],'
            '"agtuuid":"a1"}',
        )

    # -- NetworkMessagesResponse --

    def test_network_messages_response_empty(self):
        msg = NetworkMessagesResponse(src="a1", timestamp=1000.0)
        self.assertJsonEqual(
            msg,
            '{"type":"messages_response","dest":null,"src":"a1","isrc":null,"timestamp":1000.0,'
            '"objuuid":null,"coluuid":null,"messages":[]}',
        )

    def test_network_messages_response_with_ping(self):
        msg = NetworkMessagesResponse(
            src="a1",
            timestamp=1000.0,
            messages=[Ping(src="b1", timestamp=2000.0)],
        )
        self.assertJsonEqual(
            msg,
            '{"type":"messages_response","dest":null,"src":"a1","isrc":null,"timestamp":1000.0,'
            '"objuuid":null,"coluuid":null,'
            '"messages":[{"type":"ping","dest":null,"src":"b1","isrc":null,"timestamp":2000.0,'
            '"objuuid":null,"coluuid":null}]}',
        )

    # -- TicketTraceResponse --

    def test_ticket_trace_response(self):
        msg = TicketTraceResponse(
            tckuuid="t1",
            network_ticket_type=NetworkMessageType.TICKET_REQUEST,
            src="a1",
            timestamp=1000.0,
            hop_time=1000.0,
        )
        self.assertJsonEqual(
            msg,
            '{"type":"ticket_trace_response","dest":null,"src":"a1","isrc":null,"timestamp":1000.0,'
            '"objuuid":null,"coluuid":null,"tckuuid":"t1","hop_time":1000.0,'
            '"network_ticket_type":"ticket_request"}',
        )

    # -- NetworkTicket --

    def test_network_ticket_request(self):
        msg = NetworkTicket(
            tckuuid="t1",
            src="a1",
            timestamp=1000.0,
            form=SyncProcess(command="ls /"),
            type=NetworkMessageType.TICKET_REQUEST,
        )
        self.assertJsonEqual(
            msg,
            '{"type":"ticket_request","dest":null,"src":"a1","isrc":null,"timestamp":1000.0,'
            '"objuuid":null,"coluuid":null,"tckuuid":"t1","error":null,"create_time":null,'
            '"service_time":null,"tracing":false,'
            '"form":{"type":"sync_process","error":null,"objuuid":null,"coluuid":null,'
            '"timeout":15,"command":"ls /","stdout":null,"stderr":null,'
            '"status":null,"start_time":null,"elapsed_time":null}}',
        )

    def test_network_ticket_response(self):
        msg = NetworkTicket(
            tckuuid="t1",
            src="a1",
            timestamp=1000.0,
            service_time=0.5,
            form=SyncProcess(
                command="ls /",
                stdout="bin\n",
                status=0,
                start_time=1000.0,
                elapsed_time=0.1,
            ),
            type=NetworkMessageType.TICKET_RESPONSE,
        )
        self.assertJsonEqual(
            msg,
            '{"type":"ticket_response","dest":null,"src":"a1","isrc":null,"timestamp":1000.0,'
            '"objuuid":null,"coluuid":null,"tckuuid":"t1","error":null,"create_time":null,'
            '"service_time":0.5,"tracing":false,'
            '"form":{"type":"sync_process","error":null,"objuuid":null,"coluuid":null,'
            '"timeout":15,"command":"ls /","stdout":"bin\\n","stderr":null,'
            '"status":0,"start_time":1000.0,"elapsed_time":0.1}}',
        )


class TestNetworkMessageDeserialization(unittest.TestCase):
    """Verify that canonical JSON strings deserialize to the expected model instances."""

    # -- Ping --

    def test_ping(self):
        json_str = (
            '{"type":"ping","dest":null,"src":"a1","isrc":null,"timestamp":1000.0,'
            '"objuuid":null,"coluuid":null}'
        )
        self.assertEqual(Ping.model_validate_json(json_str), Ping(src="a1", timestamp=1000.0))

    # -- NetworkMessagesRequest --

    def test_network_messages_request(self):
        json_str = (
            '{"type":"messages_request","dest":null,"src":"a1","isrc":null,"timestamp":1000.0,'
            '"objuuid":null,"coluuid":null}'
        )
        self.assertEqual(
            NetworkMessagesRequest.model_validate_json(json_str),
            NetworkMessagesRequest(src="a1", timestamp=1000.0),
        )

    # -- Acknowledgement --

    def test_acknowledgement_ping(self):
        json_str = (
            '{"type":"acknowledgement","dest":null,"src":"a1","isrc":null,"timestamp":1000.0,'
            '"objuuid":null,"coluuid":null,"ack_type":"ping","forwarded":null,"error":null}'
        )
        self.assertEqual(
            Acknowledgement.model_validate_json(json_str),
            Acknowledgement(ack_type=NetworkMessageType.PING, src="a1", timestamp=1000.0),
        )

    def test_acknowledgement_with_error(self):
        json_str = (
            '{"type":"acknowledgement","dest":null,"src":"a1","isrc":null,"timestamp":1000.0,'
            '"objuuid":null,"coluuid":null,"ack_type":"ticket_request","forwarded":null,'
            '"error":"timeout"}'
        )
        self.assertEqual(
            Acknowledgement.model_validate_json(json_str),
            Acknowledgement(
                ack_type=NetworkMessageType.TICKET_REQUEST,
                src="a1",
                timestamp=1000.0,
                error="timeout",
            ),
        )

    def test_acknowledgement_forwarded(self):
        json_str = (
            '{"type":"acknowledgement","dest":null,"src":"a1","isrc":null,"timestamp":1000.0,'
            '"objuuid":null,"coluuid":null,"ack_type":"ping","forwarded":"a2","error":null}'
        )
        self.assertEqual(
            Acknowledgement.model_validate_json(json_str),
            Acknowledgement(
                ack_type=NetworkMessageType.PING,
                src="a1",
                timestamp=1000.0,
                forwarded="a2",
            ),
        )

    # -- Advertisement --

    def test_advertisement_empty_routes(self):
        json_str = (
            '{"type":"advertisement","dest":null,"src":"a1","isrc":null,"timestamp":1000.0,'
            '"objuuid":null,"coluuid":null,"routes":[],"agtuuid":"a1"}'
        )
        self.assertEqual(
            Advertisement.model_validate_json(json_str),
            Advertisement(agtuuid="a1", src="a1", timestamp=1000.0, routes=[]),
        )

    def test_advertisement_with_routes(self):
        json_str = (
            '{"type":"advertisement","dest":null,"src":"a1","isrc":null,"timestamp":1000.0,'
            '"objuuid":null,"coluuid":null,'
            '"routes":[{"agtuuid":"a2","gtwuuid":"a1","weight":1,"objuuid":null,"coluuid":null}],'
            '"agtuuid":"a1"}'
        )
        self.assertEqual(
            Advertisement.model_validate_json(json_str),
            Advertisement(
                agtuuid="a1",
                src="a1",
                timestamp=1000.0,
                routes=[Route(agtuuid="a2", gtwuuid="a1", weight=1)],
            ),
        )

    # -- NetworkMessagesResponse --

    def test_network_messages_response_empty(self):
        json_str = (
            '{"type":"messages_response","dest":null,"src":"a1","isrc":null,"timestamp":1000.0,'
            '"objuuid":null,"coluuid":null,"messages":[]}'
        )
        self.assertEqual(
            NetworkMessagesResponse.model_validate_json(json_str),
            NetworkMessagesResponse(src="a1", timestamp=1000.0),
        )

    def test_network_messages_response_with_ping(self):
        # messages items are deserialized as NetworkMessage base instances; verify JSON round-trip
        json_str = (
            '{"type":"messages_response","dest":null,"src":"a1","isrc":null,"timestamp":1000.0,'
            '"objuuid":null,"coluuid":null,'
            '"messages":[{"type":"ping","dest":null,"src":"b1","isrc":null,"timestamp":2000.0,'
            '"objuuid":null,"coluuid":null}]}'
        )
        result = NetworkMessagesResponse.model_validate_json(json_str)
        self.assertEqual(json.loads(result.model_dump_json()), json.loads(json_str))

    # -- TicketTraceResponse --

    def test_ticket_trace_response(self):
        json_str = (
            '{"type":"ticket_trace_response","dest":null,"src":"a1","isrc":null,"timestamp":1000.0,'
            '"objuuid":null,"coluuid":null,"tckuuid":"t1","hop_time":1000.0,'
            '"network_ticket_type":"ticket_request"}'
        )
        self.assertEqual(
            TicketTraceResponse.model_validate_json(json_str),
            TicketTraceResponse(
                tckuuid="t1",
                network_ticket_type=NetworkMessageType.TICKET_REQUEST,
                src="a1",
                timestamp=1000.0,
                hop_time=1000.0,
            ),
        )

    # -- NetworkTicket --

    def test_network_ticket_request(self):
        json_str = (
            '{"type":"ticket_request","dest":null,"src":"a1","isrc":null,"timestamp":1000.0,'
            '"objuuid":null,"coluuid":null,"tckuuid":"t1","error":null,"create_time":null,'
            '"service_time":null,"tracing":false,'
            '"form":{"type":"sync_process","error":null,"objuuid":null,"coluuid":null,'
            '"timeout":15,"command":"ls /","stdout":null,"stderr":null,'
            '"status":null,"start_time":null,"elapsed_time":null}}'
        )
        self.assertEqual(
            NetworkTicket.model_validate_json(json_str),
            NetworkTicket(
                tckuuid="t1",
                src="a1",
                timestamp=1000.0,
                form=SyncProcess(command="ls /"),
                type=NetworkMessageType.TICKET_REQUEST,
            ),
        )

    def test_network_ticket_response(self):
        json_str = (
            '{"type":"ticket_response","dest":null,"src":"a1","isrc":null,"timestamp":1000.0,'
            '"objuuid":null,"coluuid":null,"tckuuid":"t1","error":null,"create_time":null,'
            '"service_time":0.5,"tracing":false,'
            '"form":{"type":"sync_process","error":null,"objuuid":null,"coluuid":null,'
            '"timeout":15,"command":"ls /","stdout":"bin\\n","stderr":null,'
            '"status":0,"start_time":1000.0,"elapsed_time":0.1}}'
        )
        self.assertEqual(
            NetworkTicket.model_validate_json(json_str),
            NetworkTicket(
                tckuuid="t1",
                src="a1",
                timestamp=1000.0,
                service_time=0.5,
                form=SyncProcess(
                    command="ls /",
                    stdout="bin\n",
                    status=0,
                    start_time=1000.0,
                    elapsed_time=0.1,
                ),
                type=NetworkMessageType.TICKET_RESPONSE,
            ),
        )


if __name__ == "__main__":
    unittest.main()
