"""Analyst ② 통일 결정 (T08, 도구 decide_unification).

변이 그룹마다 TOBE 표준을 추론하고 통일 / 변형 유지 / 보류로 분류해 근거·확신도와 함께 기록합니다.

표준 추론 순서 (SERVICE.md):
  ① 다수결  ② 현대 UX 관례·Ant Design 기본 패턴  ③ 이미 정한 다른 표준과의 일관성
과잉 통일 방지는 코드로 강제합니다: 동작·정보 차이를 만드는 그룹(PROTECTED_TYPES)은 LLM이 '통일'이라 답해도
'변형 유지'로 되돌리고 그 사실을 근거에 남깁니다. 결정은 data/analysis/{domain}/unification_decisions.json 에
저장되고 RAG 근거로도 적재됩니다(T10).
"""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, Field

from src.analyst.inventory import load_inventory
from src.analyst.variants import PROTECTED_TYPES, VariantGroup, collect_groups, majority
from src.config import path as cfg_path
from src.guardrails import DATA_BLOCK_RULE, wrap_as_data
from src.llm import default_llm, invoke_structured

Decision = Literal["unify", "keep_variant", "hold"]


class GroupDecision(BaseModel):
    group_id: str = Field(description="입력의 group_id 그대로")
    role: str = Field(description="이 요소들의 공통 역할을 한국어로 짧게 (예: 검색 실행 버튼)")
    decision: Decision = Field(description="unify=의미가 같고 표현만 다름 → 표준으로 통일 / "
                                           "keep_variant=업무 의미가 있는 차이 → 공통 컴포넌트 옵션으로 유지 / "
                                           "hold=판단 근거 부족 또는 통일하면 동작이 바뀔 수 있음 → 사용자 확인")
    standard: str | None = Field(description="unify일 때 TOBE 표준 값 (라벨·형식·배치). 그 외에는 null")
    basis: Literal["majority", "ux_convention", "consistency", "business_meaning", "insufficient"] = Field(
        description="결정의 주된 근거")
    reason: str = Field(description="결정 근거를 한국어 한두 문장으로")
    confidence: float = Field(ge=0, le=1, description="결정 확신도 0~1")


class Decisions(BaseModel):
    decisions: list[GroupDecision]


_PROMPT = """당신은 레거시 화면을 차세대 표준 UI로 전환하는 UX 아키텍트입니다.
아래 변이 그룹은 여러 화면에서 같은 역할로 추정되는 UI 요소들이 서로 다르게 표현된 사례입니다.
그룹마다 통일 여부와 표준을 결정하세요.

결정 원칙:
1. 표준은 ① 다수결 ② 현대 UX 관례와 Ant Design 기본 패턴(예: 날짜 YYYY-MM-DD, 조회조건은 목록 위) ③ 다른 표준과의 일관성 순으로 정합니다.
2. 의미가 같고 라벨·형식·배치만 다르면 unify 입니다.
3. 제출 전 확인 단계, 검증 시점, 결과 표시 방식, 표시하는 정보(합계 행 등)처럼 동작이나 업무 정보가 달라지는 차이는
   절대 unify 하지 말고 keep_variant 또는 hold 로 분류하세요.
4. 같은 그룹에 묶였어도 실제로 서로 다른 업무 동작(예: 이체 실행과 대출 신청)이면 라벨을 통일하지 말고 keep_variant 입니다.
5. 근거가 부족하면 hold 입니다.

{rule}

{data}
"""


def _group_payload(g: VariantGroup) -> dict[str, Any]:
    return {"group_id": g.group_id, "element_type": g.element_type, "role_hint": g.role_hint,
            "majority": majority([m.value for m in g.members]),
            "members": [{"screen_id": m.screen_id, "value": m.value, "context": m.context[:120]} for m in g.members]}


def decide(groups: list[VariantGroup], llm=None) -> list[dict[str, Any]]:
    """변이 그룹 목록에 대한 결정을 만듭니다 (LLM 1회 + 과잉 통일 방지 규칙)."""
    if not groups:
        return []
    llm = llm or default_llm()
    data = wrap_as_data(json.dumps([_group_payload(g) for g in groups], ensure_ascii=False))
    out = invoke_structured(llm, Decisions, _PROMPT.format(rule=DATA_BLOCK_RULE, data=data))
    by_id = {d.group_id: d for d in out.decisions}

    records = []
    for g in groups:
        d = by_id.get(g.group_id) or GroupDecision(
            group_id=g.group_id, role=g.role_hint or "미상", decision="hold", standard=None,
            basis="insufficient", reason="모델이 이 그룹에 대한 결정을 돌려주지 않아 보류합니다.", confidence=0.0)
        guard_note = None
        if g.element_type in PROTECTED_TYPES and d.decision == "unify":
            guard_note = (f"과잉 통일 방지 규칙: '{g.element_type}' 요소는 동작·정보 차이를 만들므로 "
                          f"모델의 unify 결정({d.standard})을 keep_variant 로 되돌림")
            d = d.model_copy(update={"decision": "keep_variant", "standard": None, "basis": "business_meaning"})
        records.append({
            "group_id": g.group_id, "element_type": g.element_type, "role": d.role,
            "asis_variants": [{"screen_id": m.screen_id, "value": m.value} for m in g.members],
            "decision": d.decision, "standard": d.standard, "basis": d.basis, "reason": d.reason,
            "confidence": round(d.confidence, 2), "guard_note": guard_note,
        })
    return records


def decisions_path(domain: str):
    return cfg_path("analysis") / domain / "unification_decisions.json"


def decide_unification(domain: str, llm=None, embeddings=None) -> dict[str, Any]:
    """도메인 인벤토리에서 변이 그룹을 찾고 통일 결정을 저장합니다.

    언제 쓰나: 인벤토리(T07)가 만들어진 뒤, 공통 컴포넌트 설계 전에.
    언제 쓰지 않나: 인벤토리가 없을 때 → 인벤토리부터 만들라는 안내.
    """
    screens = load_inventory(domain)
    if not screens:
        return {"error": f"'{domain}' 인벤토리가 없습니다. 먼저 화면 인벤토리를 만드세요.", "decisions": []}
    groups = collect_groups(screens, embeddings=embeddings)
    records = decide(groups, llm=llm)
    result = {
        "domain": domain, "group_count": len(records),
        "summary": {k: sum(r["decision"] == k for r in records) for k in ("unify", "keep_variant", "hold")},
        "decisions": records,
    }
    out = decisions_path(domain)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def load_decisions(domain: str) -> list[dict[str, Any]]:
    p = decisions_path(domain)
    return json.loads(p.read_text(encoding="utf-8"))["decisions"] if p.exists() else []
