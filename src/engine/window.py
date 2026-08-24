"""Window management: resolution, fullscreen toggling, vsync, close state.

The default implementation is headless so the engine can run in CI and unit
tests without a display server. A pygame/SDL backend only needs to override
:meth:`Window.open`, :meth:`Window.poll_events`, and :meth:`Window.close`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Tuple


@dataclass
class DisplayMode:
    """A supported fullscreen resolution."""

    width: int
    height: int
    refresh_rate: int = 60


@dataclass
class WindowConfig:
    """Initial settings used when opening a window."""

    title: str = "GameForge"
    width: int = 1280
    height: int = 720
    vsync: bool = True
    fullscreen: bool = False
    resizable: bool = True
    headless: bool = True
    icon_path: str | None = None
    user_data: Dict[str, Any] = field(default_factory=dict)


ResizeCallback = Callable[[int, int], None]


class Window:
    """Manages OS window state and surface size independent of any backend."""

    def __init__(self, config: WindowConfig | None = None) -> None:
        self.config = config or WindowConfig()
        self.width: int = self.config.width
        self.height: int = self.config.height
        self.is_open: bool = False
        self.should_close: bool = False
        self.fullscreen: bool = self.config.fullscreen
        self.vsync: bool = self.config.vsync
        self.title: str = self.config.title
        self.display_modes: List[DisplayMode] = [
            DisplayMode(1920, 1080, 144),
            DisplayMode(1280, 720, 60),
            DisplayMode(800, 600, 60),
        ]
        self._resize_callbacks: List[ResizeCallback] = []

    # -- lifecycle -----------------------------------------------------------

    def open(self) -> bool:
        """Create the native window (no-op when headless). Returns success."""
        if self.is_open:
            return True
        self.is_open = True
        self.should_close = False
        return True

    def close(self) -> None:
        """Destroy the native window and mark it closed."""
        self.is_open = False
        self.should_close = False

    def poll_events(self) -> List[Tuple[str, Any]]:
        """Pump the OS event queue; returns events drained this frame."""
        if not self.is_open:
            return []
        return []  # backends append ("quit", None), ("key", code), ...

    def request_close(self) -> None:
        """Flag the window to close on the next poll."""
        self.should_close = True

    # -- configuration ---------------------------------------------------------

    def set_title(self, title: str) -> None:
        """Update the window title bar text."""
        self.title = title
        self.config.title = title

    def resize(self, width: int, height: int) -> None:
        """Resize the client area and notify listeners."""
        if width <= 0 or height <= 0:
            raise ValueError("window dimensions must be positive")
        self.width, self.height = width, height
        self.config.width, self.config.height = width, height
        for callback in list(self._resize_callbacks):
            callback(width, height)

    def toggle_fullscreen(self) -> bool:
        """Switch between windowed and fullscreen modes; returns new state."""
        self.fullscreen = not self.fullscreen
        mode = next(
            (m for m in self.display_modes if (m.width, m.height) == (self.width, self.height)),
            None,
        )
        if self.fullscreen and mode is None and self.display_modes:
            best = max(self.display_modes, key=lambda m: m.width * m.height)
            self.resize(best.width, best.height)
        return self.fullscreen

    def enable_vsync(self, enabled: bool) -> None:
        """Enable or disable vertical sync for the swap chain."""
        self.vsync = enabled
        self.config.vsync = enabled

    def add_resize_callback(self, callback: ResizeCallback) -> None:
        """Register *callback* to fire whenever the window resizes."""
        self._resize_callbacks.append(callback)

    @property
    def aspect_ratio(self) -> float:
        """Current width divided by height."""
        return self.width / self.height if self.height else 1.0
