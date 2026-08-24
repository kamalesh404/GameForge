# Contributing to GameForge

Thanks for helping build GameForge! This document covers workflow, style, and
review expectations.

## Development Setup

```bash
git clone https://github.com/gameforge/gameforge.git
cd gameforge
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
make test          # sanity check
```

## Branching & Commits

- Branch from `main`: `feat/short-description`, `fix/issue-123`,
  `docs/topic`.
- Use [Conventional Commits](https://www.conventionalcommits.org/):
  - `feat(physics): add prismatic joint limits`
  - `fix(renderer): correct screen_to_world y-flip`
  - `docs: expand networking guide`
- Keep commits atomic; rebase instead of merging long-lived branches.

## Pull Request Checklist

1. Tests cover the change (`pytest` passes locally).
2. `make lint` and `make typecheck` are clean.
3. Public API changes update `docs/api_reference.md` and docstrings.
4. New subsystems include a short section in `docs/architecture.md`.
5. The PR description explains *why*, links related issues, and notes any
   breaking changes.

## Code Style

- **Formatter**: black (line length 100) — run `make format`.
- **Imports**: isort with the black profile.
- **Typing**: full annotations; mypy runs on `src/` in CI.
- **Docstrings**: Google style; every public class/function documents args,
  returns, and raises.
- No comments explaining *what* — code should say that; comment only *why*.

## Testing Guidelines

| Area        | File                  | Notes                                   |
|-------------|-----------------------|-----------------------------------------|
| Engine loop | `tests/test_engine.py`| Frame counting, event bus, window state |
| ECS         | `tests/test_ecs.py`   | Queries, ordering, lifecycle callbacks  |
| Physics     | `tests/test_physics.py` | Shapes, solver, joints, quadtree      |
| Renderer    | `tests/test_renderer.py` | Camera math, batching, animation     |
| Network     | `tests/test_network.py` | Real sockets on ephemeral ports       |

Network tests are tagged `@pytest.mark.network`; keep them hermetic (port 0,
bounded waits) so they never flake CI.

## Reporting Bugs

Open an issue using the bug template. Include engine version
(`python -c "import src; print(src.version_info())"`), OS, minimal repro, and
expected vs actual behaviour.

## Proposing Features

Start with a discussion issue describing the gameplay problem before code.
Larger features need a short design note under `docs/` linked from the PR.

## Review Process

- At least one maintainer approval required.
- CI must be green: lint, typecheck, tests (Python 3.10–3.12), wheel build.
- Reviewers aim to respond within two business days.

## License

By contributing you agree your work is released under the project's MIT
License.
