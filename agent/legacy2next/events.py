"""실행 이벤트 로그. 실행마다 JSONL 파일로 남기고(평가 판정 근거), 구독자(SSE)에게 전달한다."""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from .masking import SecretRegistry, secrets

EventType = Literal["log", "stage", "guardrail", "status", "llm", "metrics"]
EventLevel = Literal["info", "warn", "block"]

RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


class RunEvent(BaseModel):
    """실행 중 생긴 일 하나. message·data는 저장 전에 마스킹한다."""

    run_id: str
    type: EventType
    source: str
    message: str
    level: EventLevel = "info"
    at: str = Field(default_factory=now_iso)
    data: dict[str, Any] = Field(default_factory=dict)


Subscriber = Callable[[RunEvent], None]


class EventLog:
    """이벤트를 logs/runs/<run_id>.jsonl 에 추가하고 구독자에게 알린다."""

    def __init__(self, log_dir: Path, registry: SecretRegistry = secrets) -> None:
        self._dir = log_dir / "runs"
        self._registry = registry
        self._subscribers: dict[str, list[Subscriber]] = {}
        self._global: list[Subscriber] = []

    def _path(self, run_id: str) -> Path:
        if not RUN_ID_PATTERN.match(run_id):
            raise ValueError(f"실행 ID 형식이 아닙니다: {run_id!r}")
        return self._dir / f"{run_id}.jsonl"

    def _masked(self, event: RunEvent) -> RunEvent:
        data_json = self._registry.mask(json.dumps(event.data, ensure_ascii=False))
        return event.model_copy(
            update={"message": self._registry.mask(event.message), "data": json.loads(data_json)}
        )

    def emit(self, event: RunEvent) -> RunEvent:
        """마스킹 → 파일 추가 → 구독자 알림. 저장된 이벤트를 돌려준다."""
        safe = self._masked(event)
        path = self._path(safe.run_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(safe.model_dump_json() + "\n")
        for subscriber in [*self._subscribers.get(safe.run_id, []), *self._global]:
            subscriber(safe)
        return safe

    def read(self, run_id: str) -> list[RunEvent]:
        path = self._path(run_id)
        if not path.exists():
            return []
        lines = path.read_text(encoding="utf-8").splitlines()
        return [RunEvent.model_validate_json(line) for line in lines if line.strip()]

    def subscribe(self, run_id: str, subscriber: Subscriber) -> Callable[[], None]:
        """구독을 등록하고 해제 함수를 돌려준다."""
        self._subscribers.setdefault(run_id, []).append(subscriber)

        def unsubscribe() -> None:
            subs = self._subscribers.get(run_id, [])
            if subscriber in subs:
                subs.remove(subscriber)

        return unsubscribe

    def queue(self, run_id: str) -> tuple[asyncio.Queue[RunEvent], Callable[[], None]]:
        """SSE용: 이벤트를 받는 asyncio 큐와 해제 함수."""
        q: asyncio.Queue[RunEvent] = asyncio.Queue()
        return q, self.subscribe(run_id, q.put_nowait)

    def subscribe_all(self, subscriber: Subscriber) -> Callable[[], None]:
        """모든 실행의 이벤트를 받는다 (사이트 목록 갱신용)."""
        self._global.append(subscriber)

        def unsubscribe() -> None:
            if subscriber in self._global:
                self._global.remove(subscriber)

        return unsubscribe

    def run_ids(self) -> list[str]:
        """이벤트 파일이 있는 실행 ID 목록 (오래된 순)."""
        if not self._dir.exists():
            return []
        files = sorted(self._dir.glob("*.jsonl"), key=lambda p: p.stat().st_ctime)
        return [p.stem for p in files]
