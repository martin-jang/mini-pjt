"""Analyst ③ Happy Path + data-testid (T09, 도구 derive_happy_paths).

화면 전환 그래프에서 이 시스템의 핵심 업무 흐름을 뽑고, 단계마다 생성 앱이 지켜야 할 data-testid 계약을
만듭니다 (결정 D10·D11·D14).

역할 분담:
  - LLM: 후보 화면·전환 정보를 보고 핵심 흐름의 '화면 순서'와 단계별 사용자 행동만 고름
  - 코드: 근거 검증 (모든 화면이 수집됐는지, 단계 사이가 실제로 이어지는지, 입력 흐름은 결과 화면 근거가 있는지)
          + data-testid 를 결정적으로 생성 (생성 앱·Verifier·Playwright가 이 ID만 사용)
근거 없는 흐름은 버립니다. 남은 흐름이 0개면 생성을 멈추라는 사유를 돌려줍니다 (D1x).
"""

from __future__ import annotations

import json
import re
from typing import Any, Literal

from pydantic import BaseModel, Field

from src.analyst import naming
from src.analyst.inventory import Screen, load_inventory
from src.config import path as cfg_path
from src.guardrails import DATA_BLOCK_RULE, wrap_as_data
from src.llm import default_llm, invoke_structured

MAX_FLOWS = 3


class ProposedStep(BaseModel):
    screen_id: str = Field(description="후보 목록에 있는 screen_id 그대로")
    action: Literal["login", "view", "fill_submit", "navigate"] = Field(
        description="이 화면에서 사용자가 하는 일. login=로그인 입력, view=내용 확인, "
                    "fill_submit=값 입력 후 제출, navigate=다음 화면으로 이동(링크·메뉴 클릭)")
    description: str = Field(description="사용자 행동을 한국어 한 문장으로")


class ProposedFlow(BaseModel):
    name: str = Field(description="흐름 이름 (한국어, 예: 계좌 조회)")
    why: str = Field(description="이 흐름이 핵심 업무인 이유 (한국어 한 문장)")
    steps: list[ProposedStep]


class FlowProposal(BaseModel):
    flows: list[ProposedFlow]


_PROMPT = """당신은 레거시 시스템의 핵심 업무 흐름을 찾는 분석가입니다.
아래는 업무 화면 목록과 화면 간 이동(links_to)입니다. 이 시스템 사용자가 가장 자주·가장 중요하게 쓰는
핵심 업무 흐름을 최대 {max_flows}개 고르세요.

규칙:
- 반드시 목록에 있는 screen_id만 쓰세요. 목록에 없는 화면을 상상해서 넣지 마세요.
- 로그인이 필요한 화면으로 가는 흐름은 로그인 화면(kind=인증 또는 로그인 입력란이 있는 화면)에서 시작하세요.
- 값을 입력해 제출하는 흐름은 결과 화면(kind=결과)이 목록에 있을 때만 고르세요. 결과 화면이 없으면 고르지 마세요.
- 각 단계는 이전 단계 화면의 links_to 에 있거나, 로그인 직후 이동하는 첫 화면이어야 합니다.

{rule}

{data}
"""


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:24] or "step"


def _is_login_screen(s: Screen) -> bool:
    return s.kind == "인증" or any(f.type == "password" for f in s.fields)


def _edges(screens: list[Screen]) -> dict[str, set[str]]:
    """화면 전환 그래프. 링크 + (로그인 화면 → 로그인 필요 화면) + (입력 화면 → 그 결과 화면)."""
    by_id = {s.screen_id: s for s in screens}
    edges = {s.screen_id: set(s.links_to) for s in screens}
    for s in screens:
        if _is_login_screen(s):
            edges[s.screen_id] |= {t.screen_id for t in screens if t.requires_login and not t.result_of}
        if s.result_of:  # 결과 화면은 같은 URL 패턴의 입력 화면에서 제출로 이어짐
            base = s.screen_id.split("__result")[0]
            if base in by_id:
                edges[base].add(s.screen_id)
    return edges


def validate_flow(flow: ProposedFlow, screens: list[Screen]) -> tuple[bool, str]:
    """흐름이 수집된 근거만으로 이뤄졌는지 검사합니다. (유효 여부, 사유)."""
    by_id = {s.screen_id: s for s in screens}
    edges = _edges(screens)
    ids = [st.screen_id for st in flow.steps]
    if len(ids) < 2:
        return False, "단계가 2개 미만"
    missing = [i for i in ids if i not in by_id]
    if missing:
        return False, f"수집되지 않은 화면 포함: {missing}"
    for a, b in zip(ids, ids[1:]):
        if b not in edges.get(a, set()):
            return False, f"이어지지 않는 단계: {a} → {b}"
    for st in flow.steps:
        if st.action == "fill_submit":
            nxt = ids[ids.index(st.screen_id) + 1] if st.screen_id != ids[-1] else None
            if not nxt or not by_id[nxt].result_of:
                return False, f"제출 결과 화면 근거 없음: {st.screen_id}"
    return True, "ok"


