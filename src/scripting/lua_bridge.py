"""Optional Lua scripting bridge with a graceful headless fallback.

When `lupa` is installed the bridge executes real Lua; otherwise it records
registered functions and script sources so tooling and tests still work.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

try:  # pragma: no cover - depends on optional dependency
    import lupa  # type: ignore

    LUA_AVAILABLE: bool = True
except ImportError:  # pragma: no cover
    lupa = None
    LUA_AVAILABLE = False


@dataclass
class ScriptHandle:
    """Metadata describing one registered gameplay script."""

    name: str
    source: str
    hooks: Dict[str, Callable[..., Any]] = field(default_factory=dict)

    def has_hook(self, hook_name: str) -> bool:
        """True when the script defines *hook_name*."""
        return hook_name in self.hooks


class LuaBridge:
    """Manages a Lua runtime (or stub) plus exported Python callbacks."""

    def __init__(self) -> None:
        self.runtime: Optional[Any] = None
        if LUA_AVAILABLE and lupa is not None:  # pragma: no cover - optional
            try:
                self.runtime = lupa.LuaRuntime(unpack_returned_tuples=True)
            except Exception as exc:  # defensive: broken native builds
                logger.warning("Lua runtime failed to start: %s", exc)
        self.exports: Dict[str, Callable[..., Any]] = {}
        self.scripts: Dict[str, ScriptHandle] = {}
        self.execution_count: int = 0
        self.last_error: Optional[str] = None

    @property
    def available(self) -> bool:
        """Whether real Lua evaluation is possible in this environment."""
        return self.runtime is not None

    def register_function(self, name: str, fn: Callable[..., Any]) -> None:
        """Expose a Python callable to scripts under *name*."""
        self.exports[name] = fn
        if self.runtime is not None:  # pragma: no cover - optional
            try:
                self.runtime.globals()[name] = fn
            except Exception as exc:
                logger.debug("could not export %s to Lua: %s", name, exc)

    def load_script(self, name: str, source: str) -> ScriptHandle:
        """Compile/record a script; returns its :class:`ScriptHandle`."""
        handle = ScriptHandle(name=name, source=source)
        if self.runtime is not None:  # pragma: no cover - optional
            try:
                chunk = self.runtime.execute(f"function() {source} end")
                handle.hooks["main"] = chunk
            except Exception as exc:
                self.last_error = str(exc)
                raise SyntaxError(f"Lua compile error in {name}: {exc}") from exc
        else:
            for line in source.splitlines():
                stripped = line.strip()
                if stripped.startswith("function"):
                    hook_name = stripped.split("(")[0].replace("function ", "")
                    handle.hooks[hook_name] = lambda *a, hn=hook_name: None
        self.scripts[name] = handle
        return handle

    def call(self, script_name: str, hook: str, *args: Any) -> Any:
        """Invoke *hook* on a loaded script with positional *args*."""
        handle = self.scripts.get(script_name)
        if handle is None:
            raise KeyError(f"script {script_name!r} not loaded")
        fn = handle.hooks.get(hook)
        if fn is None:
            return None
        self.execution_count += 1
        try:
            return fn(*args)
        except Exception as exc:
            self.last_error = str(exc)
            logger.exception("script %s.%s raised", script_name, hook)
            return None

    def execute_snippet(self, source: str) -> Any:
        """Run ad-hoc Lua source immediately."""
        self.execution_count += 1
        if self.runtime is None:
            self.last_error = "lua runtime unavailable"
            return None
        try:  # pragma: no cover - optional dependency path
            return self.runtime.execute(source)
        except Exception as exc:
            self.last_error = str(exc)
            return None

    def unload(self, name: str) -> bool:
        """Remove a previously loaded script."""
        return self.scripts.pop(name, None) is not None

    def reset(self) -> None:
        """Drop all scripts, exports, and error state."""
        self.exports.clear()
        self.scripts.clear()
        self.last_error = None
        self.execution_count = 0
