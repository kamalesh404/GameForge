"""Interactive button widget with hover/press states and click callbacks."""

from __future__ import annotations

import enum
from typing import Callable, List, Optional

from src.ui.label import Label, TextStyle
from src.ui.widget import Rect, Widget


class ButtonState(enum.Enum):
    """Visual state machine driving button rendering."""

    NORMAL = "normal"
    HOVERED = "hovered"
    PRESSED = "pressed"
    DISABLED = "disabled"


class Button(Widget):
    """Clickable control firing callbacks on press-release inside bounds."""

    def __init__(self, name: str, text: str = "Button",
                 x: float = 0.0, y: float = 0.0,
                 width: float = 140.0, height: float = 40.0) -> None:
        super().__init__(name=name, rect=Rect(x=x, y=y, width=width, height=height))
        self.focusable: bool = True
        self.state: ButtonState = ButtonState.NORMAL
        self.label: Label = Label(f"{name}:label", text=text)
        self.label.style = TextStyle(bold=True)
        self.click_callbacks: List[Callable[["Button"], None]] = []
        self.press_callbacks: List[Callable[["Button"], None]] = []
        self._mouse_down_inside: bool = False
        self.hotkey_code: Optional[int] = None

    # -- configuration -----------------------------------------------------------

    def set_text(self, text: str) -> None:
        """Update the caption text."""
        self.label.set_text(text)

    @property
    def text(self) -> str:
        """Current caption."""
        return self.label.text

    def on_click(self, callback: Callable[["Button"], None]) -> None:
        """Register a click handler (chainable style)."""
        self.click_callbacks.append(callback)

    def on_press(self, callback: Callable[["Button"], None]) -> None:
        """Register a handler fired the moment the button is pressed."""
        self.press_callbacks.append(callback)

    def bind_hotkey(self, code: int) -> None:
        """Trigger this button from a keyboard code."""
        self.hotkey_code = code

    # -- interaction -----------------------------------------------------------------

    def handle_mouse_down(self, px: float, py: float) -> bool:
        """Begin a press when *px/py* lands on the button."""
        if not self.hit_test(px, py) or not self.enabled:
            return False
        self._mouse_down_inside = True
        self.state = ButtonState.PRESSED
        for cb in list(self.press_callbacks):
            cb(self)
        return True

    def handle_mouse_up(self, px: float, py: float) -> bool:
        """Complete a click if released over the same widget."""
        was_pressed = self._mouse_down_inside
        self._mouse_down_inside = False
        self.state = ButtonState.HOVERED if self.hovered else ButtonState.NORMAL
        if not (was_pressed and self.hit_test(px, py)):
            return False
        for cb in list(self.click_callbacks):
            cb(self)
        return True

    def handle_mouse_move(self, px: float, py: float) -> bool:
        """Refresh hover state; cancels clicks that slide off-widget."""
        now_hovered = self.hit_test(px, py)
        if now_hovered != self.hovered:
            self.hovered = now_hovered
            if self.state is not ButtonState.PRESSED or not now_hovered:
                if self._mouse_down_inside and not now_hovered:
                    self._mouse_down_inside = False
                self.state = (ButtonState.PRESSED if self._mouse_down_inside
                              else ButtonState.HOVERED if now_hovered else ButtonState.NORMAL)
            if now_hovered:
                self.on_hover_start()
            else:
                self.on_hover_end()
        return now_hovered

    def activate_from_keyboard(self) -> bool:
        """Space/Enter equivalent used during focus traversal."""
        if not (self.enabled and self.visible):
            return False
        for cb in list(self.click_callbacks):
            cb(self)
        return True

    # -- state helpers ---------------------------------------------------------------

    def set_enabled(self, enabled: bool) -> None:
        """Enable/disable, forcing state back to normal."""
        self.enabled = enabled
        self.state = ButtonState.NORMAL if enabled else ButtonState.DISABLED

    def current_state(self) -> ButtonState:
        """Effective visual state honoring disabled flag."""
        if not self.enabled:
            return ButtonState.DISABLED
        return self.state

    def update(self, dt: float) -> None:
        """Per-frame hook kept for parity with the widget contract."""
