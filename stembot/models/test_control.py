"""Serialization and deserialization tests for ControlForm variants.

These tests serve as a protocol contract between stembot-python and stembot-rust.
Both implementations must produce and consume identical JSON strings.
"""
import json
import unittest

from stembot.enums import ControlFormType
from stembot.models.control import (
    Benchmark,
    CheckTicket,
    CloseTicket,
    ControlFormTicket,
    CreatePeer,
    DeletePeers,
    DiscoverPeer,
    GetConfig,
    GetPeers,
    GetRoutes,
    Hop,
    LoadFile,
    SyncProcess,
    WriteFile,
)
from stembot.models.routing import Peer, Route

#pylint: disable=too-many-public-methods, too-many-lines, too-few-public-methods
class TestControlFormSerialization(unittest.TestCase):
    """Verify that model instances serialize to the expected canonical JSON."""

    def assert_json_eq(self, instance, expected_json: str):
        self.assertEqual(json.loads(instance.model_dump_json()), json.loads(expected_json))

    # -- LoadFile --

    def test_load_file_request(self):
        form = LoadFile(path="/etc/hosts")
        self.assert_json_eq(
            form,
            '{"type":"load_file","error":null,"objuuid":null,"coluuid":null,'
            '"b64zlib":null,"path":"/etc/hosts","size":null,"md5sum":null}',
        )

    def test_load_file_response(self):
        form = LoadFile(path="/etc/hosts", b64zlib="abc123", size=1024, md5sum="d8e8fca2dc0f896fd7cb4cb0031ba249")
        self.assert_json_eq(
            form,
            '{"type":"load_file","error":null,"objuuid":null,"coluuid":null,'
            '"b64zlib":"abc123","path":"/etc/hosts","size":1024,'
            '"md5sum":"d8e8fca2dc0f896fd7cb4cb0031ba249"}',
        )

    # -- WriteFile --

    def test_write_file_request(self):
        form = WriteFile(b64zlib="abc123", path="/tmp/out.txt")
        self.assert_json_eq(
            form,
            '{"type":"write_file","error":null,"objuuid":null,"coluuid":null,'
            '"b64zlib":"abc123","path":"/tmp/out.txt","size":null,"md5sum":null}',
        )

    def test_write_file_response(self):
        form = WriteFile(b64zlib="abc123", path="/tmp/out.txt", size=6, md5sum="d8e8fca2dc0f896fd7cb4cb0031ba249")
        self.assert_json_eq(
            form,
            '{"type":"write_file","error":null,"objuuid":null,"coluuid":null,'
            '"b64zlib":"abc123","path":"/tmp/out.txt","size":6,'
            '"md5sum":"d8e8fca2dc0f896fd7cb4cb0031ba249"}',
        )

    # -- SyncProcess --

    def test_sync_process_request_str_command(self):
        form = SyncProcess(command="ls /")
        self.assert_json_eq(
            form,
            '{"type":"sync_process","error":null,"objuuid":null,"coluuid":null,'
            '"timeout":15,"command":"ls /","stdout":null,"stderr":null,'
            '"status":null,"start_time":null,"elapsed_time":null}',
        )

    def test_sync_process_request_list_command(self):
        form = SyncProcess(command=["ls", "/"])
        self.assert_json_eq(
            form,
            '{"type":"sync_process","error":null,"objuuid":null,"coluuid":null,'
            '"timeout":15,"command":["ls","/"],"stdout":null,"stderr":null,'
            '"status":null,"start_time":null,"elapsed_time":null}',
        )

    def test_sync_process_response(self):
        form = SyncProcess(
            command="ls /",
            stdout="bin\nboot\n",
            stderr="",
            status=0,
            start_time=1000.0,
            elapsed_time=0.01,
        )
        self.assert_json_eq(
            form,
            '{"type":"sync_process","error":null,"objuuid":null,"coluuid":null,'
            '"timeout":15,"command":"ls /","stdout":"bin\\nboot\\n","stderr":"",'
            '"status":0,"start_time":1000.0,"elapsed_time":0.01}',
        )

    # -- CreatePeer --

    def test_create_peer(self):
        # HttpUrl normalizes the URL by adding a trailing slash
        form = CreatePeer(agtuuid="a1", url="http://10.0.0.1:8080")
        self.assert_json_eq(
            form,
            '{"type":"create_peer","error":null,"objuuid":null,"coluuid":null,'
            '"url":"http://10.0.0.1:8080/","ttl":null,"polling":false,"agtuuid":"a1"}',
        )

    # -- DiscoverPeer --

    def test_discover_peer(self):
        # url is a plain str field, no trailing slash normalization
        form = DiscoverPeer(url="http://10.0.0.1:8080")
        self.assert_json_eq(
            form,
            '{"type":"discover_peer","error":null,"objuuid":null,"coluuid":null,'
            '"agtuuid":null,"url":"http://10.0.0.1:8080","ttl":null,"polling":false,'
            '"error":null}',
        )

    # -- DeletePeers --

    def test_delete_peers(self):
        form = DeletePeers(agtuuids=["a1", "a2"])
        self.assert_json_eq(
            form,
            '{"type":"delete_peers","error":null,"objuuid":null,"coluuid":null,'
            '"agtuuids":["a1","a2"]}',
        )

    def test_delete_peers_all(self):
        form = DeletePeers(agtuuids=None)
        self.assert_json_eq(
            form,
            '{"type":"delete_peers","error":null,"objuuid":null,"coluuid":null,'
            '"agtuuids":null}',
        )

    # -- GetPeers --

    def test_get_peers_empty(self):
        form = GetPeers()
        self.assert_json_eq(
            form,
            '{"type":"get_peers","error":null,"objuuid":null,"coluuid":null,"peers":[]}',
        )

    def test_get_peers_with_data(self):
        form = GetPeers(
            peers=[
                Peer(
                    agtuuid="a2",
                    url="http://10.0.0.2:8080",
                    polling=False,
                    destroy_time=2000.0,
                    refresh_time=1000.0,
                )
            ]
        )
        self.assert_json_eq(
            form,
            '{"type":"get_peers","error":null,"objuuid":null,"coluuid":null,'
            '"peers":[{"agtuuid":"a2","polling":false,"destroy_time":2000.0,'
            '"refresh_time":1000.0,"url":"http://10.0.0.2:8080","objuuid":null,"coluuid":null}]}',
        )

    # -- GetRoutes --

    def test_get_routes_empty(self):
        form = GetRoutes()
        self.assert_json_eq(
            form,
            '{"type":"get_routes","error":null,"objuuid":null,"coluuid":null,"routes":[]}',
        )

    def test_get_routes_with_data(self):
        form = GetRoutes(routes=[Route(agtuuid="a2", gtwuuid="a1", weight=1)])
        self.assert_json_eq(
            form,
            '{"type":"get_routes","error":null,"objuuid":null,"coluuid":null,'
            '"routes":[{"agtuuid":"a2","gtwuuid":"a1","weight":1,"objuuid":null,"coluuid":null}]}',
        )

    # -- GetConfig --

    def test_get_config_request(self):
        form = GetConfig()
        self.assert_json_eq(
            form,
            '{"type":"get_config","error":null,"objuuid":null,"coluuid":null,"config":null}',
        )

    def test_get_config_response(self):
        form = GetConfig(config={"agtuuid": "a1", "port": 8080})
        self.assert_json_eq(
            form,
            '{"type":"get_config","error":null,"objuuid":null,"coluuid":null,'
            '"config":{"agtuuid":"a1","port":8080}}',
        )

    # -- Hop --

    def test_hop(self):
        hop = Hop(agtuuid="a1", hop_time=1000.0, type_str="ticket_request")
        self.assert_json_eq(
            hop,
            '{"agtuuid":"a1","hop_time":1000.0,"type_str":"ticket_request"}',
        )

    # -- ControlFormTicket --

    def test_control_form_ticket_create(self):
        form = ControlFormTicket(
            tckuuid="t1",
            src="a1",
            dst="a2",
            create_time=1000.0,
            service_time=None,
            tracing=False,
            hops=[],
            form=SyncProcess(command="ls /"),
            type=ControlFormType.CREATE_TICKET,
        )
        self.assert_json_eq(
            form,
            '{"type":"create_ticket","error":null,"objuuid":null,"coluuid":null,'
            '"tckuuid":"t1","src":"a1","dst":"a2","create_time":1000.0,'
            '"service_time":null,"tracing":false,"hops":[],'
            '"form":{"type":"sync_process","error":null,"objuuid":null,"coluuid":null,'
            '"timeout":15,"command":"ls /","stdout":null,"stderr":null,'
            '"status":null,"start_time":null,"elapsed_time":null}}',
        )

    def test_control_form_ticket_read_with_hops(self):
        form = ControlFormTicket(
            tckuuid="t1",
            src="a1",
            dst="a2",
            create_time=1000.0,
            service_time=0.5,
            tracing=True,
            hops=[Hop(agtuuid="a1", hop_time=1001.0, type_str="ticket_request")],
            form=SyncProcess(command="ls /"),
            type=ControlFormType.READ_TICKET,
        )
        self.assert_json_eq(
            form,
            '{"type":"read_ticket","error":null,"objuuid":null,"coluuid":null,'
            '"tckuuid":"t1","src":"a1","dst":"a2","create_time":1000.0,'
            '"service_time":0.5,"tracing":true,'
            '"hops":[{"agtuuid":"a1","hop_time":1001.0,"type_str":"ticket_request"}],'
            '"form":{"type":"sync_process","error":null,"objuuid":null,"coluuid":null,'
            '"timeout":15,"command":"ls /","stdout":null,"stderr":null,'
            '"status":null,"start_time":null,"elapsed_time":null}}',
        )

    # -- CheckTicket --

    def test_check_ticket_pending(self):
        form = CheckTicket(tckuuid="t1", create_time=1000.0)
        self.assert_json_eq(
            form,
            '{"type":"check_ticket","error":null,"objuuid":null,"coluuid":null,'
            '"tckuuid":"t1","create_time":1000.0,"service_time":null}',
        )

    def test_check_ticket_serviced(self):
        form = CheckTicket(tckuuid="t1", create_time=1000.0, service_time=0.5)
        self.assert_json_eq(
            form,
            '{"type":"check_ticket","error":null,"objuuid":null,"coluuid":null,'
            '"tckuuid":"t1","create_time":1000.0,"service_time":0.5}',
        )

    # -- CloseTicket --

    def test_close_ticket(self):
        form = CloseTicket(tckuuid="t1")
        self.assert_json_eq(
            form,
            '{"type":"close_ticket","error":null,"objuuid":null,"coluuid":null,'
            '"tckuuid":"t1"}',
        )

    # -- Benchmark --

    def test_benchmark_empty(self):
        form = Benchmark(outbound_size=None, inbound_size=None)
        self.assert_json_eq(
            form,
            '{"type":"benchmark","error":null,"objuuid":null,"coluuid":null,'
            '"outbound_size":null,"inbound_size":null,"payload":null}',
        )

    def test_benchmark_with_sizes(self):
        form = Benchmark(outbound_size=64, inbound_size=128)
        self.assert_json_eq(
            form,
            '{"type":"benchmark","error":null,"objuuid":null,"coluuid":null,'
            '"outbound_size":64,"inbound_size":128,"payload":null}',
        )

    def test_benchmark_with_payload(self):
        form = Benchmark(outbound_size=64, inbound_size=128, payload="abc")
        self.assert_json_eq(
            form,
            '{"type":"benchmark","error":null,"objuuid":null,"coluuid":null,'
            '"outbound_size":64,"inbound_size":128,"payload":"abc"}',
        )


