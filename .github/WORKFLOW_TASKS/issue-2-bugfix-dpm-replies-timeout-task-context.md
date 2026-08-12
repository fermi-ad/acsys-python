# Issue 2: [Bugfix] Resolve `RuntimeError('Timeout should be used inside a task')` in `acsys.dpm.replies()` on Python 3.11+

**Status:** Implemented on branch `fix/dpm-replies-task-context`; full pytest suite passes locally. Draft PR pending.

## Summary

Make `acsys.dpm.DPM.replies()` usable when its async generator is driven through an event loop on Python 3.11 and later, without exposing the `asyncio.wait_for()` task-context runtime error.

## Reproduction and current evidence

`tests/test_dpm_task_context.py` reproduces the problem in the RED phase by:

1. Creating a bare `DPM` instance with a stubbed `__anext__`.
2. Creating `replies_gen = dpm.replies(tmo=1.0)`.
3. Driving the async generator once with `.send(None)` while marking a bare event loop as running, without wrapping the generator in an active task.
4. Asserting that Python 3.11+ raises `RuntimeError` matching `Timeout should be used inside a task`.

The GREEN regression test continues the manually driven generator after the fix and verifies that the first yielded object is a task and that the reply is returned successfully.

The relevant implementation is `DPM.replies()` in `acsys/dpm/__init__.py`, where each reply is awaited through `asyncio.wait_for(self.__anext__(), tmo)`.

## Scope

- Diagnose the supported invocation patterns for `DPM.replies()` and the Python 3.11+ `asyncio` requirement involved in the failure.
- Change the implementation and/or surrounding async boundary so the public replies API no longer fails solely because the caller drives the async generator without an existing task.
- Preserve timeout semantics: `tmo` remains the maximum interval between replies and an `asyncio.TimeoutError` remains the expected timeout signal.
- Replace the current regression test's failure expectation with a success/behavioral regression test that covers the supported calling pattern.

## Acceptance criteria

- The reproducer no longer raises `RuntimeError('Timeout should be used inside a task')` on Python 3.11+.
- Iterating `DPM.replies(tmo=...)` from a normal task continues to yield replies as before.
- A timeout between replies still raises `asyncio.TimeoutError` with the documented behavior.
- Cancellation and generator cleanup do not leave pending tasks or unhandled coroutine warnings.
- The regression coverage runs under the repository's supported Python versions, or any version-specific limitation is explicitly documented.
- No unrelated changes to DPM request/reconnection behavior are introduced.

## Verification

- RED phase: the `.send(None)` reproducer failed before the implementation change with `RuntimeError('Timeout should be used inside a task')`.
- GREEN phase: `python -m pytest -q tests/test_dpm_task_context.py -W error::RuntimeWarning` passed.
- Full suite: `python -m pytest -q` passed (`1 passed`).
- Focused regression test passed with runtime warnings treated as errors.
- The fix creates a task for `self.__anext__()` and a task for the `asyncio.wait_for()` coroutine, keeping Python 3.11+ timeout context execution inside a task.

## Dependencies and risks

- Issue 1 should establish the pytest/pytest-asyncio configuration before this issue is implemented.
- The exact repair must preserve the caller's event-loop ownership and avoid silently creating a competing loop.
- The test's current bare-object setup bypasses normal `DPM` initialization; implementation should also be validated through the real public setup path where practical.

## Review focus

- Whether the fix addresses the task-context boundary rather than masking the exception.
- Whether timeout, cancellation, and async-generator lifecycle semantics remain correct.
- Whether tests assert observable API behavior instead of depending only on a particular `asyncio` implementation detail.

## Out of scope

- Replacing the synchronization primitives used by `set_many()` (Issue 3).
- General modernization of all `asyncio.get_event_loop()` calls in the package.
