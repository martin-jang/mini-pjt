"""작업(job) 실행기 배선 테스트: 가짜 분석·생성 노드로 단계 진행·승인·실패·재시도를 확인합니다.

실제 크롤링·LLM 호출은 하지 않습니다 (교육용 더미 데이터입니다).
"""

import pytest
from fastapi import HTTPException
from langgraph.checkpoint.memory import InMemorySaver

import app as app_module
from src import agent
from src.jobs import JobManager
from src.tracing import emit, step

URL = "https://example.test/start"


def _stage(job, key):
    return next(s for s in job["stages"] if s["key"] == key)


def _fake_guard(state):
    trace = list(state.get("trace", []))
    with step(trace, "input_guard", state["question"], thread_id=state["thread_id"]) as out:
        out["output"] = "통과"
    if "blocked" in state["question"]:
        return {"intent": "blocked", "trace": trace, "status": "ok", "answer": "허용되지 않은 주소"}
    url = state["question"] if state["question"].startswith("http") else None
    return {"url": url, "domain": "example.test", "trace": trace}


def _fake_analyze(fail=False):
    def node(state):
        tid, trace = state["thread_id"], list(state["trace"])
        h1 = agent._approve("login", "로그인할까요?", {"domain": "example.test"})
        with step(trace, "crawl_site", {"login": h1.get("decision")}, thread_id=tid) as out:
            out["output"] = "화면 3개"
        with step(trace, "build_screen_inventory", "d", thread_id=tid) as out:
            out["output"] = {"screen_count": 0 if fail else 3}
        if fail:
            return {"trace": trace, "status": "failed", "answer": "수집된 화면이 없습니다."}
        for name in ("decide_unification", "derive_happy_paths", "index_documents"):
            with step(trace, name, "d", thread_id=tid) as out:
                out["output"] = "ok"
        return {"trace": trace, "status": "ok", "answer": "분석 요약"}
    return node


def _fake_generate(status="ok"):
    def node(state):
        tid = state["thread_id"]
        h3 = agent._approve("happy_path_confirm", "이 흐름으로 생성할까요?", {"happy_paths": [{"name": "조회"}]})
        if h3.get("decision") != "approve":
            return {"status": "ok", "answer": "승인하지 않아 생성을 중단했습니다."}
        for name in ("scaffold", "components", "pages", "verify"):
            emit(tid, "stage", name, {"state": "start"})
            emit(tid, "log", "generate_poc", {"message": f"{name} 진행"})
            emit(tid, "stage", name, {"state": "end", "items": ["A", "B"]} if name in ("components", "pages")
                 else {"state": "end"})
        return {"status": status, "answer": "POC 생성 완료"}
    return node


def _manager(monkeypatch, analyze=None, generate=None):
    monkeypatch.setattr(agent, "guard_node", _fake_guard)
    monkeypatch.setattr(agent, "analyze_node", analyze or _fake_analyze())
    monkeypatch.setattr(agent, "generate_node", generate or _fake_generate())
    return JobManager(lambda: agent.build_pipeline_graph(InMemorySaver()), run_async=False)


def test_happy_path_waits_only_at_approvals(monkeypatch):
    jm = _manager(monkeypatch)
    job = jm.start(URL)
    # H1 로그인 승인에서 멈춤: 크롤링 단계가 승인 대기, 입력 검사는 완료
    assert job["status"] == "waiting"
    assert job["action"]["type"] == "approval" and job["action"]["stage"] == "crawl"
    assert _stage(job, "guard")["status"] == "done"
    assert _stage(job, "crawl")["status"] == "waiting"

    job = jm.act(job["id"], "approve")
    # H3 핵심 흐름 확인에서 멈춤: 분석 단계는 모두 완료
    assert job["status"] == "waiting" and job["action"]["stage"] == "review"
    for key in ("crawl", "inventory", "unify", "happy_path"):
        assert _stage(job, key)["status"] == "done", key
    assert job["analysis"] == "분석 요약"

    job = jm.act(job["id"], "approve")
    assert job["status"] == "done" and job["action"] is None
    assert all(s["status"] == "done" for s in job["stages"])
    assert job["answer"] == "POC 생성 완료"
    assert any("components 진행" in log["message"] for log in job["logs"])


def test_reject_happy_path_stops_at_review(monkeypatch):
    jm = _manager(monkeypatch)
    job = jm.act(jm.start(URL)["id"], "approve")
    job = jm.act(job["id"], "reject")
    assert job["status"] == "stopped"
    assert _stage(job, "review")["status"] == "stopped"
    assert job["action"]["type"] == "stopped"
    assert _stage(job, "scaffold")["status"] == "pending"


def test_analysis_failure_marks_stage_and_offers_retry(monkeypatch):
    jm = _manager(monkeypatch, analyze=_fake_analyze(fail=True))
    job = jm.act(jm.start(URL)["id"], "approve")
    assert job["status"] == "failed"
    assert job["action"]["type"] == "error" and job["action"]["stage"] == "inventory"
    assert _stage(job, "inventory")["status"] == "failed"

    # 재시도: 같은 작업 ID로 처음부터 다시 실행 (다시 H1 승인에서 멈춤)
    monkeypatch.setattr(agent, "analyze_node", _fake_analyze())
    jm._graph = None
    job = jm.act(job["id"], "retry")
    assert job["status"] == "waiting" and _stage(job, "crawl")["status"] == "waiting"
    assert any("다시 실행" in log["message"] for log in job["logs"])


def test_blocked_url_stops_at_guard(monkeypatch):
    jm = _manager(monkeypatch)
    job = jm.start("https://blocked.test/")
    assert job["status"] == "stopped" and job["action"]["stage"] == "guard"


def test_partial_result_offers_action(monkeypatch):
    jm = _manager(monkeypatch, generate=_fake_generate(status="partial"))
    job = jm.act(jm.act(jm.start(URL)["id"], "approve")["id"], "approve")
    assert job["status"] == "partial" and job["action"]["type"] == "partial"


def test_unexpected_exception_is_visible(monkeypatch):
    def boom(state):
        raise RuntimeError("크롤러 연결 실패")
    jm = _manager(monkeypatch, analyze=boom)
    job = jm.start(URL)
    assert job["status"] == "failed" and "크롤러 연결 실패" in job["error"]
    assert job["action"]["type"] == "error"


def test_invalid_actions_are_rejected(monkeypatch):
    jm = _manager(monkeypatch)
    job = jm.start(URL)
    with pytest.raises(ValueError):
        jm.act(job["id"], "retry")  # 승인 대기 중에는 재시도 불가
    with pytest.raises(KeyError):
        jm.act("nope", "approve")


def test_api_maps_errors_to_http(monkeypatch):
    jm = _manager(monkeypatch)
    monkeypatch.setattr(app_module, "_jobs", jm)
    job = app_module.create_job(app_module.JobRequest(url=URL))
    assert app_module.get_job(job["id"])["status"] == "waiting"
    with pytest.raises(HTTPException) as e:
        app_module.get_job("nope")
    assert e.value.status_code == 404
    with pytest.raises(HTTPException) as e:
        app_module.job_action(job["id"], app_module.JobAction(action="retry"))
    assert e.value.status_code == 409
    assert [s["key"] for s in app_module.job_stages()][0] == "guard"
