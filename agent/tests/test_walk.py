"""T07d Hypothesize · Walk.

단위: 쓰기 동작 판정(G1), LLM이 고른 동작 재검사(없는 요소·역할 불일치·계정 값 입력 거부).
통합(실제 Playwright MCP + 시험 사이트 + 가짜 LLM): 후보 저장, 2개 이상 완주, Flow Trace 저장,
재실행 스크립트가 LLM 없이 같은 흐름을 재현 (EXP-01), 완주 못 한 후보는 이유가 남는다.
"""

import os
import shutil
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from legacy2next.api import create_app
from legacy2next.browser import MCP_CLI
from legacy2next.config import AgentConfig
from legacy2next.crawl import CrawlStore, FlowTrace, Hypotheses
from legacy2next.login import parse_elements
from legacy2next.masking import secrets
from legacy2next.walker import WalkDecision, _check, _StopFlow, is_write_action

from .fixtures.site_server import start_site

SNAPSHOT = """- generic [ref=e1]:
  - link "휴가 신청 목록" [ref=e2]
  - button "신청" [ref=e3]
  - textbox "검색어" [ref=e4]
  - button "조회" [ref=e5]
  - link "삭제" [ref=e6]
"""


def test_write_action_rule_g1():
    assert is_write_action("button", "신청")
    assert is_write_action("button", "저장하기")
    assert is_write_action("link", "삭제")
    assert not is_write_action("link", "휴가 신청 목록")  # 목록으로 가는 링크는 이동이다
    assert not is_write_action("button", "조회")


def test_llm_actions_are_rechecked():
    elements = parse_elements(SNAPSHOT)
    ok = WalkDecision(action="type", target_ref="e4", text="휴가", reason="")
    assert _check(ok, elements)[1].name == "검색어"
    cases = [
        (WalkDecision(action="click", target_ref="e3", reason=""), "write_action"),
        (WalkDecision(action="click", target_ref="e6", reason=""), "write_action"),
        (WalkDecision(action="click", target_ref="e99", reason=""), "not_found"),
        (WalkDecision(action="type", target_ref="e5", text="x", reason=""), "other"),
    ]
    for decision, kind in cases:
        with pytest.raises(_StopFlow) as info:
            _check(decision, elements)
        assert info.value.kind == kind


def test_account_values_are_never_typed_g3():
    secrets.register("walk-secret-pw-123")
    try:
        bad = WalkDecision(action="type", target_ref="e4", text="walk-secret-pw-123", reason="")
        with pytest.raises(_StopFlow):
            _check(bad, parse_elements(SNAPSHOT))
    finally:
        secrets.clear()


needs_mcp = pytest.mark.skipif(
    not MCP_CLI.exists() or shutil.which("node") is None,
    reason="Playwright MCP 미설치 (npm install --prefix agent/mcp)",
)


