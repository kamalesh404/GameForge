"""Text label widget with fonts, colors, wrapping hints, and alignment."""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Tuple

from src.ui.widget import Rect, Widget


class TextAlignment(enum.Enum):
    """Horizontal text alignment options."""

    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"


@dataclass
class TextStyle:
    """Bundle of typographic properties shared by labels/buttons."""

    font_name: str = "default"
    font_size: int = 16
    bold: bool = False
    italic: bool = False
    color: Tuple[int, int, int, int] = (235, 235, 240, 255)
    shadow_color: Tuple[int, int, int, int] | None = None

    def line_height(self) -> float:
        """Estimated pixel height of one rendered line."""
        return self.font_size * 1.25


def estimate_text_width(text: str, style: TextStyle) -> float:
    """Cheap monospace-ish width approximation for headless layout."""
    factor = 0.62 + (0.06 if style.bold else 0.0)
    return len(text) * style.font_size * factor


class Label(Widget):
    """Static text display supporting alignment and simple word wrap."""

    def __init__(self, name: str, text: str = "",
                 x: float = 0.0, y: float = 0.0,
                 width: float = 200.0, height: float = 24.0) -> None:
        super().__init__(name=name, rect=Rect(x=x, y=y, width=width, height=height))
        self.text: str = text
        self.style: TextStyle = TextStyle()
        self.alignment: TextAlignment = TextAlignment.LEFT
        self.autosize: bool = True
        self.max_width: float = width
        self.opacity: float = 1.0

    # -- content -------------------------------------------------------------------

    def set_text(self, text: str) -> None:
        """Replace displayed text and refresh autosizing."""
        self.text = text
        if self.autosize:
            self.refit()

    def refit(self) -> None:
        """Resize the rect to snugly fit the measured text."""
        measured = estimate_text_width(self.text, self.style)
        lines = max(1, self.line_count())
        self.rect.width = min(measured, max(self.max_width, 1.0)) if self.wrap_enabled() else measured
        self.rect.height = lines * self.style.line_height()

    def wrap_enabled(self) -> bool:
        """Wrapping kicks in when text exceeds max width."""
        return estimate_text_width(self.text, self.style) > self.max_width

    def line_count(self) -> int:
        """Number of wrapped lines required to display the text."""
        if not self.wrap_enabled():
            return 1
        words = self.text.split(" ")
        lines, current = 1, 0.0
        space = estimate_text_width(" ", self.style)
        for word in words:
            w = estimate_text_width(word, self.style)
            if current > 0 and current + space + w > self.max_width:
                lines += 1
                current = w
            else:
                current += (space if current > 0 else 0.0) + w
        return lines

    # -- layout helpers --------------------------------------------------------------

    def aligned_origin(self, container_width: float) -> float:
        """X offset honoring the configured horizontal alignment."""
        text_w = estimate_text_width(self.text, self.style)
        if self.alignment is TextAlignment.LEFT:
            return self.rect.x
        if self.alignment is TextAlignment.CENTER:
            return self.rect.x + (container_width - text_w) * 0.5
        return self.rect.x + max(container_width - text_w, 0.0)

    def fade_to(self, target_opacity: float, speed: float, dt: float) -> bool:
        """Animate opacity toward *target*; returns True when settled."""
        delta = target_opacity - self.opacity
        step = speed * dt
        if abs(delta) <= step:
            self.opacity = target_opacity
            return True
        self.opacity += step if delta > 0 else -step
        return False
