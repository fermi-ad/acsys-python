import asyncio
import pytest
import acsys.dpm


def _new_loop():
    """Create a test loop without leaking the loop created during import."""
    try:
        current_loop = asyncio.get_event_loop()
    except RuntimeError:
        current_loop = None
    if current_loop is not None and not current_loop.is_running():
        current_loop.close()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return loop


def _drive_once_without_task(coro, loop):
    """Advance a coroutine once without wrapping it in an asyncio.Task."""
    asyncio.events._set_running_loop(loop)
    try:
        return coro.send(None)
    finally:
        asyncio.events._set_running_loop(None)


def _close_loop(loop):
    pending = asyncio.all_tasks(loop)
    for task in pending:
        task.cancel()
    if pending:
        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
    asyncio.set_event_loop(None)
    loop.close()


def test_dpm_replies_timeout_uses_task_context():
    """DPM.replies() can start without an existing asyncio.Task."""
    dpm = object.__new__(acsys.dpm.DPM)

    async def dummy_anext():
        await asyncio.sleep(0.01)
        return "data"

    dpm.__anext__ = dummy_anext
    loop = _new_loop()
    coro = dpm.replies(tmo=1.0).__anext__()

    try:
        timeout_task = _drive_once_without_task(coro, loop)
        assert isinstance(timeout_task, asyncio.Task)
        assert loop.run_until_complete(timeout_task) == "data"
        with pytest.raises(StopIteration) as stopped:
            coro.send(None)
        assert stopped.value.value == "data"
    finally:
        coro.close()
        _close_loop(loop)
