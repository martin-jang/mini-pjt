"""Day 7 run_eval · compare_eval 재사용 (sds-ax-training/day07/practice/starter/submission.py 에서 복사).

LLM을 호출하지 않는 평가 실행기와 라운드 비교기입니다. '답이 맞았는가'는 호출자가 넘긴 judge가 판정합니다.
"""

from __future__ import annotations

from typing import Any, Callable

# 판정 결과에 쓰는 상태값입니다. 이 셋만 씁니다.
PASS, FAIL, ERROR = "pass", "fail", "error"

_DETAIL_MAX = 200


def run_eval(answer_fn: Callable[[str], Any], eval_set: list[dict],
             judge: Callable[[dict, Any], bool] | None = None) -> dict:
    """평가셋을 전부 돌려 유형별 통과율을 냅니다.

    Args:
        answer_fn: 질문 문자열을 받아 답을 돌려주는 함수. 예외가 날 수 있습니다.
        eval_set: [{"id", "question", "type", ...}] 목록
        judge: (문항, 답) -> 통과 여부. None이면 '답이 비어 있지 않으면 통과'로 봅니다.

    Returns:
        {
          "total": 전체 문항 수,
          "passed": 통과 수,
          "by_type": {유형: {"total": n, "passed": m}},
          "failures": [{"id", "type", "status", "detail"}],
        }

    반드시 지킬 것:
      - answer_fn이 예외를 던져도 전체 실행이 멈추면 안 됩니다.
        그 문항은 status를 ERROR로 기록하고 계속 진행합니다.
    """
    # 판정 함수가 없으면 '답이 비어 있지 않으면 통과'라는 기본 기준을 씁니다.
    judge = judge or _default_judge

    report: dict[str, Any] = {
        "total": 0,
        "passed": 0,
        "by_type": {},
        "failures": [],
        # compare_eval이 '어떤 문항이 통과했는지'를 알 수 있도록 전체 id 목록을 함께 남깁니다.
        # (failures에는 실패 문항만 있어서, 이것이 없으면 평가셋이 바뀐 경우를 구분할 수 없습니다.)
        "ids": [],
    }

    for idx, item in enumerate(eval_set or []):
        # 문항 형식이 깨져 있어도 전체가 멈추지 않게 기본값으로 메웁니다.
        item = item if isinstance(item, dict) else {"question": item}
        qid = item.get("id") or f"#{idx + 1}"           # id가 없으면 위치로 대신 표시
        qtype = item.get("type") or "unknown"
        question = item.get("question", "")

        report["total"] += 1
        report["ids"].append(qid)
        bucket = report["by_type"].setdefault(qtype, {"total": 0, "passed": 0})
        bucket["total"] += 1

        # 1) 답 생성. 예외는 '틀린 답'이 아니라 '터진 코드'라서 ERROR로 따로 남기고 다음 문항으로 갑니다.
        try:
            answer = answer_fn(question)
        except Exception as exc:  # noqa: BLE001 - 한 문항의 실패가 평가 전체를 멈추지 않게 합니다.
            report["failures"].append(_failure(qid, qtype, ERROR, f"answer_fn 예외: {type(exc).__name__}: {exc}"))
            continue

        # 2) 판정. 주입한 judge가 터져도 같은 이유로 ERROR로 격리합니다.
        try:
            ok = bool(judge(item, answer))
        except Exception as exc:  # noqa: BLE001
            report["failures"].append(_failure(qid, qtype, ERROR, f"judge 예외: {type(exc).__name__}: {exc}"))
            continue

        if ok:
            report["passed"] += 1
            bucket["passed"] += 1
        else:
            report["failures"].append(_failure(qid, qtype, FAIL, f"불통과 답변: {_preview(answer)}"))

    return report


def _default_judge(item: dict, answer: Any) -> bool:
    """judge가 없을 때의 기본 판정: 답이 비어 있지 않으면 통과입니다.

    None, 빈 문자열, 공백뿐인 문자열, 빈 목록·딕셔너리는 '비어 있음'으로 봅니다.
    """
    if answer is None:
        return False
    if isinstance(answer, str):
        return bool(answer.strip())
    if isinstance(answer, (list, tuple, dict, set)):
        return bool(answer)
    return True


def _failure(qid: str, qtype: str, status: str, detail: str) -> dict:
    """failures 항목 하나를 규정 스키마({id, type, status, detail})로 만듭니다."""
    return {"id": qid, "type": qtype, "status": status, "detail": detail}


def _preview(answer: Any) -> str:
    """detail에 실을 답변 요약. 빈 답은 빈 답이라고 분명히 적습니다."""
    text = "" if answer is None else str(answer)
    if not text.strip():
        return "(빈 답변)"
    return text if len(text) <= _DETAIL_MAX else text[:_DETAIL_MAX] + "…"


# ══════════════════════════════════════════════════════════════════
# 심화 파트 (3점) — 못 해도 과제는 통과합니다
# ══════════════════════════════════════════════════════════════════

def compare_eval(before: dict, after: dict) -> dict:
    """개선 전후를 비교합니다. LLM을 호출하지 않습니다.

    통과율 총합만 보면 '무엇이 좋아지고 무엇이 깨졌는지'를 알 수 없습니다.
    한 유형을 고치면 다른 유형이 깨지는 일이 실제로 자주 일어납니다.

    Args:
        before, after: run_eval이 반환한 dict

    Returns:
        {
          "fixed":     [before에서 실패했다가 after에서 통과한 문항 id],
          "regressed": [before에서 통과했다가 after에서 실패한 문항 id],
          "delta": after.passed - before.passed,
          "safe": regressed가 비었으면 True,
        }
    """
    before = before or {}
    after = after or {}

    # 실패(FAIL·ERROR 모두) 문항 id 집합입니다.
    before_failed = {f.get("id") for f in before.get("failures", [])}
    after_failed = {f.get("id") for f in after.get("failures", [])}

    # run_eval이 남긴 전체 id 목록에서 실패를 빼면 통과 문항이 됩니다.
    # ids가 없는 결과(다른 구현이 만든 dict)라면 같은 평가셋을 돌렸다고 보고 실패 목록만으로 비교합니다.
    before_ids, after_ids = before.get("ids"), after.get("ids")
    if before_ids is not None and after_ids is not None:
        before_passed = set(before_ids) - before_failed
        after_passed = set(after_ids) - after_failed
        fixed_set = before_failed & after_passed
        regressed_set = before_passed & after_failed
        order = list(after_ids) + [i for i in before_ids if i not in set(after_ids)]
    else:
        fixed_set = before_failed - after_failed
        regressed_set = after_failed - before_failed
        order = [f.get("id") for f in before.get("failures", [])] + \
                [f.get("id") for f in after.get("failures", [])]

    # 결과 순서를 평가셋 순서로 고정해 같은 입력에는 항상 같은 출력이 나오게 합니다.
    def ordered(ids: set) -> list:
        return [i for i in dict.fromkeys(order) if i in ids]

    regressed = ordered(regressed_set)
    return {
        "fixed": ordered(fixed_set),
        "regressed": regressed,
        "delta": int(after.get("passed", 0)) - int(before.get("passed", 0)),
        # 총 통과 수가 늘었어도 하나라도 깨졌으면 안전하지 않습니다. 회귀가 없을 때만 True.
        "safe": not regressed,
    }
