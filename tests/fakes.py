"""테스트용 가짜 모델 (실제 Bedrock 호출 없이 배선 검증)."""

from __future__ import annotations

from typing import Any, Callable


class _Runnable:
    def __init__(self, fn: Callable[[Any], Any]):
        self.fn = fn

    def invoke(self, value: Any) -> Any:
        return self.fn(value)


class FakeStructuredLLM:
    """with_structured_output(schema) 를 지원하는 가짜 LLM.

    responder(schema, prompt) 가 돌려준 값을 그대로 응답합니다. calls 에 호출 기록이 남습니다.
    """

    def __init__(self, responder: Callable[[type, str], Any]):
        self.responder = responder
        self.calls: list[tuple[str, str]] = []

    def with_structured_output(self, schema: type) -> _Runnable:
        def fn(prompt: Any) -> Any:
            self.calls.append((schema.__name__, str(prompt)))
            return self.responder(schema, str(prompt))
        return _Runnable(fn)
