"""Networking subsystem: protocol packets, threaded server, game client."""

from src.network.client import GameClient, LocalInput, Snapshot
from src.network.packet import (
    HEADER_SIZE,
    MAGIC,
    Packet,
    PacketType,
    recv_packet,
    send_packet,
)
from src.network.server import ClientConnection, GameServer

__all__ = [
    "GameClient",
    "LocalInput",
    "Snapshot",
    "HEADER_SIZE",
    "MAGIC",
    "Packet",
    "PacketType",
    "recv_packet",
    "send_packet",
    "ClientConnection",
    "GameServer",
]
