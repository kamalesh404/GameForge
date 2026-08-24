"""UI widget base class: geometry, visibility, focus, and event hooks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class Rect:
    """Screen-space rectangle with hit testing and containment helpers."""

    x: float = 0.0
    y: float = 0.0
    width: float = 100.0
    height: float = 40.0

    def contains(self, px: float, py: float) -> bool:
        """True when the point lies inside this rect."""
        return (self.x <= px < self.x + self.width) and (self.y <= py < self.y + self.height)

    def intersects(self, other: "Rect") -> bool:
        """AABB overlap test against another rect."""
        return not (other.x >= self.x + self.width or other.x + other.width <= self.x
                    or other.y >= self.y + self.height or other.y + other.height <= self.y)

    @property
    def center(self) -> Tuple[float, float]:
        """Midpoint coordinates."""
        return (self.x + self.width * 0.5, self.y + self.height * 0.5)

    def inflate(self, dx: float, dy: float) -> "Rect":
        """Return a copy expanded by (dx, dy) total on each axis."""
        return Rect(self.x - dx * 0.5, self.y - dy * 0.5,
                    self.width + dx, self.height + dy)


class Widget:
    """Retained-mode control participating in layout, focus, and drawing."""

    def __init__(self, name: str, rect: Optional[Rect] = None) -> None:
        self.name: str = name
        self.rect: Rect = rect or Rect()
        self.visible: bool = True
        self.enabled: bool = True
        self.focusable: bool = False
        self.focused: bool = False
        self.hovered: bool = False
        self.tooltip: str = ""
        self.tags: List[str] = []
        self.parent: Optional["Widget"] = None
        self._focus_callback = None

    def set_focus_callback(self, callback) -> None:
        """Register an observer fired on focus gain/loss."""
        self._focus_callback = callback

    # -- hierarchy --------------------------------------------------------------

    def screen_offset(self) -> Tuple[float, float]:
        """Accumulated offset from ancestor widgets."""
        ox, oy = 0.0, 0.0
        node = self.parent
        while node is not None:
            ox += node.rect.x
            oy += node.rect.y
            node = node.parent
        return (ox, oy)

    def hit_test(self, px: float, py: float) -> bool:
        """Point-in-widget test honoring visibility/enabled state."""
        if not (self.visible and self.enabled):
            return False
        ox, oy = self.screen_offset()
        return self.rect.contains(px - ox, py - oy)

    # -- focus ----------------------------------------------------------------------

    def can_focus(self) -> bool:
        """Eligibility for keyboard focus."""
        return self.focusable and self.visible and self.enabled

    def gain_focus(self) -> bool:
        """Acquire focus; returns False when not focusable."""
        if not self.can_focus():
            return False
        self.focused = True
        callback = getattr(self, "on_focus", None)
        if callable(callback):
            callback()
        return True

    def lose_focus(self) -> None:
        """Release keyboard focus."""
        was_focused = self.focused
        self.focused = False
        if was_focused:
            callback = getattr(self, "on_blur", None)
            if callable(callback):
                callback()

    # -- per-frame hooks ---------------------------------------------------------------

    def on_hover_start(self) -> None:
        """Called when the pointer enters the widget bounds."""

    def on_hover_end(self) -> None:
        """Called when the pointer leaves the widget bounds."""

    def update(self, dt: float) -> None:
        """Animate or refresh widget-local state."""

    def measure(self) -> Tuple[float, float]:
        """Preferred size; defaults to current rect dimensions."""
        return (self.rect.width, self.rect.height)

    def __repr__(self) -> str:
        state = "visible" if self.visible else "hidden"
        return f"<{type(self).__name__} {self.name!r} {state}>"
