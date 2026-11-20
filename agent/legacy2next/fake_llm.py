"""테스트용 가짜 LLM 클라이언트 (`--fake-llm`). 실제 Bedrock 없이 E2E·개발 확인을 하기 위함.

Router 분류만 흉내 낸다: URL이 있으면 신규 생성(확장 단어가 있으면 확장),
사이트 관련 단어가 있으면 질의,
그 외는 범위 밖. 실제 판단 품질은 실제 LLM으로 RTR 평가 샘플을 돌려 확인한다.
"""

from __future__ import annotations

import json
import re
from types import SimpleNamespace
from typing import Any

URL_PATTERN = re.compile(r"https?://[^\s<>\"']+")
QUERY_WORDS = (
    "화면",
    "컴포넌트",
    "happy",
    "분석",
    "디자인",
    "데이터",
    "목업",
    "결정",
    "승인",
    "진행",
    "결과",
    "변이",
    "사이트",
)
EXTEND_WORDS = ("확장", "추가", "더 만들", "이어서")


def _between(text: str, tag: str) -> str:
    match = re.search(rf"<{tag}>(.*?)</{tag}>", text, re.S)
    return match.group(1).strip() if match else ""


def classify(user_message: str) -> dict[str, Any]:
    request = _between(user_message, "user_request")
    sites = [s.strip() for s in _between(user_message, "known_sites").split(",")]
    selected = _between(user_message, "selected_site")
    lowered = request.lower()
    url_match = URL_PATTERN.search(request)
    named = next((s for s in sites if s and s in lowered), None)
    if url_match or (named and any(w in request for w in EXTEND_WORDS)):
        intent = "extend" if any(w in request for w in EXTEND_WORDS) else "new"
        return {
            "intent": intent,
            "url": url_match.group(0) if url_match else None,
            "alias": named,
            "reason": "(가짜 LLM) URL 또는 확장 요청 단어",
        }
    if named or any(w in lowered for w in QUERY_WORDS):
        return {
            "intent": "query",
            "url": None,
            "alias": named or selected or None,
            "reason": "(가짜 LLM) 사이트 관련 단어",
        }
    return {
        "intent": "out_of_scope",
        "url": None,
        "alias": None,
        "reason": "(가짜 LLM) 서비스와 관련 없는 요청",
    }


class _FakeMessages:
    async def create(self, **kwargs: Any) -> Any:
        content = kwargs["messages"][-1]["content"]
        text = (
            content
            if isinstance(content, str)
            else "".join(b.get("text", "") for b in content if isinstance(b, dict))
        )
        return SimpleNamespace(
            model="fake-llm",
            stop_reason="end_turn",
            stop_details=None,
            usage=SimpleNamespace(input_tokens=0, output_tokens=0),
            content=[
                SimpleNamespace(type="text", text=json.dumps(classify(text), ensure_ascii=False))
            ],
        )


class FakeLlmClient:
    """LlmGateway가 쓰는 client.beta.messages.create 모양만 맞춘다."""

    def __init__(self) -> None:
        self.beta = SimpleNamespace(messages=_FakeMessages())
