import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from legacy2next.api import create_app
from legacy2next.config import AgentConfig


@pytest.fixture
def client(tmp_path: Path):
    cfg = AgentConfig(
        log_dir=tmp_path / "logs", checkpoint_path=tmp_path / "cp.sqlite", stub_step_ms=0
    )
    with TestClient(create_app(cfg, fake_llm=True)) as c:
        yield c


def wait_status(client: TestClient, alias: str, status: str, timeout: float = 10) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        run = client.get(f"/runs/{alias}").json()
        if run["status"] == status:
            return run
        time.sleep(0.05)
    raise AssertionError(f"{alias} 상태가 {status}가 되지 않음: {run['status']}")


def test_health_and_cors(client):
    res = client.get("/health", headers={"Origin": "http://localhost:5173"})
    assert res.status_code == 200
    assert res.json()["status"] == "ok"
    assert res.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_full_flow_with_two_approvals(client):
    res = client.post("/query", json={"alias": "demo", "url": "https://legacy.example.com"})
    assert res.status_code == 200
    assert res.json()["intent"] == "new"

    # 승인 1에서 멈춘다
    run = wait_status(client, "demo", "awaiting_analysis")
    stages = {s["id"]: s["state"] for s in run["stages"]}
    assert stages["explorer"] == "done" and stages["analysisReview"] == "waiting"
    assert run["analysis"]["happyPaths"][0]["id"] == "hp1"
    assert run["metrics"]["screensCollected"] == 18
    assert client.get("/runs").json() == [
        {"alias": "demo", "url": "https://legacy.example.com", "status": "awaiting_analysis"}
    ]

    # 수정 요청은 의견이 있어야 하고, 보내면 다시 승인 대기
    bad = client.post(
        "/runs/demo/analysis",
        json={
            "action": "revise",
            "happyPathIds": ["hp1"],
            "dataMode": "mock",
            "variantDecisions": {},
        },
    )
    assert bad.status_code == 400
    approve = {
        "action": "approve",
        "happyPathIds": ["hp1", "hp2"],
        "dataMode": "mock",
        "variantDecisions": {"v1": "unify", "v2": "prop", "v3": "hold"},
    }
    assert client.post("/runs/demo/analysis", json=approve).status_code == 202

    # 승인 2에서 멈춘다: 대폭 변경 화면은 일괄 승인에 포함되지 않는다
    run = wait_status(client, "demo", "awaiting_design")
    assert run["approvedAnalysis"]["happyPathIds"] == ["hp1", "hp2"]
    screens = run["design"]["screens"]
    major = [s for s in screens if s["majorChange"]]
    assert len(major) == 1
    assert all(c["why"] for c in major[0]["changes"])  # 바뀐 점마다 이유가 있다
    assert client.post("/runs/demo/design", json={"action": "approveRegular"}).status_code == 202
    run = wait_status(client, "demo", "awaiting_design")
    assert [s["state"] for s in run["design"]["screens"] if s["majorChange"]] == ["pending"]
    res = client.post(
        "/runs/demo/design", json={"action": "approveScreen", "screenId": major[0]["id"]}
    )
    assert res.status_code == 202

    run = wait_status(client, "demo", "done")
    assert run["result"]["outputDir"] == "next-pjt/demo/"
    assert all(s["state"] == "done" for s in run["stages"])
    assert run["timing"]["finishedAt"] is not None
    assert any("승인 2 완료" in line["message"] for line in run["logs"])


def test_reject_and_stop(client):
    client.post("/query", json={"alias": "a1", "url": "https://a.example.com"})
    wait_status(client, "a1", "awaiting_analysis")
    client.post(
        "/runs/a1/analysis",
        json={"action": "reject", "happyPathIds": [], "dataMode": "mock", "variantDecisions": {}},
    )
    run = wait_status(client, "a1", "stopped")
    assert {s["id"]: s["state"] for s in run["stages"]}["analysisReview"] == "stopped"

    client.post("/query", json={"alias": "a2", "url": "https://b.example.com"})
    wait_status(client, "a2", "awaiting_analysis")
    assert client.post("/runs/a2/stop").status_code == 202
    wait_status(client, "a2", "stopped")
    # 중단된 실행에는 승인을 보낼 수 없다
    res = client.post(
        "/runs/a2/analysis",
        json={
            "action": "approve",
            "happyPathIds": ["hp1"],
            "dataMode": "mock",
            "variantDecisions": {},
        },
    )
    assert res.status_code == 400


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ({"alias": "x", "url": "https://a.example.com"}, "별칭"),
        ({"alias": "ok-site", "url": "legacy.example.com"}, "URL"),
        ({"alias": "ok-site", "url": "https://a.example.com", "kind": "extend"}, "T16"),
        ({"alias": "ok-site"}, "url 또는 question"),
    ],
)
def test_query_validation(client, body, message):
    res = client.post("/query", json=body)
    assert res.status_code == 400
    assert message in res.json()["detail"]


def test_duplicate_alias_and_unknown_run(client):
    client.post("/query", json={"alias": "dup", "url": "https://a.example.com"})
    res = client.post("/query", json={"alias": "dup", "url": "https://a.example.com"})
    assert res.status_code == 400
    assert client.get("/runs/nope").status_code == 404


def test_query_question_stub(client):
    client.post("/query", json={"alias": "q1", "url": "https://a.example.com"})
    res = client.post("/query", json={"alias": "q1", "question": "Happy Path는?"})
    assert res.json()["intent"] == "query"
    assert res.json()["answer"]["kind"] == "answer"


def test_design_change_reads_old_string_format():
    from legacy2next.schemas import DesignChange

    assert DesignChange.model_validate("예전 문구").model_dump() == {"what": "예전 문구", "why": ""}


@pytest.mark.parametrize(
    ("question", "alias", "kind", "check"),
    [
        ("오늘 점심 메뉴 추천해줘", None, "rejected", "레거시 웹 시스템"),
        ("https://legacy.example.com 분석해서 POC 만들어줘", None, "start", "새 POC 생성"),
        ("화면 구성이 어떻게 돼?", None, "answer", "대상 사이트"),
    ],
)
def test_query_router_answers(client, question, alias, kind, check):
    res = client.post("/query", json={"question": question, "alias": alias})
    answer = res.json()["answer"]
    assert answer["kind"] == kind
    assert check in answer["text"]
    if kind == "start":
        assert answer["start"] == {
            "kind": "new",
            "url": "https://legacy.example.com",
            "alias": "legacy-example",
        }
