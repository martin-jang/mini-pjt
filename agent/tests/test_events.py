import pytest

from legacy2next.events import EventLog, RunEvent
from legacy2next.masking import SecretRegistry


def test_emit_masks_writes_jsonl_and_notifies(tmp_path):
    reg = SecretRegistry()
    reg.register("pw-secret")
    log = EventLog(tmp_path, reg)
    received = []
    unsubscribe = log.subscribe("run-1", received.append)

    log.emit(
        RunEvent(
            run_id="run-1",
            type="log",
            source="explorer",
            message="pw=pw-secret",
            data={"value": "pw-secret"},
        )
    )
    unsubscribe()
    log.emit(RunEvent(run_id="run-1", type="log", source="explorer", message="두 번째"))

    events = log.read("run-1")
    assert [e.message for e in events] == ["pw=***", "두 번째"]
    assert events[0].data == {"value": "***"}
    assert len(received) == 1
    assert "pw-secret" not in (tmp_path / "runs" / "run-1.jsonl").read_text(encoding="utf-8")


@pytest.mark.parametrize("bad", ["../escape", "a/b", "", "."])
def test_run_id_cannot_escape_log_dir(tmp_path, bad):
    log = EventLog(tmp_path)
    with pytest.raises(ValueError):
        log.emit(RunEvent(run_id=bad, type="log", source="system", message="x"))


async def test_queue_receives_events(tmp_path):
    log = EventLog(tmp_path)
    q, unsubscribe = log.queue("run-2")
    log.emit(RunEvent(run_id="run-2", type="status", source="system", message="시작"))
    event = q.get_nowait()
    unsubscribe()
    assert event.message == "시작"
