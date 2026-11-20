from types import SimpleNamespace
from typing import Any

import pytest

from legacy2next.config import Secrets
from legacy2next.events import EventLog
from legacy2next.llm import (
    CallBudget,
    LlmBudgetExceededError,
    LlmGateway,
    LlmRefusalError,
    create_gateway,
)
from legacy2next.masking import SecretRegistry


class FakeMessages:
    """받은 요청을 기록하고 정해 둔 응답을 돌려주는 가짜 beta.messages."""

    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []
        self.stop_reason = "end_turn"

    async def create(self, **kwargs: Any) -> Any:
        self.requests.append(kwargs)
        return SimpleNamespace(
            model=kwargs["model"],
            stop_reason=self.stop_reason,
            stop_details=SimpleNamespace(category="cyber")
            if self.stop_reason == "refusal"
            else None,
            usage=SimpleNamespace(input_tokens=10, output_tokens=2),
            content=[SimpleNamespace(type="text", text="ok")],
        )


@pytest.fixture
def setup(tmp_path):
    reg = SecretRegistry()
    reg.register("pw-secret")
    messages = FakeMessages()
    client = SimpleNamespace(beta=SimpleNamespace(messages=messages))
    events = EventLog(tmp_path, reg)
    gateway = LlmGateway(
        client, "global.anthropic.claude-sonnet-4-6", CallBudget(limit=2), events, reg
    )
    return gateway, messages, events


async def test_gateway_masks_input_and_records_call(setup):
    gateway, messages, events = setup
    reply = await gateway.ainvoke(
        "run-1",
        "analyst",
        system="계정 pw-secret 는 보이면 안 된다",
        messages=[
            {"role": "user", "content": "pw-secret 로 로그인"},
            {"role": "user", "content": [{"type": "text", "text": "또 pw-secret"}]},
        ],
    )
    assert reply.content[0].text == "ok"
    sent = messages.requests[0]
    assert sent["model"] == "global.anthropic.claude-sonnet-4-6"
    assert "pw-secret" not in str(sent["system"]) + str(sent["messages"])
    logged = events.read("run-1")
    assert logged[0].type == "llm"
    assert logged[0].message == "LLM 호출 1/2"
    assert logged[0].data["input_tokens"] == 10


async def test_gateway_stops_at_budget_and_logs_guardrail(setup):
    gateway, messages, events = setup
    msg = [{"role": "user", "content": "a"}]
    await gateway.ainvoke("run-1", "analyst", system="s", messages=msg)
    await gateway.ainvoke("run-1", "analyst", system="s", messages=msg)
    with pytest.raises(LlmBudgetExceededError):
        await gateway.ainvoke("run-1", "analyst", system="s", messages=msg)
    assert len(messages.requests) == 2  # 한도 초과 호출은 모델에 가지 않는다
    last = events.read("run-1")[-1]
    assert last.type == "guardrail" and last.level == "block" and last.data["rule"] == "G8"
    # 다른 실행은 따로 센다
    await gateway.ainvoke("run-2", "analyst", system="s", messages=msg)


async def test_gateway_raises_on_refusal(setup):
    gateway, messages, events = setup
    messages.stop_reason = "refusal"
    with pytest.raises(LlmRefusalError):
        await gateway.ainvoke(
            "run-1", "analyst", system="s", messages=[{"role": "user", "content": "x"}]
        )
    assert events.read("run-1")[-1].level == "warn"


def test_create_gateway_requires_model_id(tmp_path):
    with pytest.raises(ValueError):
        create_gateway(
            Secrets(bedrock_model_id="", _env_file=None), CallBudget(1), EventLog(tmp_path)
        )


def test_create_gateway_builds_bedrock_client_without_network(tmp_path):
    settings = Secrets(
        bedrock_model_id="global.anthropic.claude-sonnet-4-6",
        aws_region="us-east-1",
        _env_file=None,
    )
    gateway = create_gateway(settings, CallBudget(1), EventLog(tmp_path))
    assert isinstance(gateway, LlmGateway)
