---
name: Bug report
about: Report a defect in GameForge
title: "[bug] "
labels: bug
assignees: ""
---

**Describe the bug**
A clear and concise description of what went wrong.

**To Reproduce**
Minimal code or steps to reproduce:

```python
from src.engine.core import Engine, EngineConfig
# ... minimal repro
```

**Expected behavior**
What you expected to happen instead.

**Environment (please complete):**
- GameForge version: [output of `python -c "import src; print(src.version_info())"`]
- Python version: [e.g. 3.12.4]
- OS: [e.g. Windows 11 / Ubuntu 24.04 / macOS 14]
- Subsystem: [engine / ecs / renderer / physics / audio / input / ui / network]

**Logs / stack trace**

```
paste traceback here
```

**Additional context**
Anything else that may help diagnose the issue (headless vs windowed,
deterministic seed values, network conditions...).