def build_contract(flow_no: int, flow: ProposedFlow, screens: list[Screen]) -> dict[str, Any]:
    """검증된 흐름에 data-testid 계약을 붙입니다 (결정적, 화면 단위 ID).

    여러 흐름이 같은 화면(예: 로그인)을 지나도 같은 ID를 쓰도록 화면 단위로 만듭니다.
      page_testid  : 단계 화면의 최상위 요소
      action_testid: 다음 단계로 넘어가는 요소. 제출·로그인은 '{slug}-submit', 이동은 '{slug}-to-{다음 slug}'
      fields       : login/fill_submit 단계에서 채울 입력 필드와 testid
    """
    by_id = {s.screen_id: s for s in screens}
    slugs = naming.slug_map(screens)  # 코드 생성(API 계약)과 같은 규칙 · 같은 화면 목록(업무 화면)
    fid = f"hp{flow_no}"
    steps = []
    for n, st in enumerate(flow.steps, start=1):
        s = by_id[st.screen_id]
        slug = slugs[s.screen_id]
        nxt = by_id[flow.steps[n].screen_id] if n < len(flow.steps) else None
        next_slug = slugs[nxt.screen_id] if nxt else None
        fields = []
        if st.action in ("login", "fill_submit"):
            named = [f for f in s.fields if f.name]
            if st.action == "login":
                named = [f for f in named if f.type == "password" or f.name in ("username", "user", "id", "email")]
            fields = [{"name": f.name, "label": f.label, "type": f.type, "testid": naming.field_testid(slug, f.name)}
                      for f in named]
        if not nxt:
            action_testid = None
        elif st.action in ("login", "fill_submit"):
            action_testid = naming.submit_testid(slug)
        else:
            action_testid = naming.link_testid(slug, next_slug)
        steps.append({
            "step_id": f"{fid}-s{n}", "screen_id": s.screen_id, "screen_title": s.title_ko or s.title,
            "slug": slug, "action": st.action, "description": st.description,
            "page_testid": naming.page_testid(slug), "action_testid": action_testid,
            "next_slug": next_slug, "fields": fields,
        })
    return {"flow_id": fid, "name": flow.name, "why": flow.why, "steps": steps}


def reassign_testids(domain: str) -> list[dict[str, Any]]:
    """저장된 happy_paths.json 의 testid 를 현재 규칙으로 다시 계산합니다 (LLM 재호출 없이)."""
    screens = [s for s in load_inventory(domain) if s.is_business]  # derive_happy_paths·API 계약과 같은 화면 목록
    p = happy_paths_path(domain)
    data = json.loads(p.read_text(encoding="utf-8"))
    flows = []
    for n, f in enumerate(data["flows"], start=1):
        pf = ProposedFlow(name=f["name"], why=f["why"],
                          steps=[ProposedStep(screen_id=s["screen_id"], action=s["action"], description=s["description"])
                                 for s in f["steps"]])
        flows.append(build_contract(n, pf, screens))
    data["flows"] = flows
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return flows


def _candidate_payload(screens: list[Screen]) -> list[dict[str, Any]]:
    edges = _edges(screens)
    return [{"screen_id": s.screen_id, "title": s.title, "kind": s.kind, "purpose": s.purpose,
             "requires_login": s.requires_login, "links_to": sorted(edges[s.screen_id])} for s in screens]


def happy_paths_path(domain: str):
    return cfg_path("analysis") / domain / "happy_paths.json"


def derive_happy_paths(domain: str, llm=None) -> dict[str, Any]:
    """핵심 업무 흐름과 data-testid 계약을 만들어 저장합니다.

    언제 쓰나: 인벤토리(T07) 이후, 생성 전에. 결과는 H3에서 사용자 확인을 받습니다.
    언제 쓰지 않나: 인벤토리가 없을 때 → 안내 반환.
    """
    screens = [s for s in load_inventory(domain) if s.is_business]
    if not screens:
        return {"error": f"'{domain}' 인벤토리가 없습니다. 먼저 화면 인벤토리를 만드세요.", "flows": []}
    llm = llm or default_llm()
    data = wrap_as_data(json.dumps(_candidate_payload(screens), ensure_ascii=False))
    proposal = invoke_structured(llm, FlowProposal,
                                 _PROMPT.format(max_flows=MAX_FLOWS, rule=DATA_BLOCK_RULE, data=data))
    valid, rejected = [], []
    for f in proposal.flows[:MAX_FLOWS]:
        ok, reason = validate_flow(f, screens)
        if ok:
            valid.append(f)
        else:
            rejected.append({"name": f.name, "reason": reason})
    # 다른 흐름의 앞부분과 똑같은 흐름은 중복이므로 뺍니다 (예: 로그인→목록 ⊂ 로그인→목록→상세)
    seqs = [[st.screen_id for st in f.steps] for f in valid]
    kept = []
    for i, f in enumerate(valid):
        dup_of = next((valid[j].name for j, other in enumerate(seqs)
                       if j != i and len(other) > len(seqs[i]) and other[:len(seqs[i])] == seqs[i]), None)
        if dup_of:
            rejected.append({"name": f.name, "reason": f"'{dup_of}' 흐름에 포함되는 중복"})
        else:
            kept.append(f)
    flows = [build_contract(n, f, screens) for n, f in enumerate(kept, start=1)]
    result: dict[str, Any] = {"domain": domain, "flows": flows, "rejected": rejected}
    if not flows:
        result["error"] = "근거가 있는 핵심 업무 흐름을 찾지 못해 생성을 진행할 수 없습니다."
    out = happy_paths_path(domain)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def load_happy_paths(domain: str) -> list[dict[str, Any]]:
    p = happy_paths_path(domain)
    return json.loads(p.read_text(encoding="utf-8"))["flows"] if p.exists() else []
