"""LLM 호출 래퍼. 실행당 호출 수 한도(G8)와 입력 마스킹(G3), 호출 기록, 거절(refusal) 처리를 맡는다.

Bedrock Claude는 Anthropic SDK의 bedrock-runtime 클라이언트(InvokeModel)로 부른다 (추론 프로필 ID).
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Protocol

from anthropic import AsyncAnthropicBedrock, BetaRefusalFallbackMiddleware
from anthropic.types.beta import BetaMessage, BetaMessageParam

from .config import Secrets
from .events import EventLog, RunEvent
from .masking import SecretRegistry, secrets

logger = logging.getLogger(__name__)

DEFAULT_MAX_TOKENS = 16000


class LlmBudgetExceededError(RuntimeError):
    """실행당 LLM 호출 수 상한에 닿음 (G8). 그래프는 멈추고 사용자에게 보고한다."""


class LlmRefusalError(RuntimeError):
    """모델(대체 모델 포함)이 요청을 거절함 (stop_reason == "refusal")."""


class CallBudget:
    """실행 ID별 호출 수 집계."""

    def __init__(self, limit: int) -> None:
        self.limit = limit
        self._counts: dict[str, int] = {}
        self._lock = threading.Lock()

    def used(self, run_id: str) -> int:
        with self._lock:
            return self._counts.get(run_id, 0)

    def take(self, run_id: str) -> int:
        """호출 1회를 예약한다. 상한을 넘으면 예외, 아니면 이번 호출 번호를 돌려준다."""
        with self._lock:
            used = self._counts.get(run_id, 0)
            if used >= self.limit:
                raise LlmBudgetExceededError(
                    f"LLM 호출 수 상한({self.limit}회)에 닿아 실행을 멈춥니다."
                )
            self._counts[run_id] = used + 1
            return used + 1


class _BetaMessages(Protocol):
    async def create(self, **kwargs: Any) -> BetaMessage: ...


class _Beta(Protocol):
    @property
    def messages(self) -> _BetaMessages: ...


class MessagesClient(Protocol):
    """게이트웨이가 쓰는 클라이언트 모양. 실제는 AsyncAnthropicBedrock, 테스트는 가짜."""

    @property
    def beta(self) -> _Beta: ...


class LlmGateway:
    """모든 노드는 이 게이트웨이로만 LLM을 부른다."""

    def __init__(
        self,
        client: MessagesClient,
        model: str,
        budget: CallBudget,
        events: EventLog,
        registry: SecretRegistry = secrets,
    ) -> None:
        self._client = client
        self._model = model
        self._budget = budget
        self._events = events
        self._registry = registry

    def _mask_content(self, content: Any) -> Any:
        if isinstance(content, str):
            return self._registry.mask(content)
        if isinstance(content, list):
            return [
                {**block, "text": self._registry.mask(str(block["text"]))}
                if isinstance(block, dict) and block.get("type") == "text"
                else block
                for block in content
            ]
        return content

    def _mask_messages(self, messages: list[BetaMessageParam]) -> list[BetaMessageParam]:
        return [
            {**message, "content": self._mask_content(message["content"])}  # type: ignore[typeddict-item]
            for message in messages
        ]

    def _emit(self, run_id: str, source: str, **fields: Any) -> None:
        self._events.emit(RunEvent(run_id=run_id, source=source, **fields))

    async def ainvoke(
        self,
        run_id: str,
        source: str,
        *,
        system: str,
        messages: list[BetaMessageParam],
        max_tokens: int = DEFAULT_MAX_TOKENS,
        **params: Any,
    ) -> BetaMessage:
        """한도 확인 → 입력 마스킹 → 호출 → 거절 확인 → 이벤트 기록."""
        try:
            number = self._budget.take(run_id)
        except LlmBudgetExceededError as e:
            self._emit(
                run_id,
                source,
                type="guardrail",
                level="block",
                message=f"G8 {e}",
                data={"rule": "G8", "limit": self._budget.limit},
            )
            raise

        response = await self._client.beta.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=self._registry.mask(system),
            messages=self._mask_messages(messages),
            **params,
        )

        self._emit(
            run_id,
            source,
            type="llm",
            message=f"LLM 호출 {number}/{self._budget.limit}",
            data={
                "model": response.model,
                "stop_reason": response.stop_reason,
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
        )
        if response.stop_reason == "refusal":
            category = response.stop_details.category if response.stop_details else None
            self._emit(
                run_id,
                source,
                type="log",
                level="warn",
                message=f"모델이 요청을 거절했습니다 (분류: {category or '없음'})",
            )
            raise LlmRefusalError(f"모델이 요청을 거절했습니다 (분류: {category or '없음'})")
        return response


def create_bedrock_client(settings: Secrets) -> AsyncAnthropicBedrock:
    """Bedrock(bedrock-runtime) 클라이언트. 자격 증명은 AWS 기본 체인(.env의 AWS_* 등)에서 읽는다.

    Mantle(bedrock-mantle) 경로는 현재 계정 IAM 권한이 없어 쓰지 않는다.

    거절 시 대체 모델로 다시 시도하는 SDK 미들웨어를 단다 (Bedrock은 서버 쪽 fallbacks 미지원).
    """
    middleware = []
    if settings.bedrock_fallback_model_id:
        middleware.append(
            BetaRefusalFallbackMiddleware([{"model": settings.bedrock_fallback_model_id}])
        )
    return AsyncAnthropicBedrock(aws_region=settings.aws_region, middleware=middleware)


def create_gateway(settings: Secrets, budget: CallBudget, events: EventLog) -> LlmGateway:
    if not settings.bedrock_model_id:
        raise ValueError(".env에 BEDROCK_MODEL_ID가 없습니다.")
    return LlmGateway(create_bedrock_client(settings), settings.bedrock_model_id, budget, events)
