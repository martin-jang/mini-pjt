"""L2 분석 정확도 채점 (정답 라벨과 결정적 비교). 평가 하네스(T12)와 진행 점검에서 함께 씁니다.

정답(evaluation/golden/variant_groups.json, unification_labels.json)은 합성 픽스처에 주입한 변이 목록에서
자동 생성된 것이라 분석 결과와 독립적입니다.
"""

from __future__ import annotations

import json
from typing import Any

from src.config import ROOT


def _golden() -> tuple[list[dict], dict[str, dict]]:
    g = ROOT / "evaluation" / "golden"
    groups = json.loads((g / "variant_groups.json").read_text(encoding="utf-8"))["groups"]
    labels = {l["group_id"]: l for l in json.loads((g / "unification_labels.json").read_text(encoding="utf-8"))["labels"]}
    return groups, labels


def _norm(v: Any) -> str:
    return str(v).strip().lower()


def match_group(gold: dict, decisions: list[dict]) -> dict | None:
    """정답 그룹의 (화면, 값) 쌍을 모두 포함하는 예측 그룹을 찾습니다. 여러 개면 가장 작은 그룹."""
    need = {(m["screen_id"], _norm(m["value"])) for m in gold["members"]}
    # 컬럼 구성처럼 값이 여러 단어인 경우 대비: '/' 구분 공백 정규화
    norm = lambda v: " / ".join(p.strip() for p in _norm(v).split("/"))
    need = {(s, norm(v)) for s, v in need}
    cands = []
    for d in decisions:
        have = {(m["screen_id"], norm(m["value"])) for m in d["asis_variants"]}
        if need <= have:
            cands.append(d)
    return min(cands, key=lambda d: len(d["asis_variants"])) if cands else None


def score_unification(decisions: list[dict]) -> dict[str, Any]:
    """변이 그룹 recall, 결정 정확도, 과잉 통일 건수, 근거 기재율."""
    groups, labels = _golden()
    rows, found, correct, over = [], 0, 0, 0
    for gold in groups:
        pred = match_group(gold, decisions)
        exp = labels[gold["group_id"]]["expected_decision"]
        got = pred["decision"] if pred else None
        found += pred is not None
        correct += got == exp
        if exp == "keep_variant" and got == "unify":
            over += 1
        rows.append({"golden": gold["group_id"], "matched": pred["group_id"] if pred else None,
                     "expected": exp, "got": got, "standard": pred["standard"] if pred else None})
    with_reason = sum(bool(d.get("reason")) for d in decisions)
    return {
        "variant_group_recall": found / len(groups) if groups else 0.0,
        "decision_accuracy": correct / len(groups) if groups else 0.0,
        "over_unification": over,
        "reason_coverage": with_reason / len(decisions) if decisions else 0.0,
        "rows": rows,
    }