class TestControlFormDeserialization(unittest.TestCase):
    """Verify that canonical JSON strings deserialize to the expected model instances."""

    # -- LoadFile --

    def test_load_file_request(self):
        json_str = (
            '{"type":"load_file","error":null,"objuuid":null,"coluuid":null,'
            '"b64zlib":null,"path":"/etc/hosts","size":null,"md5sum":null}'
        )
        self.assertEqual(LoadFile.model_validate_json(json_str), LoadFile(path="/etc/hosts"))

    def test_load_file_response(self):
        json_str = (
            '{"type":"load_file","error":null,"objuuid":null,"coluuid":null,'
            '"b64zlib":"abc123","path":"/etc/hosts","size":1024,'
            '"md5sum":"d8e8fca2dc0f896fd7cb4cb0031ba249"}'
        )
        self.assertEqual(
            LoadFile.model_validate_json(json_str),
            LoadFile(path="/etc/hosts", b64zlib="abc123", size=1024, md5sum="d8e8fca2dc0f896fd7cb4cb0031ba249"),
        )

    # -- WriteFile --

    def test_write_file_request(self):
        json_str = (
            '{"type":"write_file","error":null,"objuuid":null,"coluuid":null,'
            '"b64zlib":"abc123","path":"/tmp/out.txt","size":null,"md5sum":null}'
        )
        self.assertEqual(
            WriteFile.model_validate_json(json_str),
            WriteFile(b64zlib="abc123", path="/tmp/out.txt"),
        )

    def test_write_file_response(self):
        json_str = (
            '{"type":"write_file","error":null,"objuuid":null,"coluuid":null,'
            '"b64zlib":"abc123","path":"/tmp/out.txt","size":6,'
            '"md5sum":"d8e8fca2dc0f896fd7cb4cb0031ba249"}'
        )
        self.assertEqual(
            WriteFile.model_validate_json(json_str),
            WriteFile(b64zlib="abc123", path="/tmp/out.txt", size=6, md5sum="d8e8fca2dc0f896fd7cb4cb0031ba249"),
        )

    # -- SyncProcess --

    def test_sync_process_request_str_command(self):
        json_str = (
            '{"type":"sync_process","error":null,"objuuid":null,"coluuid":null,'
            '"timeout":15,"command":"ls /","stdout":null,"stderr":null,'
            '"status":null,"start_time":null,"elapsed_time":null}'
        )
        self.assertEqual(SyncProcess.model_validate_json(json_str), SyncProcess(command="ls /"))

    def test_sync_process_request_list_command(self):
        json_str = (
            '{"type":"sync_process","error":null,"objuuid":null,"coluuid":null,'
            '"timeout":15,"command":["ls","/"],"stdout":null,"stderr":null,'
            '"status":null,"start_time":null,"elapsed_time":null}'
        )
        self.assertEqual(SyncProcess.model_validate_json(json_str), SyncProcess(command=["ls", "/"]))

    def test_sync_process_response(self):
        json_str = (
            '{"type":"sync_process","error":null,"objuuid":null,"coluuid":null,'
            '"timeout":15,"command":"ls /","stdout":"bin\\nboot\\n","stderr":"",'
            '"status":0,"start_time":1000.0,"elapsed_time":0.01}'
        )
        self.assertEqual(
            SyncProcess.model_validate_json(json_str),
            SyncProcess(
                command="ls /",
                stdout="bin\nboot\n",
                stderr="",
                status=0,
                start_time=1000.0, elapsed_time=0.01),
        )

    # -- CreatePeer --

    def test_create_peer(self):
        json_str = (
            '{"type":"create_peer","error":null,"objuuid":null,"coluuid":null,'
            '"url":"http://10.0.0.1:8080/","ttl":null,"polling":false,"agtuuid":"a1"}'
        )
        self.assertEqual(
            CreatePeer.model_validate_json(json_str),
            CreatePeer(agtuuid="a1", url="http://10.0.0.1:8080"),
        )

    # -- DiscoverPeer --

    def test_discover_peer(self):
        json_str = (
            '{"type":"discover_peer","error":null,"objuuid":null,"coluuid":null,'
            '"agtuuid":null,"url":"http://10.0.0.1:8080","ttl":null,"polling":false,'
            '"error":null}'
        )
        self.assertEqual(
            DiscoverPeer.model_validate_json(json_str),
            DiscoverPeer(url="http://10.0.0.1:8080"),
        )

    # -- DeletePeers --

    def test_delete_peers(self):
        json_str = (
            '{"type":"delete_peers","error":null,"objuuid":null,"coluuid":null,'
            '"agtuuids":["a1","a2"]}'
        )
        self.assertEqual(DeletePeers.model_validate_json(json_str), DeletePeers(agtuuids=["a1", "a2"]))

    def test_delete_peers_all(self):
        json_str = (
            '{"type":"delete_peers","error":null,"objuuid":null,"coluuid":null,'
            '"agtuuids":null}'
        )
        self.assertEqual(DeletePeers.model_validate_json(json_str), DeletePeers(agtuuids=None))

    # -- GetPeers --

    def test_get_peers_empty(self):
        json_str = '{"type":"get_peers","error":null,"objuuid":null,"coluuid":null,"peers":[]}'
        self.assertEqual(GetPeers.model_validate_json(json_str), GetPeers())

    def test_get_peers_with_data(self):
        json_str = (
            '{"type":"get_peers","error":null,"objuuid":null,"coluuid":null,'
            '"peers":[{"agtuuid":"a2","polling":false,"destroy_time":2000.0,'
            '"refresh_time":1000.0,"url":"http://10.0.0.2:8080","objuuid":null,"coluuid":null}]}'
        )
        self.assertEqual(
            GetPeers.model_validate_json(json_str),
            GetPeers(
                peers=[
                    Peer(
                        agtuuid="a2",
                        url="http://10.0.0.2:8080",
                        polling=False,
                        destroy_time=2000.0,
                        refresh_time=1000.0,
                    )
                ]
            ),
        )

    # -- GetRoutes --

    def test_get_routes_empty(self):
        json_str = '{"type":"get_routes","error":null,"objuuid":null,"coluuid":null,"routes":[]}'
        self.assertEqual(GetRoutes.model_validate_json(json_str), GetRoutes())

    def test_get_routes_with_data(self):
        json_str = (
            '{"type":"get_routes","error":null,"objuuid":null,"coluuid":null,'
            '"routes":[{"agtuuid":"a2","gtwuuid":"a1","weight":1,"objuuid":null,"coluuid":null}]}'
        )
        self.assertEqual(
            GetRoutes.model_validate_json(json_str),
            GetRoutes(routes=[Route(agtuuid="a2", gtwuuid="a1", weight=1)]),
        )

    # -- GetConfig --

    def test_get_config_request(self):
        json_str = '{"type":"get_config","error":null,"objuuid":null,"coluuid":null,"config":null}'
        self.assertEqual(GetConfig.model_validate_json(json_str), GetConfig())

    def test_get_config_response(self):
        json_str = (
            '{"type":"get_config","error":null,"objuuid":null,"coluuid":null,'
            '"config":{"agtuuid":"a1","port":8080}}'
        )
        self.assertEqual(
            GetConfig.model_validate_json(json_str),
            GetConfig(config={"agtuuid": "a1", "port": 8080}),
        )

    # -- Hop --

    def test_hop(self):
        json_str = '{"agtuuid":"a1","hop_time":1000.0,"type_str":"ticket_request"}'
        self.assertEqual(
            Hop.model_validate_json(json_str),
            Hop(agtuuid="a1", hop_time=1000.0, type_str="ticket_request"),
        )

    # -- ControlFormTicket --

    def test_control_form_ticket_create(self):
        json_str = (
            '{"type":"create_ticket","error":null,"objuuid":null,"coluuid":null,'
            '"tckuuid":"t1","src":"a1","dst":"a2","create_time":1000.0,'
            '"service_time":null,"tracing":false,"hops":[],'
            '"form":{"type":"sync_process","error":null,"objuuid":null,"coluuid":null,'
            '"timeout":15,"command":"ls /","stdout":null,"stderr":null,'
            '"status":null,"start_time":null,"elapsed_time":null}}'
        )
        self.assertEqual(
            ControlFormTicket.model_validate_json(json_str),
            ControlFormTicket(
                tckuuid="t1",
                src="a1",
                dst="a2",
                create_time=1000.0,
                service_time=None,
                tracing=False,
                hops=[],
                form=SyncProcess(command="ls /"),
                type=ControlFormType.CREATE_TICKET,
            ),
        )

    def test_control_form_ticket_read_with_hops(self):
        json_str = (
            '{"type":"read_ticket","error":null,"objuuid":null,"coluuid":null,'
            '"tckuuid":"t1","src":"a1","dst":"a2","create_time":1000.0,'
            '"service_time":0.5,"tracing":true,'
            '"hops":[{"agtuuid":"a1","hop_time":1001.0,"type_str":"ticket_request"}],'
            '"form":{"type":"sync_process","error":null,"objuuid":null,"coluuid":null,'
            '"timeout":15,"command":"ls /","stdout":null,"stderr":null,'
            '"status":null,"start_time":null,"elapsed_time":null}}'
        )
        self.assertEqual(
            ControlFormTicket.model_validate_json(json_str),
            ControlFormTicket(
                tckuuid="t1",
                src="a1",
                dst="a2",
                create_time=1000.0,
                service_time=0.5,
                tracing=True,
                hops=[Hop(agtuuid="a1", hop_time=1001.0, type_str="ticket_request")],
                form=SyncProcess(command="ls /"),
                type=ControlFormType.READ_TICKET,
            ),
        )

    # -- CheckTicket --

    def test_check_ticket_pending(self):
        json_str = (
            '{"type":"check_ticket","error":null,"objuuid":null,"coluuid":null,'
            '"tckuuid":"t1","create_time":1000.0,"service_time":null}'
        )
        self.assertEqual(
            CheckTicket.model_validate_json(json_str),
            CheckTicket(tckuuid="t1", create_time=1000.0),
        )

    def test_check_ticket_serviced(self):
        json_str = (
            '{"type":"check_ticket","error":null,"objuuid":null,"coluuid":null,'
            '"tckuuid":"t1","create_time":1000.0,"service_time":0.5}'
        )
        self.assertEqual(
            CheckTicket.model_validate_json(json_str),
            CheckTicket(tckuuid="t1", create_time=1000.0, service_time=0.5),
        )

    # -- CloseTicket --

    def test_close_ticket(self):
        json_str = (
            '{"type":"close_ticket","error":null,"objuuid":null,"coluuid":null,'
            '"tckuuid":"t1"}'
        )
        self.assertEqual(
            CloseTicket.model_validate_json(json_str),
            CloseTicket(tckuuid="t1"),
        )

    # -- Benchmark --

    def test_benchmark_empty(self):
        json_str = (
            '{"type":"benchmark","error":null,"objuuid":null,"coluuid":null,'
            '"outbound_size":null,"inbound_size":null,"payload":null}'
        )
        self.assertEqual(
            Benchmark.model_validate_json(json_str),
            Benchmark(outbound_size=None, inbound_size=None),
        )

    def test_benchmark_with_sizes(self):
        json_str = (
            '{"type":"benchmark","error":null,"objuuid":null,"coluuid":null,'
            '"outbound_size":64,"inbound_size":128,"payload":null}'
        )
        self.assertEqual(
            Benchmark.model_validate_json(json_str),
            Benchmark(outbound_size=64, inbound_size=128),
        )

    def test_benchmark_with_payload(self):
        json_str = (
            '{"type":"benchmark","error":null,"objuuid":null,"coluuid":null,'
            '"outbound_size":64,"inbound_size":128,"payload":"abc"}'
        )
        self.assertEqual(
            Benchmark.model_validate_json(json_str),
            Benchmark(outbound_size=64, inbound_size=128, payload="abc"),
        )


if __name__ == "__main__":
    unittest.main()
