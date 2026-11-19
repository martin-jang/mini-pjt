"""모델 생성과 공통 유틸 (Day 1 패턴 재사용).

모델은 반드시 함수 안에서 만듭니다. 모듈을 불러오는 것만으로 AWS 자격증명을 요구하지 않고,
테스트는 가짜 모델을 주입해 실호출 없이 배선을 검증할 수 있게 하기 위해서입니다.
"""

from __future__ import annotations

import sys
import time
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

import src.config  # noqa: F401  .env(AWS 자격증명)를 먼저 읽기 위해 불러옵니다

import os

from src.config import settings as _settings

# 모델·리전은 config/settings.yaml 의 llm 항목에서 읽고, 환경변수로 덮어쓸 수 있습니다.
_LLM_CFG = _settings().get("llm", {})
MODEL_ID = os.getenv("LLM_MODEL_ID") or _LLM_CFG.get("model_id", "us.anthropic.claude-sonnet-4-5-20250929-v1:0")
REGION = os.getenv("LLM_REGION") or _LLM_CFG.get("region", "us-east-1")
EMBED_ID = _LLM_CFG.get("embed_model_id", "amazon.titan-embed-text-v2:0")
EMBED_REGION = _LLM_CFG.get("embed_region", "us-east-1")

T = TypeVar("T", bound=BaseModel)


def _caller_module() -> str:
    """default_llm()을 부른 모듈 이름. 비용 대시보드에서 단계(stage)별로 묶는 데 씁니다."""
    frame = sys._getframe(2)
    return frame.f_globals.get("__name__", "unknown")


def default_llm(max_tokens: int = 4096):
    """교육 고정 LLM (Bedrock Claude Sonnet 4.5).

    호출마다 토큰 사용량을 logs/llm_usage.jsonl에 남기는 콜백을 붙입니다 (src/usage_log.py).
    """
    from langchain_aws import ChatBedrockConverse

    from src.usage_log import UsageLogger

    return ChatBedrockConverse(model=MODEL_ID, region_name=REGION, temperature=0, max_tokens=max_tokens,
                               callbacks=[UsageLogger(MODEL_ID, _caller_module())])


def default_embeddings():
    """교육 고정 임베딩 (Titan v2, 1024차원). 호출 건수·어림 토큰을 사용량 로그에 남깁니다."""
    from langchain_aws import BedrockEmbeddings

    from src.usage_log import LoggedEmbeddings

    return LoggedEmbeddings(BedrockEmbeddings(model_id=EMBED_ID, region_name=EMBED_REGION),
                            EMBED_ID, _caller_module())


def get_text(message: Any) -> str:
    """ChatBedrockConverse는 content를 블록 리스트로 주기도 하므로 텍스트만 모아 반환합니다."""
    content = message.content if hasattr(message, "content") else message
    if isinstance(content, list):
        return "".join(b.get("text", "") for b in content if isinstance(b, dict))
    return str(content)


def _is_throttle(e: Exception) -> bool:
    text = f"{type(e).__name__} {e}".lower()
    return "throttl" in text or "too many requests" in text or "429" in text


def invoke_structured(llm, schema: type[T], prompt: str, *, retries: int = 1) -> T:
    """구조화 출력 호출 (오류 처리 E3).

    - Bedrock 스로틀링(429)은 지수 백오프로 최대 3회 재시도
    - 스키마 검증 실패는 오류 내용을 붙여 1회 재요청
    - 그래도 실패하면 예외를 올려 호출한 쪽이 사용자에게 어느 단계가 실패했는지 알리게 함
    """
    runnable = llm.with_structured_output(schema)
    message = prompt
    for attempt in range(retries + 1):
        for backoff in range(3):
            try:
                result = runnable.invoke(message)
                break
            except Exception as e:  # 스로틀링만 재시도, 그 외는 바로 올림
                if _is_throttle(e) and backoff < 2:
                    time.sleep(2 ** (backoff + 1))
                    continue
                raise
        try:
            return result if isinstance(result, schema) else schema.model_validate(result)
        except ValidationError as ve:
            if attempt >= retries:
                raise
            message = f"{prompt}\n\n[이전 응답이 스키마 검증에 실패했습니다. 오류를 고쳐 다시 답하세요]\n{ve}"
    raise RuntimeError("unreachable")
