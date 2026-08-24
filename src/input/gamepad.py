"""Gamepad abstraction: axes, radial dead zones, and rumble effects."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple


@dataclass
class RumbleState:
    """Active vibration with decay toward zero intensity."""

    low_frequency: float = 0.0
    high_frequency: float = 0.0
    remaining_seconds: float = 0.0

    @property
    def active(self) -> bool:
        """True while a rumble is still playing."""
        return self.remaining_seconds > 0.0 and (self.low_frequency or self.high_frequency)


class Gamepad:
    """State container for one connected controller."""

    def __init__(self, device_index: int = 0, name: str = "Generic Pad") -> None:
        self.device_index: int = device_index
        self.name: str = name
        self.connected: bool = False
        self.buttons_down: set[int] = set()
        self.buttons_pressed_edge: set[int] = set()
        self.axes: Dict[int, float] = {}
        self.deadzone: float = 0.18
        self.rumble: RumbleState = RumbleState()
        self.last_activity: float = 0.0

    # -- connection -----------------------------------------------------------

    def connect(self) -> None:
        """Mark the pad attached and reset transient state."""
        self.connected = True
        self.buttons_down.clear()
        self.axes.clear()

    def disconnect(self) -> None:
        """Clear all state when the pad is unplugged."""
        self.connected = False
        self.buttons_down.clear()
        self.axes.clear()
        self.rumble = RumbleState()

    def is_connected(self) -> bool:
        """Connection probe used by the input manager."""
        return self.connected

    # -- raw input --------------------------------------------------------------

    def _touch(self) -> None:
        self.last_activity = time.monotonic()

    def press_button(self, button_id: int) -> None:
        """Register a button-down edge."""
        if button_id not in self.buttons_down:
            self.buttons_pressed_edge.add(button_id)
        self.buttons_down.add(button_id)
        self._touch()

    def release_button(self, button_id: int) -> None:
        """Register a button-up transition."""
        self.buttons_down.discard(button_id)

    def set_axis(self, axis_id: int, raw_value: float) -> None:
        """Store a raw analog axis reading in ``[-1, 1]``."""
        clamped = max(-1.0, min(1.0, raw_value))
        if abs(clamped) <= self.deadzone:
            clamped = 0.0
        else:
            # rescale so output spans full range past the dead zone
            sign = 1.0 if clamped > 0 else -1.0
            span = 1.0 - self.deadzone
            clamped = sign * (abs(clamped) - self.deadzone) / span
        self.axes[axis_id] = clamped
        self._touch()

    def apply_radial_deadzone(self, x: float, y: float,
                              zone: Optional[float] = None) -> Tuple[float, float]:
        """Normalize a stick vector so diagonals are not exaggerated."""
        limit = zone if zone is not None else self.deadzone
        magnitude = min((x * x + y * y) ** 0.5, 1.0)
        if magnitude <= limit:
            return (0.0, 0.0)
        scaled = (magnitude - limit) / (1.0 - limit)
        factor = scaled / max(magnitude, 1e-9)
        return (x * factor, y * factor)

    # -- queries -------------------------------------------------------------------

    def get_axis(self, axis_id: int, default: float = 0.0) -> float:
        """Dead-zone-adjusted value for one axis."""
        return self.axes.get(axis_id, default)

    def stick_vector(self) -> Tuple[float, float]:
        """Left stick as an (x, y) tuple after radial correction."""
        x = self.get_axis(0)
        y = self.get_axis(1)
        return self.apply_radial_deadzone(x, y)

    def is_button_down(self, button_id: int) -> bool:
        """Held-state query for *button_id*."""
        return self.connected and button_id in self.buttons_down

    def consume_press(self, button_id: int) -> bool:
        """True once per physical press until the next end_frame()."""
        if button_id in self.buttons_pressed_edge:
            self.buttons_pressed_edge.discard(button_id)
            return True
        return False

    # -- rumble -----------------------------------------------------------------------

    def start_rumble(self, low: float, high: float, duration: float) -> bool:
        """Begin vibration; returns False when unsupported/disconnected."""
        if not self.connected:
            return False
        self.rumble = RumbleState(
            low_frequency=max(0.0, min(low, 1.0)),
            high_frequency=max(0.0, min(high, 1.0)),
            remaining_seconds=max(0.0, duration),
        )
        return True

    def stop_rumble(self) -> None:
        """Silence motors immediately."""
        self.rumble = RumbleState()

    def update(self, dt: float) -> bool:
        """Decay rumble timers; returns True while still vibrating."""
        if self.rumble.active:
            self.rumble.remaining_seconds = max(0.0, self.rumble.remaining_seconds - dt)
            if not self.rumble.active:
                self.rumble = RumbleState()
                return False
            return True
        return False


@dataclass
class GamepadManager:
    """Owns all pads and routes hot-plug events."""

    pads: Dict[int, Gamepad] = field(default_factory=dict)
    default_deadzone: float = 0.18

    def ensure_pad(self, index: int) -> Gamepad:
        """Fetch-or-create a pad slot for *index*."""
        if index not in self.pads:
            pad = Gamepad(device_index=index)
            pad.deadzone = self.default_deadzone
            self.pads[index] = pad
        return self.pads[index]

    def on_connect(self, index: int, name: str = "Pad") -> Gamepad:
        """Handle a controller attach event."""
        pad = self.ensure_pad(index)
        pad.name = name
        pad.connect()
        return pad

    def on_disconnect(self, index: int) -> bool:
        """Handle a controller detach event."""
        pad = self.pads.get(index)
        if pad is None:
            return False
        pad.disconnect()
        return True

    def first_active(self) -> Optional[Gamepad]:
        """First connected pad, or None when only keyboard is available."""
        for pad in self.pads.values():
            if pad.is_connected():
                return pad
        return None

    def update_all(self, dt: float) -> int:
        """Tick every pad; returns count of actively rumbling pads."""
        return sum(1 for pad in self.pads.values() if pad.update(dt))