@needs_mcp
def test_walk_completes_flows_and_replays_without_llm(tmp_path: Path):
    server = start_site()
    site = f"http://127.0.0.1:{server.server_address[1]}"
    cfg = AgentConfig(
        log_dir=tmp_path / "logs",
        checkpoint_path=tmp_path / "cp.sqlite",
        output_root=tmp_path / "next-pjt",
        session_dir=tmp_path / "sessions",
        stub_step_ms=0,
        explorer={"mode": "mcp", "headless": True, "auth_headless": True},
    )
    try:
        with TestClient(create_app(cfg, fake_llm=True)) as client:
            client.post("/query", json={"alias": "walk-t", "url": f"{site}/"})
            deadline = time.monotonic() + 120
            while time.monotonic() < deadline:
                run = client.get("/runs/walk-t").json()
                if run["status"] in ("awaiting_analysis", "failed"):
                    break
                time.sleep(0.3)
    finally:
        server.shutdown()
    log = "\n".join(line["message"] for line in run["logs"])
    assert run["status"] == "awaiting_analysis", log[-1500:]

    store = CrawlStore(tmp_path / "next-pjt" / "walk-t" / "crawl")
    hypotheses = store.load_hypotheses()
    assert isinstance(hypotheses, Hypotheses) and len(hypotheses.candidates) >= 2
    totals = [c.total for c in hypotheses.candidates]
    assert totals == sorted(totals, reverse=True)  # 점수 높은 순

    flows = store.load_flows()
    completed = [f for f in flows if f.status == "completed"]
    assert len(completed) >= 2, [(f.name, f.reason) for f in flows]
    for flow in completed:
        FlowTrace.model_validate(flow.model_dump())
        assert flow.steps and all(s.to_url.startswith(site) for s in flow.steps)
        # 재실행 스크립트가 LLM 없이 같은 흐름을 재현한다 (EXP-01)
        assert flow.replay and flow.replay.ok and flow.replay.llm_calls == 0
        assert flow.replay.steps_done == len(flow.steps)

    search = next(f for f in completed if f.kind == "search")
    assert [s.action for s in search.steps] == ["type", "click"]
    assert search.steps[0].input_kind == "검색어" and search.steps[0].value
    assert search.steps[-1].to_title == "공지사항 목록" and "searchWrd=" in search.steps[-1].to_url
    assert any(r.method == "GET" and "searchWrd=" in r.url for r in search.steps[-1].network)
    view = next(f for f in completed if f.kind == "view" and f.start_url.endswith("/board.html"))
    assert view.steps[0].target and view.steps[0].target.role == "link"
    assert view.steps[-1].to_title == "공지사항 상세"
    assert view.steps[0].code  # Playwright 실행 코드도 남긴다

    failed = [f for f in flows if f.status == "failed"]
    assert all(f.fail_kind and f.reason for f in failed)  # 완주 못 한 후보는 이유가 있다
    manifest = store.load_manifest()
    assert manifest and set(manifest.flows) == {f.flow_id for f in flows}
    assert "흐름 걷기: 완주" in log and "재실행 확인" in log
    # 콘솔 스냅샷에 후보·완주·실패 이유·재실행 결과가 보인다
    walk = run["walk"]
    assert walk["domain"] and len(walk["candidates"]) == len(hypotheses.candidates)
    statuses = {c["id"]: c for c in walk["candidates"]}
    for flow in flows:
        view_ = statuses[flow.flow_id]
        assert view_["status"] == flow.status
        if flow.status == "completed":
            assert view_["replayOk"] is True and view_["steps"]
        else:
            assert view_["failKind"] and view_["result"]
    # 걷다가 처음 닿은 상세 화면도 원본·파생을 저장했다
    assert any(s.title == "공지사항 상세" for s in manifest.screens)


# ── 실제 Bedrock으로 흐름 걷기 (L2N_LIVE=1일 때만, 호출 비용 발생) ──

LIVE = os.environ.get("L2N_LIVE") == "1"


@needs_mcp
@pytest.mark.skipif(not LIVE, reason="L2N_LIVE=1일 때만 실제 Bedrock 호출")
def test_walk_with_real_llm(tmp_path: Path):
    from dotenv import load_dotenv

    from legacy2next.config import REPO_ROOT

    load_dotenv(REPO_ROOT / ".env")
    server = start_site()
    site = f"http://127.0.0.1:{server.server_address[1]}"
    cfg = AgentConfig(
        log_dir=tmp_path / "logs",
        checkpoint_path=tmp_path / "cp.sqlite",
        output_root=tmp_path / "next-pjt",
        session_dir=tmp_path / "sessions",
        stub_step_ms=0,
        explorer={"mode": "mcp", "headless": True, "auth_headless": True},
    )
    try:
        with TestClient(create_app(cfg)) as client:
            client.post("/query", json={"alias": "walk-live", "url": f"{site}/"})
            deadline = time.monotonic() + 600
            while time.monotonic() < deadline:
                run = client.get("/runs/walk-live").json()
                if run["status"] in ("awaiting_analysis", "failed"):
                    break
                time.sleep(1)
    finally:
        server.shutdown()
    log = "\n".join(line["message"] for line in run["logs"])
    print(log)
    assert run["status"] == "awaiting_analysis", log[-2000:]
    store = CrawlStore(tmp_path / "next-pjt" / "walk-live" / "crawl")
    flows = store.load_flows()
    for f in flows:
        steps = " → ".join(f"{s.action} {s.target.name if s.target else ''}" for s in f.steps)
        print(f.flow_id, f.name, f.status, f.fail_kind, f.reason, "|", steps, "| replay", f.replay)
    completed = [f for f in flows if f.status == "completed"]
    assert len(completed) >= 2
    assert all(f.replay and f.replay.ok for f in completed)
    print("LLM 호출", run["metrics"]["llmCalls"])
