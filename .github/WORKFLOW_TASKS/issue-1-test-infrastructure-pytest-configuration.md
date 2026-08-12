# Issue 1: [Test Infrastructure] Configure pytest and pytest-asyncio in `pyproject.toml`

**Status:** Implemented on branch `chore/configure-pytest`. Configuration and installation checks pass; full-suite verification remains blocked by the pre-existing Issue 2 regression test. No Issue 2 code changes were made, and work stops here pending Issue 2 approval.

## Summary

Move the test-runner configuration and async test dependency into the project metadata so local development and CI use the same declared setup.

## Context

- `pyproject.toml` currently declares only `build`, `wheel`, and `setuptools`-related development tooling; it does not declare `pytest` or `pytest-asyncio`.
- The GitHub Actions workflow installs `pytest` and `flake8` directly in `.github/workflows/python-package.yml`.
- `tests/test_dpm_task_context.py` imports `pytest` and exercises asyncio behavior, but is currently written around a manually managed event loop rather than `pytest-asyncio` fixtures/markers.
- The package supports Python `>=3.9.21`, while CI also lists Python 3.8; the supported-version policy and compatible `pytest-asyncio` range should be respected rather than assumed.

## Scope

- Add the required test dependencies and pytest configuration in `pyproject.toml`.
- Decide and document the appropriate `pytest-asyncio` mode and async-test conventions for this repository.
- Align CI installation with the declared development/test dependencies where appropriate.
- Do not change production behavior as part of this issue.

## Acceptance criteria

- A clean development environment can install the declared test tooling from the project configuration.
- `pytest` discovers and runs the repository test suite without requiring ad hoc test-runner installation beyond the documented development install.
- Async tests have an explicit, consistent configuration and do not depend on implicit event-loop behavior.
- CI continues to run the test suite across the supported Python versions, with dependency compatibility verified.
- The resulting configuration is documented sufficiently for contributors to run the same checks locally.

## Verification

- Clean virtual environment: `pip install -e ".[dev]"` succeeded and installed `pytest`, `pytest-asyncio`, `build`, and `wheel` from the project metadata.
- Async configuration smoke test: passed with `asyncio_mode = "auto"`.
- Pytest collection: passed (`1 test collected`).
- Full `python -m pytest -q`: blocked by the existing `tests/test_dpm_task_context.py` expectation; it fails because the test does not raise the Issue 2 `RuntimeError` under the current Python 3.13 runtime.
- Python 3.8 and 3.9 dependency resolution: passed using compatible `pytest`/`pytest-asyncio` releases.
- Wheel build: passed after installing the declared build backend dependencies; only pre-existing setuptools license deprecation warnings were emitted.
- No production package dependency was added solely for test infrastructure.

## Dependencies and risks

- This issue should be completed before relying on `pytest-asyncio`-specific tests for Issues 2 or 3.
- `pytest-asyncio` compatibility with the repository's Python-version matrix must be checked before selecting a version constraint.
- CI currently uses `continue-on-error: true` for pytest; whether that policy should change is an explicit follow-up decision, not an assumed part of this issue.

## Review focus

- Whether the dependency belongs in the existing `dev` optional-dependency group or a newly named test group.
- Whether the chosen async mode and event-loop scope are explicit and compatible with the test suite.
- Whether local and CI installation paths remain consistent.

## Out of scope

- Fixing the `DPM.replies()` timeout failure (Issue 2).
- Refactoring `set_many()` synchronization (Issue 3).
