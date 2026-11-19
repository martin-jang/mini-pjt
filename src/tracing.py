"""실행 트레이스 (Day 7 TraceCollector 기반).

노드·도구 실행을 TraceCollector 이벤트로 기록하고, 동시에 과제 규약의 trace 항목
({"step","input","output"})을 만듭니다. 단계별 소요 시간(elapsed_ms)을 함께 남겨
'URL → POC 소요 시간' 지표의 근거로 씁니다. 모든 입출력 문자열은 PII 마스킹 후 기록합니다.
"""

from __future__ import annotations

import json
import time
from contextlib import contextmanager
from typing import Any, Iterator

from src.config import path as cfg_path
from src.guardrails import mask_pii
from src.reuse.day07_trace import TraceCollector

_MAX = 300


def _short(value: Any) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    text = mask_pii(text)
    return text if len(text) <= _MAX else text[:_MAX] + "…"


@contextmanager
def step(trace: list[dict[str, Any]], name: str, input: Any = None, *, thread_id: str | None = None) -> Iterator[dict]:
    """with step(trace, "retrieve", q) as out: out["output"] = ... 형태로 한 단계를 기록합니다."""
    collector = TraceCollector()
    collector.record("tool_start", name)
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
