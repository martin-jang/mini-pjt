"""작업(job) 실행기: URL 하나 → 분석 → POC 생성을 백그라운드로 돌리고 단계별 진행을 기록합니다.

작업 화면(static/index.html)이 쓰는 경로입니다. 채점 규약 경로(POST /query)는 그대로 두고,
같은 노드(analyze_node·generate_node)를 묶은 작업 그래프(build_pipeline_graph)를 실행합니다.

- 진행 표시: tracing.step() 과 generate_poc(progress=...) 가 내보내는 이벤트를 10개 단계(STAGES)로 바꿉니다.
- 사용자 개입: 승인(interrupt)·실패가 생긴 경우에만 job["action"] 에 필요한 행동을 적습니다.
  화면은 이 값이 있을 때만 승인/거절·재시도 버튼을 보여 줍니다.
- 동시에 하나의 작업만 실행합니다 (크롤러 세션·output 폴더를 공유하므로).
- 작업 기록은 메모리에만 둡니다 (서버 재시작 시 사라짐). 그래프 상태는 체크포인터에 남습니다.
사이트 고유 값은 없습니다.
"""

from __future__ import annotations

import threading
import time
import uuid
from typing import Any, Callable

from src.guardrails import mask_pii
from src.tracing import add_listener, remove_listener

# 화면에 그릴 단계 (순서 고정). key 는 이벤트 매핑용, label 은 표시용.
STAGES: list[dict[str, str]] = [
    {"key": "guard", "label": "입력 검사", "desc": "URL 허용 도메인·인젝션 검사"},
    {"key": "crawl", "label": "크롤링", "desc": "화면 수집 (로그인 승인 시 로그인 화면 포함)"},
    {"key": "inventory", "label": "화면 인벤토리", "desc": "업무 화면 분류·필드 추출"},
    {"key": "unify", "label": "UI 패턴 통일", "desc": "변이 그룹 묶기·통일 결정"},
    {"key": "happy_path", "label": "핵심 흐름 도출", "desc": "Happy Path 도출·RAG 적재"},
    {"key": "review", "label": "생성 범위 확인", "desc": "덮어쓰기·핵심 흐름 승인"},
    {"key": "scaffold", "label": "프로젝트 골격", "desc": "템플릿 복사·API 계약·MSW"},
    {"key": "components", "label": "공통 컴포넌트", "desc": "LLM 컴포넌트·스토리 생성"},
    {"key": "pages", "label": "화면 코드", "desc": "Happy Path 화면 생성"},
    {"key": "verify", "label": "빌드·검증", "desc": "빌드·규칙·흐름 검증, 자가 수정"},
]
_KEYS = [s["key"] for s in STAGES]

# tracing.step 이름 → 단계 key
_STEP_TO_STAGE = {
    "input_guard": "guard",
    "crawl_site": "crawl",
    "build_screen_inventory": "inventory",
    "decide_unification": "unify",
    "derive_happy_paths": "happy_path",
    "index_documents": "happy_path",
}
# interrupt 종류 → 승인을 기다리는 단계 key
_INTERRUPT_TO_STAGE = {"login": "crawl", "overwrite": "review", "happy_path_confirm": "review"}

_MAX_LOGS = 200


def _now() -> float:
    return round(time.time(), 1)


