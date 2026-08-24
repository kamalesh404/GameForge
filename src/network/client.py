"""Game client: connection handling, snapshot interpolation, prediction."""

from __future__ import annotations

import queue
import socket
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

from src.network.packet import Packet, PacketType, recv_packet, send_packet


@dataclass
class Snapshot:
    """Authoritative world state broadcast by the server."""

    tick: int
    server_time: float
    positions: Dict[int, Tuple[float, float]] = field(default_factory=dict)


@dataclass
class LocalInput:
    """Client frame input used for prediction and server reconciliation."""

    move_x: float = 0.0
    move_y: float = 0.0
    seq: int = 0

    def as_dict(self) -> Dict[str, float]:
        """Serialize for the INPUT packet payload."""
        return {"x": self.move_x, "y": self.move_y, "seq": self.seq}


class GameClient:
    """Connects to a :class:`~src.network.server.GameServer` over TCP."""

    INTERP_DELAY_MS: float = 100.0
    RECONCILE_THRESHOLD: float = 48.0

    def __init__(self) -> None:
        self.socket: Optional[socket.socket] = None
        self.connected: bool = False
        self.player_id: int = -1
        self.seq: int = 0
        self.packets_sent: int = 0
        self.packets_received: int = 0
        self.inbox: "queue.Queue[Packet]" = queue.Queue()
        self.snapshot_buffer: list[Snapshot] = []
        self.local_position: Tuple[float, float] = (0.0, 0.0)
        self._rx_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    # -- connection -----------------------------------------------------------------

    def connect(self, host: str = "127.0.0.1", port: int = 7777,
                timeout: float = 3.0) -> bool:
        """Open the socket and wait briefly for a WELCOME reply."""
        try:
            sock = socket.create_connection((host, port), timeout=timeout)
        except OSError:
            return False
        sock.settimeout(timeout)
        self.socket = sock
        hello = Packet.from_json(PacketType.HELLO, {"name": "client"})
        send_packet(sock, hello)
        welcome = recv_packet(sock)
        if welcome is None or welcome.msg_type is not PacketType.WELCOME:
            sock.close()
            return False
        self.player_id = welcome.to_json().get("player_id", -1)
        self.connected = True
        self._rx_thread = threading.Thread(target=self._receive_loop, daemon=True)
        self._rx_thread.start()
        return True

    def disconnect(self) -> None:
        """Politely leave and close the socket."""
        if not self.connected:
            return
        bye = Packet(msg_type=PacketType.DISCONNECT, seq=self._next_seq())
        try:
            if self.socket is not None:
                send_packet(self.socket, bye)
        except OSError:
            pass
        self.connected = False
        if self.socket is not None:
            try:
                self.socket.close()
            except OSError:
                pass

    def _next_seq(self) -> int:
        self.seq += 1
        return self.seq

    # -- receive path --------------------------------------------------------------------

    def _receive_loop(self) -> None:
        while self.connected:
            try:
                packet = recv_packet(self.socket)  # type: ignore[arg-type]
            except (ConnectionError, OSError):
                break
            if packet is None:
                break
            self.packets_received += 1
            if packet.msg_type is PacketType.SNAPSHOT:
                data = packet.to_json()
                snap = Snapshot(tick=int(data.get("tick", 0)),
                                server_time=float(data.get("time", 0.0)))
                state = data.get("state", {})
                snap.positions = {int(k): tuple(v)  # type: ignore[misc]
                                  for k, v in state.items()}
                with self._lock:
                    self.snapshot_buffer.append(snap)
                    if len(self.snapshot_buffer) > 32:
                        self.snapshot_buffer.pop(0)
            elif packet.msg_type is PacketType.DISCONNECT:
                break
            else:
                self.inbox.put(packet)

    def poll_message(self, timeout: float = 0.5) -> Optional[Packet]:
        """Pop the next non-snapshot packet, waiting up to *timeout*."""
        try:
            return self.inbox.get(timeout=timeout)
        except queue.Empty:
            return None

    # -- outbound --------------------------------------------------------------------------

    def send_chat(self, text: str) -> bool:
        """Send a CHAT message; returns success."""
        if not self.connected:
            return False
        pkt = Packet.from_json(PacketType.CHAT, {"text": text}, seq=self._next_seq())
        assert self.socket is not None
        send_packet(self.socket, pkt)
        self.packets_sent += 1
        return True

    def send_input(self, move_x: float, move_y: float) -> LocalInput:
        """Transmit an INPUT frame and apply local prediction."""
        inp = LocalInput(move_x=move_x, move_y=move_y, seq=self._next_seq())
        if self.connected and self.socket is not None:
            pkt = Packet.from_json(PacketType.INPUT, inp.as_dict(), seq=inp.seq)
            try:
                send_packet(self.socket, pkt)
                self.packets_sent += 1
            except OSError:
                pass
        self.predict(inp)
        return inp

    # -- interpolation & prediction ---------------------------------------------------------------

    def latest_snapshots(self) -> Tuple[Optional[Snapshot], Optional[Snapshot]]:
        """Two snapshots bracketing the render time (delay behind newest)."""
        with self._lock:
            if len(self.snapshot_buffer) < 2:
                return None, None
            target_time = self.snapshot_buffer[-1].server_time - (self.INTERP_DELAY_MS / 1000.0)
            older = None
            for snap in self.snapshot_buffer:
                if snap.server_time <= target_time:
                    older = snap
            newer_idx = self.snapshot_buffer.index(older) + 1 if older else 0
            newer = self.snapshot_buffer[newer_idx] if newer_idx < len(self.snapshot_buffer) else None
            return older, newer

    def interpolated_position(self, entity_id: int) -> Optional[Tuple[float, float]]:
        """Smoothed position of *entity_id* between buffered snapshots."""
        older, newer = self.latest_snapshots()
        if older is None or newer is None:
            return None
        span = newer.server_time - older.server_time
        t = 0.0 if span <= 0 else min(max((time.time() - span - older.server_time) / span, 0.0), 1.0)
        pa, pb = older.positions.get(entity_id), newer.positions.get(entity_id)
        if pa is None or pb is None:
            return pb or pa
        return (pa[0] + (pb[0] - pa[0]) * t, pa[1] + (pb[1] - pa[1]) * t)

    def predict(self, inp: LocalInput, speed: float = 220.0) -> Tuple[float, float]:
        """Move the locally-controlled avatar immediately."""
        x = self.local_position[0] + inp.move_x * speed * 0.016
        y = self.local_position[1] + inp.move_y * speed * 0.016
        self.local_position = (x, y)
        return self.local_position

    def reconcile(self, server_position: Tuple[float, float]) -> bool:
        """Snap when drift exceeds tolerance; returns True if corrected."""
        dx = server_position[0] - self.local_position[0]
        dy = server_position[1] - self.local_position[1]
        if (dx * dx + dy * dy) ** 0.5 > GameClient.RECONCILE_THRESHOLD:
            self.local_position = server_position
            return True
        return False
