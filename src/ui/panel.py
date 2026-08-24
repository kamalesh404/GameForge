"""Container panel widget with background, border, padding, and children."""

from __future__ import annotations

from typing import List, Optional, Tuple

from src.ui.widget import Rect, Widget


class Panel(Widget):
    """Rectangular container that lays out and clips child widgets."""

    def __init__(self, name: str, x: float = 0.0, y: float = 0.0,
                 width: float = 320.0, height: float = 240.0) -> None:
        super().__init__(name=name, rect=Rect(x=x, y=y, width=width, height=height))
        self.children: List[Widget] = []
        self.background_color: Tuple[int, int, int, int] = (28, 30, 40, 235)
        self.border_color: Tuple[int, int, int, int] = (90, 100, 130, 255)
        self.border_width: float = 1.0
        self.padding: float = 8.0
        self.clip_children: bool = True
        self.scroll_offset: float = 0.0

    # -- child management -----------------------------------------------------------

    def add_child(self, widget: Widget) -> Widget:
        """Attach a child widget positioned relative to this panel."""
        if widget.parent is not None and hasattr(widget.parent, "remove_child"):
            widget.parent.remove_child(widget)  # type: ignore[attr-defined]
        widget.parent = self
        self.children.append(widget)
        return widget

    def remove_child(self, widget: Widget) -> bool:
        """Detach *widget*; returns True when it was present."""
        if widget in self.children:
            widget.parent = None
            self.children.remove(widget)
            return True
        return False

    def child_by_name(self, name: str) -> Optional[Widget]:
        """Direct child lookup by name."""
        for child in self.children:
            if child.name == name:
                return child
        return None

    @property
    def content_rect(self) -> Rect:
        """Inner area remaining after padding is applied."""
        p = self.padding
        return Rect(x=p, y=p,
                    width=max(self.rect.width - 2 * p, 0.0),
                    height=max(self.rect.height - 2 * p, 0.0))

    # -- layout ------------------------------------------------------------------------

    def stack_vertical(self, gap: float = 4.0) -> None:
        """Flow visible children top-to-bottom inside the padded area."""
        area = self.content_rect
        cursor_y = area.y - self.scroll_offset
        for child in self.children:
            if not child.visible:
                continue
            child.rect.x = area.x
            child.rect.y = cursor_y
            cursor_y += child.rect.height + gap

    def stack_horizontal(self, gap: float = 4.0) -> None:
        """Flow visible children left-to-right inside the padded area."""
        area = self.content_rect
        cursor_x = area.x - self.scroll_offset
        for child in self.children:
            if not child.visible:
                continue
            child.rect.x = cursor_x
            child.rect.y = area.y
            cursor_x += child.rect.width + gap

    def fit_content_height(self, gap: float = 4.0) -> float:
        """Grow the panel height to contain stacked children; returns new h."""
        total = self.padding * 2.0
        visible = [c for c in self.children if c.visible]
        total += sum(c.rect.height for c in visible)
        total += gap * max(len(visible) - 1, 0)
        self.rect.height = max(total, self.rect.height * 0.5)
        return self.rect.height

    # -- interaction -----------------------------------------------------------------------

    def hit_test(self, px: float, py: float) -> bool:
        """Panels absorb hits anywhere over their surface."""
        return super().hit_test(px, py)

    def update(self, dt: float) -> None:
        """Tick every visible child."""
        for child in self.children:
            if child.visible:
                child.update(dt)

    def walk_visible(self) -> List[Widget]:
        """Depth-first list of visible widgets including nested panels."""
        found: List[Widget] = []
        for child in self.children:
            if not child.visible:
                continue
            found.append(child)
            if isinstance(child, Panel):
                found.extend(child.walk_visible())
        return found
