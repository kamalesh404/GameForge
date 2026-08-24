"""UI manager: z-ordered hit testing, event routing, and focus traversal."""

from __future__ import annotations

from typing import List, Optional, Tuple

from src.input.manager import InputManager
from src.ui.button import Button
from src.ui.panel import Panel
from src.ui.widget import Rect, Widget


class UIManager:
    """Root-level coordinator owning widgets and dispatching input events."""

    def __init__(self) -> None:
        self.widgets: List[Widget] = []
        self.focused: Optional[Widget] = None
        self.captured_mouse: Optional[Widget] = None
        self.z_counter: int = 0
        self.modal: Optional[Panel] = None
        self.hit_count_last_frame: int = 0

    # -- registration ------------------------------------------------------------

    def add(self, widget: Widget, focusable_order: bool = True) -> Widget:
        """Register a top-level widget at the front of the z order."""
        widget.tags.append(f"z{self.z_counter}")
        self.z_counter += 1
        self.widgets.append(widget)
        if focusable_order and widget.can_focus() and self.focused is None:
            self.set_focus(widget)
        return widget

    def remove(self, widget: Widget) -> bool:
        """Unregister a widget, clearing focus/capture when needed."""
        if widget in self.widgets:
            self.widgets.remove(widget)
            if self.focused is widget:
                self.focused = None
            if self.captured_mouse is widget:
                self.captured_mouse = None
            return True
        return False

    def ordered_top_first(self) -> List[Widget]:
        """Widgets sorted so later-registered (topmost) come first."""
        return list(reversed(self.widgets))

    # -- focus ----------------------------------------------------------------------

    def set_focus(self, widget: Optional[Widget]) -> bool:
        """Move keyboard focus to *widget*, blurring the previous holder."""
        if widget is not None and not widget.can_focus():
            return False
        if self.focused is widget:
            return True
        if self.focused is not None:
            self.focused.lose_focus()
        self.focused = widget
        if widget is not None:
            widget.gain_focus()
        return True

    def cycle_focus(self) -> Optional[Widget]:
        """Advance focus to the next focusable widget in tab order."""
        candidates = [w for w in self.widgets if w.can_focus()]
        if not candidates:
            return None
        try:
            idx = candidates.index(self.focused)  # type: ignore[arg-type]
        except ValueError:
            idx = -1
        nxt = candidates[(idx + 1) % len(candidates)]
        self.set_focus(nxt)
        return nxt

    # -- mouse routing ------------------------------------------------------------------

    def _hit_topmost(self, px: float, py: float) -> Optional[Widget]:
        for widget in self.ordered_top_first():
            if isinstance(widget, Panel):
                for child in reversed(widget.walk_visible()):
                    if child.hit_test(px, py):
                        return child
            if widget.hit_test(px, py):
                return widget
        return None

    def dispatch_mouse_down(self, px: float, py: float, button: int = 1) -> bool:
        """Route a press; returns True when a widget consumed it."""
        target = self._hit_topmost(px, py)
        self.hit_count_last_frame += 1
        if target is None:
            self.set_focus(None)
            return False
        self.captured_mouse = target
        if isinstance(target, Button):
            target.handle_mouse_down(px, py)
        if target.can_focus():
            self.set_focus(target)
        return True

    def dispatch_mouse_move(self, px: float, py: float) -> bool:
        """Update hover states along the current pointer position."""
        hovered_any = False
        for widget in self.widgets:
            is_over = widget.hit_test(px, py)
            if isinstance(widget, Button):
                widget.handle_mouse_move(px, py)
            elif is_over != widget.hovered:
                widget.hovered = is_over
                if is_over:
                    widget.on_hover_start()
                    hovered_any = True
                else:
                    widget.on_hover_end()
            elif is_over:
                hovered_any = True
        return hovered_any

    def dispatch_mouse_up(self, px: float, py: float, button: int = 1) -> bool:
        """Complete a click on the captured widget."""
        target = self.captured_mouse or self._hit_topmost(px, py)
        self.captured_mouse = None
        if isinstance(target, Button):
            return target.handle_mouse_up(px, py)
        return target is not None

    # -- integration -----------------------------------------------------------------------

    def process_input(self, inputs: InputManager) -> bool:
        """Feed an :class:`InputManager` snapshot through the UI."""
        mx, my = inputs.mouse_position
        self.dispatch_mouse_move(mx, my)
        left_code = InputManager.encode_mouse(1)
        consumed = False
        if inputs.just_pressed(left_code):
            consumed = self.dispatch_mouse_down(mx, my, 1)
        if inputs.just_released(left_code):
            self.dispatch_mouse_up(mx, my, 1)
        tab_pressed = inputs.is_down(9)  # TAB
        if tab_pressed and inputs.just_pressed(9):
            self.cycle_focus()
        return consumed

    def draw_order(self) -> List[Widget]:
        """Bottom-to-top paint order of visible widgets."""
        return [w for w in self.widgets if w.visible]

    def bounds_union(self) -> Rect:
        """Bounding rect covering every registered widget."""
        xs = [(w.rect.x, w.rect.x + w.rect.width) for w in self.widgets]
        ys = [(w.rect.y, w.rect.y + w.rect.height) for w in self.widgets]
        flat_x = [v for pair in xs for v in pair] or [0.0]
        flat_y = [v for pair in ys for v in pair] or [0.0]
        return Rect(min(flat_x), min(flat_y),
                    max(flat_x) - min(flat_x), max(flat_y) - min(flat_y))
