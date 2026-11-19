"""실행 트레이스 (Day 7 TraceCollector 기반).

노드·도구 실행을 TraceCollector 이벤트로 기록하고, 동시에 과제 규약의 trace 항목
({"step","input","output"})을 만듭니다. 단계별 소요 시간(elapsed_ms)을 함께 남겨
'URL → POC 소요 시간' 지표의 근거로 씁니다. 모든 입출력 문자열은 PII 마스킹 후 기록합니다.
"""

from __future__ import annotations

import json
import time
from contextlib import contextmanager
from typing import Any, Callable, Iterator

from src.config import path as cfg_path
from src.guardrails import mask_pii
from src.reuse.day07_trace import TraceCollector

_MAX = 300

# ── 진행 이벤트 리스너 (작업 화면의 단계 도식용) ──
# thread_id 별로 콜백을 등록해 두면 step() 시작·종료 시점에 호출합니다.
# 그래프 상태(trace)는 노드가 끝나야 갱신되므로, 노드 안의 세부 단계 진행을 실시간으로
# 보여 주려면 이 훅이 필요합니다. 리스너 오류는 본 작업을 멈추지 않습니다.
_listeners: dict[str, Callable[[str, str, dict[str, Any]], None]] = {}


def add_listener(thread_id: str, fn: Callable[[str, str, dict[str, Any]], None]) -> None:
    """thread_id 의 진행 이벤트를 받을 콜백 fn(event, step_name, data) 을 등록합니다."""
    _listeners[thread_id] = fn


def remove_listener(thread_id: str) -> None:
    _listeners.pop(thread_id, None)


def emit(thread_id: str | None, event: str, name: str, data: dict[str, Any] | None = None) -> None:
    """등록된 리스너에 진행 이벤트를 보냅니다 (event: start / end / log / stage)."""
    fn = _listeners.get(thread_id or "")
    if fn is None:
        return
    try:
        fn(event, name, data or {})
    except Exception:  # 화면 갱신 실패가 생성 작업을 깨뜨리지 않도록 무시
        pass


def _short(value: Any) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    text = mask_pii(text)
    return text if len(text) <= _MAX else text[:_MAX] + "…"


@contextmanager
def step(trace: list[dict[str, Any]], name: str, input: Any = None, *, thread_id: str | None = None) -> Iterator[dict]:
    """with step(trace, "retrieve", q) as out: out["output"] = ... 형태로 한 단계를 기록합니다."""
    collector = TraceCollector()
    collector.record("tool_start", name)
    emit(thread_id, "start", name, {"input": _short(input)})
    started = time.perf_counter()
    out: dict[str, Any] = {"output": None}
    error = None
    try:
        yield out
    except Exception as e:  # 실패도 기록하고 다시 올립니다 (조용한 실패 금지)
        error = f"{type(e).__name__}: {e}"
        raise
    finally:
        elapsed = int((time.perf_counter() - started) * 1000)
        collector.record("tool_end", name, latency_s=round(elapsed / 1000, 3), error=error)
        entry = {"step": name, "input": _short(input), "output": _short(error or out["output"]),
                 "elapsed_ms": elapsed}
        trace.append(entry)
        emit(thread_id, "end", name, {"output": entry["output"], "elapsed_ms": elapsed, "error": error})
        _append_log({"thread_id": thread_id, **entry, "events": collector.events})


def _append_log(record: dict[str, Any]) -> None:
    """logs/trace.jsonl 에 한 줄 추가. 기록 실패는 본 작업을 멈추지 않습니다."""
    try:
        p = cfg_path("trace_log")
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    except OSError:
        pass
