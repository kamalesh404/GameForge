"""Threaded TCP game server: client registry, echo, and state snapshots."""

from __future__ import annotations

import socket
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, Optional, Tuple

from src.network.packet import Packet, PacketType, recv_packet, send_packet


@dataclass
class ClientConnection:
    """Server-side record for one connected client."""

    address: Tuple[str, int]
    socket: socket.socket
    player_id: int
    connected_since: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    display_name: str = "player"

    def send(self, packet: Packet) -> bool:
        """Thread-safe packet write; False on failure."""
        try:
            send_packet(self.socket, packet)
            return True
        except OSError:
            return False


class GameServer:
    """Accepts TCP clients, echoes traffic, and broadcasts snapshots."""

    def __init__(self, host: str = "127.0.0.1", port: int = 0,
                 snapshot_rate_hz: float = 10.0, max_clients: int = 32,
                 verbose: bool = False) -> None:
        self.host: str = host
        self.port: int = port
        self.max_clients: int = max_clients
        self.snapshot_rate_hz: float = snapshot_rate_hz
        self.verbose: bool = verbose
        self.clients: Dict[Tuple[str, int], ClientConnection] = {}
        self.game_state: Dict[str, object] = {}
        self.running: bool = False
        self.next_player_id: int = 1
        self.packets_received: int = 0
        self.on_packet: Optional[Callable[[ClientConnection, Packet], None]] = None
        self._lock = threading.Lock()
        self._listen_socket: Optional[socket.socket] = None
        self._accept_thread: Optional[threading.Thread] = None
        self._snapshot_thread: Optional[threading.Thread] = None

    # -- lifecycle ---------------------------------------------------------------

    def start(self) -> int:
        """Bind, listen, and spawn worker threads; returns the bound port."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.host, self.port))
        sock.listen(8)
        self.port = sock.getsockname()[1]
        self._listen_socket = sock
        self.running = True
        self._accept_thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._accept_thread.start()
        if self.snapshot_rate_hz > 0:
            self._snapshot_thread = threading.Thread(target=self._snapshot_loop, daemon=True)
            self._snapshot_thread.start()
        if self.verbose:
            print(f"[GameServer] listening on {self.host}:{self.port}")
        return self.port

    def stop(self) -> None:
        """Disconnect everyone and close the listener."""
        self.running = False
        with self._lock:
            for client in list(self.clients.values()):
                client.send(Packet(msg_type=PacketType.DISCONNECT))
                try:
                    client.socket.close()
                except OSError:
                    pass
            self.clients.clear()
        if self._listen_socket is not None:
            try:
                self._listen_socket.close()
            except OSError:
                pass

    @property
    def client_count(self) -> int:
        """Live connections right now."""
        with self._lock:
            return len(self.clients)

    # -- worker loops ------------------------------------------------------------------

    def _accept_loop(self) -> None:
        while self.running:
            try:
                conn, addr = self._listen_socket.accept()  # type: ignore[union-attr]
            except OSError:
                break
            with self._lock:
                if len(self.clients) >= self.max_clients:
                    conn.close()
                    continue
                client = ClientConnection(address=addr, socket=conn,
                                          player_id=self.next_player_id)
                self.next_player_id += 1
                self.clients[addr] = client
            send_packet(conn, Packet.from_json(PacketType.WELCOME,
                                               {"player_id": client.player_id}))
            threading.Thread(target=self._client_loop, args=(client,), daemon=True).start()

    def _client_loop(self, client: ClientConnection) -> None:
        while self.running:
            try:
                packet = recv_packet(client.socket)
            except (ConnectionError, OSError):
                break
            if packet is None:
                break
            client.last_seen = time.time()
            self.packets_received += 1
            if self.verbose:
                print(f"[GameServer] {client.address} -> {packet.msg_type.name}")
            if self.on_packet is not None:
                self.on_packet(client, packet)
            if packet.msg_type == PacketType.PING:
                pong = Packet(msg_type=PacketType.PONG, seq=packet.seq,
                              timestamp=packet.timestamp, payload=b"")
                client.send(pong)
            elif packet.msg_type == PacketType.CHAT:
                self.broadcast(packet)
        with self._lock:
            self.clients.pop(client.address, None)
        try:
            client.socket.close()
        except OSError:
            pass

    def _snapshot_loop(self) -> None:
        interval = 1.0 / max(self.snapshot_rate_hz, 1e-6)
        seq = 0
        while self.running:
            time.sleep(interval)
            seq += 1
            self.broadcast_snapshot(seq)

    # -- outbound helpers -------------------------------------------------------------

    def broadcast(self, packet: Packet, exclude: Optional[ClientConnection] = None) -> int:
        """Send *packet* to every client; returns successful deliveries."""
        sent = 0
        with self._lock:
            targets = [c for c in self.clients.values() if c is not exclude]
        for client in targets:
            if client.send(packet):
                sent += 1
        return sent

    def broadcast_snapshot(self, seq: int) -> int:
        """Push current game state as a SNAPSHOT packet."""
        snapshot = Packet.from_json(
            PacketType.SNAPSHOT,
            {"tick": seq, "time": time.time(), "state": dict(self.game_state)},
            seq=seq, compress=True,
        )
        return self.broadcast(snapshot)
