"""Tests for packet serialization and live server/client communication."""

import time

import pytest

from src.network.client import GameClient, LocalInput
from src.network.packet import (
    HEADER_SIZE,
    MAGIC,
    Packet,
    PacketType,
)
from src.network.server import GameServer


class TestPacketProtocol:
    def test_roundtrip_preserves_fields(self) -> None:
        pkt = Packet(msg_type=PacketType.CHAT, seq=42, timestamp=123.5,
                     payload=b"hello world")
        clone = Packet.deserialize(pkt.serialize())
        assert clone.msg_type is PacketType.CHAT
        assert clone.seq == 42 and clone.timestamp == 123.5
        assert clone.payload == b"hello world"

    def test_compression_shrinks_payload(self) -> None:
        blob = b"repeat" * 200
        compressed = Packet(msg_type=PacketType.SNAPSHOT, payload=blob, compressed=True)
        plain = Packet(msg_type=PacketType.SNAPSHOT, payload=blob, compressed=False)
        assert len(compressed.serialize()) < len(plain.serialize())
        assert Packet.deserialize(compressed.serialize()).payload == blob

    def test_crc_detects_corruption(self) -> None:
        wire = bytearray(Packet(msg_type=PacketType.PING, seq=1).serialize())
        wire[-2] ^= 0xFF  # flip a CRC byte
        with pytest.raises(ValueError):
            Packet.deserialize(bytes(wire))

    def test_bad_magic_rejected(self) -> None:
        wire = bytearray(Packet(msg_type=PacketType.PING).serialize())
        wire[0:4] = b"XXXX"
        with pytest.raises(ValueError):
            Packet.deserialize(bytes(wire))

    def test_json_helpers(self) -> None:
        pkt = Packet.from_json(PacketType.INPUT, {"x": 1.0, "y": -1.0}, compress=True)
        data = Packet.deserialize(pkt.serialize()).to_json()
        assert data["x"] == 1.0 and data["y"] == -1.0

    def test_header_size_constant_matches_struct(self) -> None:
        import struct

        from src.network.packet import HEADER_FMT

        assert HEADER_SIZE == struct.calcsize(HEADER_FMT)


@pytest.mark.network
class TestServerClientIntegration:
    def _wait_until(self, predicate, timeout: float = 3.0) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if predicate():
                return True
            time.sleep(0.02)
        return False

    def test_ping_pong_between_client_and_server(self) -> None:
        server = GameServer(port=0, snapshot_rate_hz=0)
        port = server.start()
        client = GameClient()
        try:
            assert client.connect(port=port) is True
            assert client.player_id >= 1
            sent = client.send_chat("ping?")
            assert sent is True
            reply = client.poll_message(timeout=3.0)
            assert reply is not None
            assert reply.msg_type is PacketType.CHAT  # server echoes chat traffic
        finally:
            client.disconnect()
            server.stop()

    def test_snapshot_broadcast_reaches_client(self) -> None:
        received = []

        def capture(client_conn, packet) -> None:
            pass  # server-side hook unused here

        server = GameServer(port=0, snapshot_rate_hz=50)
        server.on_packet = capture
        port = server.start()
        client = GameClient()
        try:
            assert client.connect(port=port)
            ok = self._wait_until(lambda: len(client.snapshot_buffer) >= 8)
            assert ok, "client should buffer snapshots"
            older, newer = client.latest_snapshots()
            assert older is not None and newer is not None
            assert newer.tick >= older.tick
        finally:
            client.disconnect()
            server.stop()

    def test_prediction_and_reconciliation(self) -> None:
        client = GameClient()
        client.local_position = (0.0, 0.0)
        # predict locally without a live socket (connected=False skips send)
        pos = client.predict(LocalInput(move_x=10, move_y=-4), speed=100)
        assert pos[0] > 0 and pos[1] < 0
        assert client.reconcile((pos[0] + 9999, pos[1])) is True
        assert client.local_position[0] == pytest.approx(pos[0] + 9999)
