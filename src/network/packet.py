"""Binary packet protocol: framing, compression, CRC integrity checks."""

from __future__ import annotations

import enum
import json
import struct
import zlib
from dataclasses import dataclass
from typing import Any, Optional

MAGIC: bytes = b"GF01"
FLAG_COMPRESSED: int = 0x0001
HEADER_FMT: str = "!4sHHIdI"
HEADER_SIZE: int = struct.calcsize(HEADER_FMT)
CRC_SIZE: int = 4


class PacketType(enum.IntEnum):
    """Message categories used by the game protocol."""

    HELLO = 1
    WELCOME = 2
    INPUT = 3
    SNAPSHOT = 4
    CHAT = 5
    PING = 6
    PONG = 7
    DISCONNECT = 8
    CUSTOM = 100


@dataclass(slots=True)
class Packet:
    """A single framed message exchanged between server and clients."""

    msg_type: PacketType
    seq: int = 0
    timestamp: float = 0.0
    payload: bytes = b""
    compressed: bool = False

    # -- serialization -----------------------------------------------------------

    def _body_bytes(self) -> bytes:
        """Optionally compress the raw payload."""
        if self.compressed:
            return zlib.compress(self.payload)
        return self.payload

    @staticmethod
    def _decompress(body: bytes, was_compressed: bool) -> bytes:
        """Undo compression applied on the wire."""
        return zlib.decompress(body) if was_compressed else body

    def serialize(self) -> bytes:
        """Encode to wire format: header + body + CRC32 trailer."""
        body = self._body_bytes()
        flags = FLAG_COMPRESSED if self.compressed else 0
        header = struct.pack(HEADER_FMT, MAGIC, flags, int(self.msg_type),
                             self.seq, self.timestamp, len(body))
        crc = zlib.crc32(body) & 0xFFFFFFFF
        return header + body + struct.pack("!I", crc)

    @classmethod
    def deserialize(cls, buffer: bytes) -> "Packet":
        """Decode one full packet from *buffer*, verifying magic and CRC."""
        if len(buffer) < HEADER_SIZE + CRC_SIZE:
            raise ValueError("buffer too short for a packet")
        magic, flags, msg_type_raw, seq, ts, length = struct.unpack_from(HEADER_FMT, buffer, 0)
        if magic != MAGIC:
            raise ValueError(f"bad magic {magic!r}")
        expected_total = HEADER_SIZE + length + CRC_SIZE
        if len(buffer) < expected_total:
            raise ValueError(f"incomplete packet: need {expected_total}, got {len(buffer)}")
        body_start = HEADER_SIZE
        body = buffer[body_start:body_start + length]
        (crc_stored,) = struct.unpack_from("!I", buffer, body_start + length)
        if zlib.crc32(body) & 0xFFFFFFFF != crc_stored:
            raise ValueError("CRC mismatch — packet corrupted")
        payload = cls._decompress(body, bool(flags & FLAG_COMPRESSED))
        return cls(msg_type=PacketType(msg_type_raw), seq=seq, timestamp=ts,
                   payload=payload, compressed=bool(flags & FLAG_COMPRESSED))

    # -- JSON conveniences ---------------------------------------------------------

    @classmethod
    def from_json(cls, msg_type: PacketType, obj: Any, seq: int = 0,
                  compress: bool = False, **kwargs: Any) -> "Packet":
        """Build a packet whose payload is UTF-8 encoded JSON."""
        return cls(msg_type=msg_type, seq=seq,
                   payload=json.dumps(obj).encode("utf-8"),
                   compressed=compress, **kwargs)

    def to_json(self) -> Any:
        """Parse the payload as JSON."""
        return json.loads(self.payload.decode("utf-8"))

    def wire_size(self) -> int:
        """Exact byte count this packet occupies on the wire."""
        return HEADER_SIZE + len(self._body_bytes()) + CRC_SIZE


# -- stream framing helpers --------------------------------------------------------


def send_packet(sock, packet: Packet) -> int:
    """Write one length-prefixed packet to *sock*; returns bytes written."""
    wire = packet.serialize()
    sock.sendall(struct.pack("!I", len(wire)) + wire)
    return len(wire) + 4


def _recv_exact(sock, count: int) -> bytes:
    """Read exactly *count* bytes or raise ConnectionError."""
    chunks = bytearray()
    while len(chunks) < count:
        chunk = sock.recv(count - len(chunks))
        if not chunk:
            raise ConnectionError("peer closed connection mid-packet")
        chunks.extend(chunk)
    return bytes(chunks)


def recv_packet(sock) -> Optional[Packet]:
    """Blocking read of one framed packet; None only on clean EOF at boundary."""
    try:
        (wire_len,) = struct.unpack("!I", _recv_exact(sock, 4))
    except ConnectionError:
        return None
    wire = _recv_exact(sock, wire_len)
    return Packet.deserialize(wire)
