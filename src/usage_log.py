"""LLM·임베딩 호출 사용량 기록 (비용 대시보드용).

개발한 시스템이 Bedrock에 보내는 요청을 한 건마다 `logs/llm_usage.jsonl`에 한 줄씩 남깁니다.
`scripts/cost_dashboard.py`가 이 파일을 읽어 요청 건수와 예상 비용을 집계합니다.

언제 쓰나:
- `src.llm.default_llm()` / `default_embeddings()`가 자동으로 붙이므로 호출하는 쪽은 신경 쓸 필요가 없습니다.
- 테스트의 가짜 모델에는 붙지 않으므로 테스트 실행이 사용량 로그를 오염시키지 않습니다.

언제 쓰지 않나:
- 비용 계산은 여기서 하지 않습니다. 단가가 바뀌어도 과거 로그를 다시 계산할 수 있도록
  토큰 수만 남기고, 금액은 대시보드가 `config/pricing.yaml`로 계산합니다.

기록 실패(디스크 권한 등)는 본 작업을 멈추지 않도록 조용히 무시합니다.
환경변수 `LLM_USAGE_LOG`로 경로를 바꿀 수 있고, 빈 문자열이면 기록하지 않습니다.
"""

from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler

DEFAULT_LOG_PATH = Path(__file__).resolve().parent.parent / "logs" / "llm_usage.jsonl"
_lock = threading.Lock()


def log_path() -> Path | None:
    """기록할 파일 경로. LLM_USAGE_LOG가 빈 문자열이면 None(기록 끔)."""
    env = os.environ.get("LLM_USAGE_LOG")
    if env is None:
        return DEFAULT_LOG_PATH
    return Path(env) if env.strip() else None


def write_record(record: dict[str, Any]) -> None:
    """한 줄(JSON)을 덧붙입니다. 실패해도 예외를 올리지 않습니다."""
    path = log_path()
    if path is None:
        return
    record = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), **record}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with _lock, path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass


def _usage_from_result(response: Any) -> tuple[int, int]:
    """LLMResult에서 입력/출력 토큰 수를 꺼냅니다. 없으면 (0, 0)."""
    for gens in getattr(response, "generations", None) or []:
        for gen in gens:
            meta = getattr(getattr(gen, "message", None), "usage_metadata", None) or {}
            if meta:
                return int(meta.get("input_tokens", 0)), int(meta.get("output_tokens", 0))
    usage = (getattr(response, "llm_output", None) or {}).get("usage") or {}
    return int(usage.get("inputTokens", 0)), int(usage.get("outputTokens", 0))


class UsageLogger(BaseCallbackHandler):
    """채팅 모델 호출 1건 = 로그 1줄. stage는 모델을 만든 모듈 이름(예: src.analyst.inventory)."""

    def __init__(self, model: str, stage: str):
        self.model = model
        self.stage = stage
        self._started: dict[UUID, float] = {}

    def on_chat_model_start(self, serialized, messages, *, run_id: UUID, **kwargs) -> None:
        self._started[run_id] = time.perf_counter()

    def on_llm_start(self, serialized, prompts, *, run_id: UUID, **kwargs) -> None:
        self._started[run_id] = time.perf_counter()

    def _elapsed(self, run_id: UUID) -> float | None:
        start = self._started.pop(run_id, None)
        return round(time.perf_counter() - start, 2) if start is not None else None

    def on_llm_end(self, response, *, run_id: UUID, **kwargs) -> None:
        in_tok, out_tok = _usage_from_result(response)
        write_record({"kind": "chat", "model": self.model, "stage": self.stage, "status": "ok",
                      "input_tokens": in_tok, "output_tokens": out_tok,
                      "latency_s": self._elapsed(run_id)})

    def on_llm_error(self, error: BaseException, *, run_id: UUID, **kwargs) -> None:
        # 실패한 요청도 건수에는 남깁니다 (스로틀링 재시도 횟수를 보기 위해). 토큰은 알 수 없어 0.
        write_record({"kind": "chat", "model": self.model, "stage": self.stage, "status": "error",
                      "error": type(error).__name__, "input_tokens": 0, "output_tokens": 0,
                      "latency_s": self._elapsed(run_id)})


def estimate_tokens(texts: list[str]) -> int:
    """임베딩 API는 토큰 수를 돌려주지 않으므로 글자 수로 어림합니다 (약 3글자 = 1토큰, 한글 혼합 기준)."""
    return sum(max(1, len(t) // 3) for t in texts)


class LoggedEmbeddings:
    """임베딩 객체를 감싸 호출 건수와 어림 토큰 수를 남깁니다. 나머지 속성은 원본에 위임."""

    def __init__(self, inner: Any, model: str, stage: str):
        self._inner = inner
        self._model = model
        self._stage = stage

    def _log(self, texts: list[str]) -> None:
        write_record({"kind": "embedding", "model": self._model, "stage": self._stage,
                      "status": "ok", "texts": len(texts),
                      "input_tokens": estimate_tokens(texts), "output_tokens": 0,
                      "estimated": True})

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        result = self._inner.embed_documents(texts)
        self._log(texts)
        return result

    def embed_query(self, text: str) -> list[float]:
        result = self._inner.embed_query(text)
        self._log([text])
        return result

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)
