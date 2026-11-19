"""사용량 기록·대시보드 집계 테스트 (실제 Bedrock 호출 없음)."""

from __future__ import annotations

import json
from uuid import uuid4

from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult

from scripts.cost_dashboard import render_html, summarize_claude_code, summarize_system
from src.usage_log import LoggedEmbeddings, UsageLogger


def _result(inp: int, out: int) -> LLMResult:
    msg = AIMessage(content="ok", usage_metadata={"input_tokens": inp, "output_tokens": out, "total_tokens": inp + out})
    return LLMResult(generations=[[ChatGeneration(message=msg)]])


def test_logger_writes_tokens_and_errors(tmp_path, monkeypatch):
    log = tmp_path / "usage.jsonl"
    monkeypatch.setenv("LLM_USAGE_LOG", str(log))
    cb = UsageLogger("m1", "src.analyst.inventory")
    rid = uuid4()
    cb.on_chat_model_start({}, [[]], run_id=rid)
    cb.on_llm_end(_result(1000, 200), run_id=rid)
    cb.on_llm_error(RuntimeError("throttled"), run_id=uuid4())

    rows = [json.loads(x) for x in log.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["input_tokens"] == 1000 and rows[0]["output_tokens"] == 200
    assert rows[0]["stage"] == "src.analyst.inventory" and rows[0]["latency_s"] is not None
    assert rows[1]["status"] == "error"

    s = summarize_system(log, {"m1": {"input": 3.0, "output": 15.0}})
    assert s["total"]["requests"] == 2 and s["total"]["errors"] == 1
    assert abs(s["total"]["cost"] - (1000 * 3 + 200 * 15) / 1e6) < 1e-12


def test_logging_disabled_with_empty_env(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_USAGE_LOG", "")
    UsageLogger("m", "s").on_llm_end(_result(1, 1), run_id=uuid4())  # 예외 없이 무시


def test_logged_embeddings_delegates(tmp_path, monkeypatch):
    log = tmp_path / "usage.jsonl"
    monkeypatch.setenv("LLM_USAGE_LOG", str(log))

    class Inner:
        dim = 3
        def embed_documents(self, texts):
            return [[0.0] * 3 for _ in texts]

    emb = LoggedEmbeddings(Inner(), "e1", "src.analyst.variants")
    assert len(emb.embed_documents(["가나다라마바", "abc"])) == 2
    assert emb.dim == 3
    row = json.loads(log.read_text(encoding="utf-8"))
    assert row["kind"] == "embedding" and row["texts"] == 2 and row["estimated"] is True


def test_claude_code_dedupes_streamed_lines(tmp_path):
    def line(out, mid="msg_1"):
        return json.dumps({"type": "assistant", "sessionId": "s1", "timestamp": "2026-11-18T04:00:00Z",
                           "message": {"id": mid, "model": "opus", "usage": {
                               "input_tokens": 10, "output_tokens": out, "cache_read_input_tokens": 1000,
                               "cache_creation_input_tokens": 100,
                               "cache_creation": {"ephemeral_1h_input_tokens": 100, "ephemeral_5m_input_tokens": 0}}}})
    (tmp_path / "s1.jsonl").write_text("\n".join([line(5), line(50), line(7, "msg_2")]), encoding="utf-8")
    price = {"opus": {"input": 4, "output": 20, "cache_write_5m": 5, "cache_write_1h": 8, "cache_read": 0.2}}
    c = summarize_claude_code(tmp_path, price)
    assert c["total"]["requests"] == 2
    assert c["total"]["output"] == 57
    expected = (20 * 4 + 57 * 20 + 200 * 8 + 2000 * 0.2) / 1e6
    assert abs(c["total"]["cost"] - expected) < 1e-12
    assert "LLM 비용 대시보드" in render_html({"generated_at": "x", "system": {}, "claude_code": c})
