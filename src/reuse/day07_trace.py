"""Day 7 TraceCollector 재사용 (sds-ax-training/day07/practice/starter/submission.py 에서 복사).

에이전트 실행 이벤트(도구·모델 시작/끝)를 결정적 구조로 기록합니다. API 응답의 trace 와
logs/trace.jsonl 은 src/tracing.py 가 이 기록에서 만듭니다.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

# TraceCollector가 받는 이벤트 종류입니다. local_tracer.py의 FileTracer와 같은 이름을 씁니다.
TRACE_EVENTS = ("llm_start", "llm_end", "tool_start", "tool_end")

# failures의 detail에 답변을 옮겨 적을 때 자르는 길이입니다. 보고서가 길어지지 않게 합니다.
_DETAIL_MAX = 200


# ══════════════════════════════════════════════════════════════════
# 기초 파트 (7점)
# ══════════════════════════════════════════════════════════════════

class TraceCollector:
    """실행 중 일어난 일을 기록합니다.

    LangChain 콜백 핸들러로도 쓸 수 있게 만들되, 여기서는 최소 인터페이스만 요구합니다.
    trace는 결정적 구조체라서, LLM이 무슨 말을 했든 이벤트 개수와 필드는 확정 검사됩니다.
    """

    def __init__(self) -> None:
        # 이벤트를 기록 순서대로 담는 목록입니다. 순번(seq)은 이 목록의 길이로 매깁니다.
        self._events: list[dict] = []

    def record(self, event: str, name: str, **fields: Any) -> None:
        """이벤트 하나를 기록합니다.

        event: "llm_start" | "llm_end" | "tool_start" | "tool_end" 중 하나
        name : 모델 이름 또는 도구 이름
        fields: latency_s, tokens 등 부가 정보
        """
        # 정해진 네 종류 밖의 이벤트는 받지 않습니다.
        # 오타("tool_ended" 등)가 조용히 섞이면 나중에 grep으로 셀 때 숫자가 어긋납니다.
        if event not in TRACE_EVENTS:
            raise ValueError(f"지원하지 않는 event입니다: {event!r} (허용: {', '.join(TRACE_EVENTS)})")

        # 기본 필드(seq, event, name, ts)를 먼저 두고 부가 필드(latency_s, tokens 등)를 뒤에 붙입니다.
        # 부가 필드가 기본 필드 이름과 겹치면 기본 필드를 지키기 위해 무시합니다.
        entry: dict[str, Any] = {
            "seq": len(self._events) + 1,           # 1부터 시작하는 기록 순번
            "event": event,
            "name": str(name),
            "ts": round(time.time(), 3),            # 기록 시각(유닉스 초)
        }
        for key, value in fields.items():
            entry.setdefault(key, value)
        self._events.append(entry)

    @property
    def events(self) -> list[dict]:
        """기록된 이벤트 목록을 반환합니다."""
        # 바깥에서 목록이나 이벤트를 고쳐도 기록 원본이 바뀌지 않도록 사본을 돌려줍니다.
        return [dict(e) for e in self._events]

    def dump(self, path: str | Path) -> None:
        """이벤트를 JSON Lines 파일로 씁니다. 한 줄에 한 이벤트."""
        # JSON Lines: 한 줄에 이벤트 하나. 한글은 그대로 남겨 grep으로 바로 찾을 수 있게 합니다.
        # 직렬화할 수 없는 값(예외 객체 등)은 default=str로 문자열로 바꿔 dump 자체가 죽지 않게 합니다.
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            for e in self._events:
                f.write(json.dumps(e, ensure_ascii=False, default=str) + "\n")