class JobManager:
    """작업 목록과 실행 스레드를 관리합니다. graph_factory 는 테스트에서 가짜 그래프를 넣기 위한 주입점입니다."""

    def __init__(self, graph_factory: Callable[[], Any], run_async: bool = True):
        self._graph_factory = graph_factory
        self._graph = None
        self._jobs: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()
        self._run_async = run_async  # 테스트에서는 False 로 동기 실행

    # ── 조회 ──
    def graph(self):
        with self._lock:
            if self._graph is None:
                self._graph = self._graph_factory()
        return self._graph

    def get(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return _snapshot(job) if job else None

    def latest(self) -> dict[str, Any] | None:
        with self._lock:
            if not self._jobs:
                return None
            return _snapshot(max(self._jobs.values(), key=lambda j: j["created_at"]))

    def running(self) -> dict[str, Any] | None:
        with self._lock:
            return next((j for j in self._jobs.values() if j["status"] == "running"), None)

    # ── 시작·재개 ──
    def start(self, url: str) -> dict[str, Any]:
        """새 작업을 만들고 실행합니다. 이미 실행 중인 작업이 있으면 ValueError."""
        with self._lock:
            busy = self.running()
            if busy:
                raise ValueError(f"이미 실행 중인 작업이 있습니다 ({busy['id']}). 끝난 뒤 다시 시작해 주세요.")
            job_id = uuid.uuid4().hex[:12]
            self._jobs[job_id] = _new_job(job_id, url)
        self._launch(job_id, {"question": url, "thread_id": job_id, "trace": [], "contexts": [],
                              "answer": "", "status": "ok", "tools": []})
        return self.get(job_id)

    def act(self, job_id: str, action: str, edits: dict[str, Any] | None = None) -> dict[str, Any]:
        """사용자 행동 처리. action: approve / reject (승인 대기 시), retry (실패 시).

        상태에 맞지 않는 행동은 ValueError (예: 승인 대기 아닌데 approve)."""
        from langgraph.types import Command

        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise KeyError(job_id)
            if action in ("approve", "reject"):
                if job["status"] != "waiting":
                    raise ValueError("승인을 기다리는 작업이 아닙니다.")
                stage = job["action"]["stage"]
                job["stages"][stage]["status"] = "running"
                job["stages"][stage]["detail"] = "승인함" if action == "approve" else "거절함"
                self._log(job, f"사용자 {'승인' if action == 'approve' else '거절'}: {job['action']['title']}")
                job["status"], job["action"] = "running", None
                payload: Any = Command(resume={"decision": action, **({"edits": edits} if edits else {})})
            elif action == "retry":
                if job["status"] not in ("failed", "stopped", "partial"):
                    raise ValueError("실패하거나 중단된 작업만 다시 실행할 수 있습니다.")
                busy = self.running()
                if busy:
                    raise ValueError(f"이미 실행 중인 작업이 있습니다 ({busy['id']}).")
                url = job["url"]
                fresh = _new_job(job_id, url)
                fresh["logs"] = job["logs"] + [{"t": _now(), "message": "── 다시 실행 ──"}]
                self._jobs[job_id] = fresh
                # 같은 thread_id 로 새 입력을 넣으면 그래프가 처음부터 다시 시작합니다
                payload = {"question": url, "thread_id": job_id, "trace": [], "contexts": [],
                           "answer": "", "status": "ok", "tools": []}
            else:
                raise ValueError(f"알 수 없는 행동입니다: {action}")
        self._launch(job_id, payload)
        return self.get(job_id)

    # ── 실행 ──
    def _launch(self, job_id: str, payload: Any) -> None:
        if self._run_async:
            threading.Thread(target=self._run, args=(job_id, payload), daemon=True).start()
        else:
            self._run(job_id, payload)

    def _run(self, job_id: str, payload: Any) -> None:
        config = {"configurable": {"thread_id": job_id}}
        add_listener(job_id, lambda ev, name, data: self._on_event(job_id, ev, name, data))
        try:
            graph = self.graph()
            interrupted = None
            for update in graph.stream(payload, config, stream_mode="updates"):
                if "__interrupt__" in update:
                    interrupted = update["__interrupt__"][0].value
                for node, out in update.items():
                    if node == "analyze" and isinstance(out, dict) and out.get("status") != "failed":
                        with self._lock:
                            self._jobs[job_id]["analysis"] = out.get("answer", "")
            values = graph.get_state(config).values
            if interrupted is not None:
                self._wait_for_approval(job_id, interrupted)
            else:
                self._finish(job_id, values)
        except Exception as e:  # 예상 못 한 오류도 화면에 보이게 (조용한 실패 금지)
            with self._lock:
                job = self._jobs[job_id]
                stage = _current_stage(job) or "guard"
                job["stages"][stage]["status"] = "failed"
                msg = mask_pii(f"{type(e).__name__}: {e}")[:500]
                job["stages"][stage]["detail"] = msg
                job["status"], job["error"] = "failed", msg
                job["action"] = {"type": "error", "stage": stage, "title": "예상하지 못한 오류", "message": msg}
                self._log(job, f"오류: {msg}")
        finally:
            remove_listener(job_id)
            with self._lock:
                self._jobs[job_id]["updated_at"] = _now()

    def _wait_for_approval(self, job_id: str, pending: dict[str, Any]) -> None:
        with self._lock:
            job = self._jobs[job_id]
            stage = _INTERRUPT_TO_STAGE.get(pending.get("type"), _current_stage(job) or "review")
            # 승인 단계 이전 단계는 모두 끝난 것으로 표시 (예: H4 덮어쓰기 확인 시점)
            for k in _KEYS[:_KEYS.index(stage)]:
                if job["stages"][k]["status"] in ("pending", "running"):
                    job["stages"][k]["status"] = "done"
            job["stages"][stage]["status"] = "waiting"
            job["status"] = "waiting"
            titles = {"login": "데모 계정 로그인 승인", "overwrite": "기존 결과물 덮어쓰기 승인",
                      "happy_path_confirm": "핵심 업무 흐름 확인"}
            job["action"] = {"type": "approval", "stage": stage, "kind": pending.get("type"),
                             "title": titles.get(pending.get("type"), "승인 필요"),
                             "message": pending.get("message", "승인이 필요합니다."),
                             "detail": {k: v for k, v in pending.items() if k not in ("type", "message")}}
            self._log(job, f"승인 대기: {job['action']['title']}")

    def _finish(self, job_id: str, values: dict[str, Any]) -> None:
        with self._lock:
            job = self._jobs[job_id]
            status = values.get("status", "ok")
            answer = values.get("answer", "")
            job["answer"] = answer
            job["tools"] = values.get("tools", [])
            reached_verify = job["stages"]["verify"]["status"] in ("done", "failed")
            # 실패·중단 위치: 입력 단계에서 막혔으면 guard, 아니면 진행 중이던(또는 마지막으로 움직인) 단계
            blocked_at_input = values.get("intent") == "blocked" or not values.get("url")
            where = "guard" if blocked_at_input else (_current_stage(job) or job.get("last_stage") or "guard")
            if status == "failed":
                stage = where
                job["stages"][stage]["status"] = "failed"
                job["stages"][stage]["detail"] = answer[:300]
                job["status"], job["error"] = "failed", answer
                job["action"] = {"type": "error", "stage": stage, "title": f"{_label(stage)} 단계 실패",
                                 "message": answer}
            elif reached_verify:
                job["status"] = "partial" if status == "partial" else "done"
                if status == "partial":
                    job["action"] = {"type": "partial", "stage": "verify", "title": "일부 항목 실패",
                                     "message": "빌드는 됐지만 일부 검증이 실패했습니다. 결과를 확인하거나 다시 실행해 주세요."}
            else:
                # 가드 차단·승인 거절 등으로 생성 전에 끝남
                stage = where
                job["stages"][stage]["status"] = "stopped"
                job["stages"][stage]["detail"] = answer[:300]
                job["status"] = "stopped"
                job["action"] = {"type": "stopped", "stage": stage, "title": "작업이 중단되었습니다", "message": answer}
            for k in _KEYS:
                if job["stages"][k]["status"] == "running":
                    job["stages"][k]["status"] = "done"
            self._log(job, f"작업 종료: {job['status']}")

    # ── 진행 이벤트 → 단계 상태 ──
    def _on_event(self, job_id: str, event: str, name: str, data: dict[str, Any]) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            job["updated_at"] = _now()
            if event == "log":
                self._log(job, data.get("message", ""))
                return
            if event == "stage":  # generate_poc 세부 단계
                st = data.get("state")
                if name not in job["stages"]:
                    return
                if st == "start":
                    self._mark_before(job, name)
                    self._set(job, name, "running", _stage_detail(name, data))
                elif st == "end":
                    self._set(job, name, "done", _stage_detail(name, data))
                elif st == "fail":
                    self._set(job, name, "failed", data.get("error", "실패"))
                elif st == "round":
                    detail = (f"검증 {data.get('round')}회차: 빌드 {'성공' if data.get('app_ok') else '실패'}, "
                              f"규칙 위반 {data.get('violations')}건, 흐름 {'통과' if data.get('flow_ok') else '실패'}")
                    job["stages"][name]["detail"] = detail
                    self._log(job, detail)
                return
            stage = _STEP_TO_STAGE.get(name)
            if stage is None:
                if name == "generate_poc" and event == "start":
                    self._mark_before(job, "scaffold")
                return
            if event == "start":
                self._mark_before(job, stage)
                if job["stages"][stage]["status"] != "running":
                    self._set(job, stage, "running", None)
            elif event == "end":
                if data.get("error"):
                    self._set(job, stage, "failed", data["error"])
                elif name != "derive_happy_paths":  # 핵심 흐름 단계는 RAG 적재까지 끝나야 완료
                    self._set(job, stage, "done", data.get("output"))
                else:
                    job["stages"][stage]["detail"] = data.get("output")

    def _mark_before(self, job: dict[str, Any], stage: str) -> None:
        """stage 를 시작하면 앞선 단계 중 진행 중·대기였던 것은 완료로 정리합니다."""
        for k in _KEYS[:_KEYS.index(stage)]:
            if job["stages"][k]["status"] in ("pending", "running", "waiting"):
                job["stages"][k]["status"] = "done"

    def _set(self, job: dict[str, Any], stage: str, status: str, detail: Any) -> None:
        s = job["stages"][stage]
        if status == "running" and s["started_at"] is None:
            s["started_at"] = _now()
        if status in ("done", "failed"):
            s["ended_at"] = _now()
        s["status"] = status
        job["last_stage"] = stage
        if detail is not None:
            s["detail"] = mask_pii(detail if isinstance(detail, str) else str(detail))[:300]
        self._log(job, f"[{_label(stage)}] {_STATUS_KO.get(status, status)}"
                       + (f" — {s['detail']}" if detail is not None and s["detail"] else ""))

    def _log(self, job: dict[str, Any], message: str) -> None:
        job["logs"].append({"t": _now(), "message": mask_pii(message)[:400]})
        del job["logs"][:-_MAX_LOGS]


_STATUS_KO = {"running": "시작", "done": "완료", "failed": "실패", "waiting": "승인 대기", "stopped": "중단"}


def _label(key: str) -> str:
    return next(s["label"] for s in STAGES if s["key"] == key)


def _stage_detail(name: str, data: dict[str, Any]) -> str | None:
    items, problems = data.get("items"), data.get("problems")
    if name == "scaffold" and data.get("pages") is not None:
        return f"화면 {data['pages']}개 라우트, 컴포넌트 명세 {data['components']}개"
    if items is not None:
        text = f"{len(items)}개: {', '.join(map(str, items))}"
        if problems:
            text += f" (수정 필요 {len(problems)}개)"
        return text
    if data.get("status"):
        return f"최종 상태 {data['status']}"
    return None


def _current_stage(job: dict[str, Any]) -> str | None:
    """진행 중이거나 승인 대기 중인 마지막 단계."""
    active = [k for k in _KEYS if job["stages"][k]["status"] in ("running", "waiting")]
    return active[-1] if active else None


def _new_job(job_id: str, url: str) -> dict[str, Any]:
    return {"id": job_id, "url": url, "status": "running", "created_at": _now(), "updated_at": _now(),
            "stages": {s["key"]: {"status": "pending", "detail": None, "started_at": None, "ended_at": None}
                       for s in STAGES},
            "action": None, "last_stage": None, "analysis": "", "answer": "", "error": None, "tools": [], "logs": []}


def _snapshot(job: dict[str, Any]) -> dict[str, Any]:
    """화면에 내려줄 사본. 단계는 STAGES 순서의 목록으로 바꿉니다."""
    return {**{k: v for k, v in job.items() if k != "stages"},
            "stages": [{**meta, **job["stages"][meta["key"]]} for meta in STAGES],
            "logs": list(job["logs"][-80:])}
