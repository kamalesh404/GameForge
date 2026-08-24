"""Input action mapping with keyboard/mouse state tracking and rebinding."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

MOUSE_LEFT, MOUSE_MIDDLE, MOUSE_RIGHT = 1, 2, 3


@dataclass
class ActionBinding:
    """One logical action mapped to any number of physical inputs."""

    name: str
    keys: Set[int] = field(default_factory=set)
    mouse_buttons: Set[int] = field(default_factory=set)
    deadzone_scale: float = 1.0


class InputManager:
    """Tracks per-frame key/button state and resolves logical actions."""

    def __init__(self) -> None:
        self.pressed: Set[int] = set()
        self.released_this_frame: Set[int] = set()
        self.held_last_frame: Set[int] = set()
        self.mouse_position: Tuple[float, float] = (0.0, 0.0)
        self.mouse_delta: Tuple[float, float] = (0.0, 0.0)
        self.mouse_wheel: float = 0.0
        self.actions: Dict[str, ActionBinding] = {}
        self.text_buffer: List[str] = []
        self.enabled: bool = True

    # -- binding ---------------------------------------------------------------

    def bind_action(self, name: str, keys: Optional[List[int]] = None,
                    mouse_buttons: Optional[List[int]] = None) -> ActionBinding:
        """Create or extend an action mapping; returns the binding."""
        binding = self.actions.get(name)
        if binding is None:
            binding = ActionBinding(name=name)
            self.actions[name] = binding
        binding.keys.update(keys or [])
        binding.mouse_buttons.update(mouse_buttons or [])
        return binding

    def unbind_action(self, name: str) -> bool:
        """Remove an entire action mapping."""
        return self.actions.pop(name, None) is not None

    def rebind_key(self, name: str, old_key: int, new_key: int) -> bool:
        """Swap one physical key inside an existing binding."""
        binding = self.actions.get(name)
        if binding is None or old_key not in binding.keys:
            return False
        binding.keys.discard(old_key)
        binding.keys.add(new_key)
        return True

    def binding_for(self, name: str) -> Optional[ActionBinding]:
        """Fetch a binding without creating one."""
        return self.actions.get(name)

    # -- raw state (called by the platform backend) -------------------------------

    def press(self, code: int) -> None:
        """Mark a key/button as down starting this frame."""
        if not self.enabled:
            return
        if code not in self.pressed:
            self.released_this_frame.discard(code)
            self.pressed.add(code)

    def release(self, code: int) -> None:
        """Mark a key/button as up starting this frame."""
        if code in self.pressed:
            self.pressed.discard(code)
            self.released_this_frame.add(code)

    def set_mouse(self, position: Tuple[float, float], delta: Tuple[float, float]) -> None:
        """Update cursor position and motion delta for this frame."""
        self.mouse_position = position
        self.mouse_delta = delta

    def add_text_input(self, text: str) -> None:
        """Append typed characters consumed by UI text fields."""
        self.text_buffer.append(text)

    def end_frame(self) -> None:
        """Snapshot state so 'just pressed' queries reset next frame."""
        self.held_last_frame = set(self.pressed)
        self.released_this_frame.clear()
        self.mouse_wheel = 0.0
        self.text_buffer.clear()

    # -- queries --------------------------------------------------------------------

    def is_down(self, code: int) -> bool:
        """True while the physical input *code* is held."""
        return self.enabled and code in self.pressed

    def just_pressed(self, code: int) -> bool:
        """True on the single frame a key transitions to down."""
        return self.enabled and code in self.pressed and code not in self.held_last_frame

    def just_released(self, code: int) -> bool:
        """True on the frame a key transitions to up."""
        return self.enabled and code in self.released_this_frame

    def _sources_down(self, binding: ActionBinding) -> bool:
        codes = set(binding.keys) | {10000 + b for b in binding.mouse_buttons}
        return any(c in self.pressed for c in codes)

    def is_action_active(self, name: str) -> bool:
        """True while any input mapped to the action is held."""
        binding = self.actions.get(name)
        return self.enabled and binding is not None and self._sources_down(binding)

    def action_just_pressed(self, name: str) -> bool:
        """Edge-triggered action query."""
        binding = self.actions.get(name)
        if not self.enabled or binding is None:
            return False
        codes = set(binding.keys) | {10000 + b for b in binding.mouse_buttons}
        return any(c in self.pressed and c not in self.held_last_frame for c in codes)

    @staticmethod
    def encode_mouse(button: int) -> int:
        """Map a mouse button into the unified code space."""
        return 10000 + button

    @staticmethod
    def decode_mouse(code: int) -> Optional[int]:
        """Recover a mouse button number from its unified code."""
        return code - 10000 if code >= 10000 else None
