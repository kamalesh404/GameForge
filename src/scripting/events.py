"""Script-facing event system with a bounded, drainable event queue."""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Deque, Dict, List

MAX_QUEUE_DEPTH: int = 1024


@dataclass(frozen=True)
class ScriptEvent:
    """Immutable message delivered to gameplay scripts."""

    name: str
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0
    source: str = "engine"

    def get(self, key: str, default: Any = None) -> Any:
        """Convenience accessor into the payload dict."""
        return self.payload.get(key, default)


EventHandler = Callable[[ScriptEvent], None]


class ScriptEventQueue:
    """Bounded FIFO queue plus subscription registry for script hooks."""

    def __init__(self, capacity: int = MAX_QUEUE_DEPTH) -> None:
        self.capacity: int = capacity
        self._queue: Deque[ScriptEvent] = deque()
        self._handlers: Dict[str, List[EventHandler]] = {}
        self._wildcards: List[EventHandler] = []
        self.dropped_count: int = 0
        self.processed_count: int = 0

    def subscribe(self, event_name: str, handler: EventHandler) -> None:
        """Register *handler* for a specific event *event_name*."""
        self._handlers.setdefault(event_name, []).append(handler)

    def subscribe_all(self, handler: EventHandler) -> None:
        """Register *handler* to observe every dispatched event."""
        self._wildcards.append(handler)

    def emit(self, name: str, payload: Dict[str, Any] | None = None,
             source: str = "gameplay") -> bool:
        """Enqueue an event; returns False when the queue overflowed."""
        if len(self._queue) >= self.capacity:
            self.dropped_count += 1
            return False
        event = ScriptEvent(name=name, payload=payload or {},
                            timestamp=time.time(), source=source)
        self._queue.append(event)
        return True

    def _dispatch(self, event: ScriptEvent) -> None:
        for handler in list(self._handlers.get(event.name, [])):
            handler(event)
        for observer in list(self._wildcards):
            observer(event)

    def process(self, limit: int = 64) -> int:
        """Dispatch up to *limit* queued events; returns count handled."""
        handled = 0
        while self._queue and handled < limit:
            self._dispatch(self._queue.popleft())
            handled += 1
            self.processed_count += 1
        return handled

    def poll(self) -> ScriptEvent | None:
        """Pop the next raw event without dispatching handlers."""
        return self._queue.popleft() if self._queue else None

    def pending(self) -> int:
        """Number of events waiting in the queue."""
        return len(self._queue)

    def clear(self) -> None:
        """Drop queued events but keep subscriptions intact."""
        self.dropped_count += len(self._queue)
        self._queue.clear()

    def stats(self) -> Dict[str, int]:
        """Snapshot of queue telemetry."""
        return {"pending": self.pending(), "processed": self.processed_count,
                "dropped": self.dropped_count}


class GameplayHooks:
    """Standard event names emitted by engine systems, for reference."""

    ENTITY_SPAWNED = "entity_spawned"
    ENTITY_DESTROYED = "entity_destroyed"
    COLLISION_START = "collision_start"
    DAMAGE_TAKEN = "damage_taken"
    LEVEL_LOADED = "level_loaded"
    PLAYER_DIED = "player_died"

    ALL: List[str] = [ENTITY_SPAWNED, ENTITY_DESTROYED, COLLISION_START,
                      DAMAGE_TAKEN, LEVEL_LOADED, PLAYER_DIED]
