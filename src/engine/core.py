"""Engine core: configuration, event bus, statistics, and the game loop."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Tuple

from src.ecs.world import World
from src.engine.scene import Scene
from src.engine.window import Window, WindowConfig
from src.math.random import lerp

MAX_DELTA: float = 0.25
Handler = Callable[[Any], None]


class EventBus:
    """Synchronous publish/subscribe hub with optional deferred queueing."""

    def __init__(self) -> None:
        self._handlers: Dict[str, List[Handler]] = {}
        self._queue: List[Tuple[str, Any]] = []
        self.deferred: bool = False
        self._next_token: int = 0
        self._token_map: Dict[int, Tuple[str, Handler]] = {}

    def subscribe(self, event_type: str, handler: Handler) -> int:
        """Register *handler* for *event_type* and return a token."""
        token = self._next_token
        self._next_token += 1
        self._handlers.setdefault(event_type, []).append(handler)
        self._token_map[token] = (event_type, handler)
        return token

    def unsubscribe(self, token: int) -> bool:
        """Remove a previously registered handler via its *token*."""
        entry = self._token_map.pop(token, None)
        if entry is None:
            return False
        event_type, handler = entry
        if handler in self._handlers.get(event_type, []):
            self._handlers[event_type].remove(handler)
        return True

    def post(self, event_type: str, data: Any = None) -> None:
        """Dispatch immediately, or enqueue when deferred mode is active."""
        if self.deferred:
            self._queue.append((event_type, data))
            return
        for handler in list(self._handlers.get(event_type, [])):
            handler(data)

    def pump(self) -> int:
        """Flush queued events; returns the number dispatched."""
        pending, self._queue = self._queue, []
        was_deferred, self.deferred = self.deferred, False
        try:
            for event_type, data in pending:
                self.post(event_type, data)
        finally:
            self.deferred = was_deferred
        return len(pending)

    def clear(self) -> None:
        """Drop every subscription and queued event."""
        self._handlers.clear()
        self._queue.clear()
        self._token_map.clear()


@dataclass
class EngineConfig:
    """Top-level engine settings applied at startup."""

    title: str = "GameForge"
    width: int = 1280
    height: int = 720
    target_fps: int = 60
    fixed_timestep: float = 1.0 / 60.0
    headless: bool = True
    vsync: bool = True


@dataclass
class EngineStats:
    """Rolling performance counters updated once per frame."""

    frame_count: int = 0
    fps: float = 0.0
    delta_time: float = 0.0
    uptime_seconds: float = 0.0
    history: List[float] = field(default_factory=list)


class Engine:
    """Owns the window, world, scenes, and the fixed-timestep main loop."""

    def __init__(self, config: EngineConfig | None = None) -> None:
        self.config: EngineConfig = config or EngineConfig()
        self.events: EventBus = EventBus()
        window_cfg = WindowConfig(
            title=self.config.title,
            width=self.config.width,
            height=self.config.height,
            vsync=self.config.vsync,
            headless=self.config.headless,
        )
        self.window: Window = Window(window_cfg)
        self.world: World = World()
        self.scene: Scene = Scene("main")
        self.stats: EngineStats = EngineStats()
        self.running: bool = False
        self.max_frames: int | None = None
        self._last_time: float = 0.0
        self._accumulator: float = 0.0
        self._start_time: float = 0.0

    # -- lifecycle -----------------------------------------------------------

    def initialize(self) -> None:
        """Open the window and stamp the loop's starting clock."""
        self.window.open()
        self._last_time = time.perf_counter()
        self._start_time = self._last_time
        self.events.post("engine_initialized", {"title": self.window.title})

    def shutdown(self) -> None:
        """Close the window, stop the loop, and emit a shutdown event."""
        self.running = False
        self.window.close()
        self.events.post("engine_shutdown", {"frames": self.stats.frame_count})

    def quit(self) -> None:
        """Request the loop to exit after the current frame."""
        self.running = False

    # -- per-frame work --------------------------------------------------------

    def tick(self) -> float:
        """Run one frame; returns the raw delta time used."""
        now = time.perf_counter()
        raw_delta = now - self._last_time
        self._last_time = now
        delta = min(raw_delta, MAX_DELTA)

        for _event_kind, payload in self.window.poll_events():
            if _event_kind == "quit":
                self.quit()

        self._accumulator += delta
        while self._accumulator >= self.config.fixed_timestep:
            self.world.fixed_update(self.config.fixed_timestep)
            self._accumulator -= self.config.fixed_timestep

        self.world.update(delta)
        self.scene.propagate()
        self.world.render()
        self.events.pump()

        self.stats.frame_count += 1
        self.stats.delta_time = delta
        self.stats.uptime_seconds = now - self._start_time
        instant = 1.0 / delta if delta > 0 else 0.0
        self.stats.fps = lerp(instant, self.stats.fps or instant, 0.95)
        self.stats.history.append(delta)
        if len(self.stats.history) > 240:
            self.stats.history.pop(0)
        return delta

    def run(self, max_frames: int | None = None) -> None:
        """Block running frames until quit, close, or *max_frames* reached."""
        self.initialize()
        self.running = True
        self.max_frames = max_frames
        try:
            while self.running and not self.window.should_close:
                self.tick()
                if max_frames is not None and self.stats.frame_count >= max_frames:
                    break
        finally:
            self.shutdown()
