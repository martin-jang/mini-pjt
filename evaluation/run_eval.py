"""평가 하네스 (T12): test_queries.json 을 /query 에 돌려 L1~L4 지표를 한 번에 산출합니다.

실행:
    .venv\\Scripts\\python evaluation/run_eval.py --round 1
    .venv\\Scripts\\python evaluation/run_eval.py --round 1 --no-ragas      # RAGAS 생략 (빠른 확인)
    .venv\\Scripts\\python evaluation/run_eval.py --round 1 --ids 2,6,10   # 일부 케이스만

구성 (SERVICE.md §5 평가 운영 원칙, 결정 D15):
  - 실행: Day 7 run_eval 재사용. 문항마다 새 thread_id 로 /query 본체(app.run_query)를 호출
  - 승인: auto_approve=true → 자동 승인 / false·null → 멈춘 상태 그대로 판정 (guardrail은 승인 요청 자체가 정답)
  - 판정: LLM-as-Judge(expected_traits 충족·forbidden 위반) + 결정적 검사(expected_tools, 승인 요청 상태)
  - RAGAS 4종: L1 질의 케이스 중 reference 가 있고 negative 가 아닌 케이스만
  - L2: 분석 정답 비교 (src/analyst/score.py 등), L4: guardrail 케이스 통과율
  - 평가는 스냅샷 재생 모드로 실행 (config crawl.snapshot_mode=replay)
결과: evaluation/results/round{N}.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pydantic import BaseModel, Field  # noqa: E402

from src.llm import default_llm, invoke_structured  # noqa: E402
from src.reuse.day07_eval import compare_eval, run_eval  # noqa: E402

EVAL_DIR = ROOT / "evaluation"
MAX_APPROVALS = 5


# ──────────────────────────────────────────────────────────────────
# 답 생성 (승인 정책 포함)
# ──────────────────────────────────────────────────────────────────


def ask(item: dict[str, Any], graph) -> dict[str, Any]:
    """한 문항을 /query 본체로 실행합니다. auto_approve=true 면 승인 요청에 자동 승인."""
    from app import QueryRequest, run_query

    started = time.perf_counter()
    r = run_query(QueryRequest(question=item["input"]), graph=graph)
    approvals = 0
    while r.status == "needs_approval" and item.get("auto_approve") is True and approvals < MAX_APPROVALS:
        approvals += 1
        r = run_query(QueryRequest(question="승인", thread_id=r.thread_id, approval={"decision": "approve"}), graph=graph)
    out = r.model_dump()
    out["approvals"] = approvals
    out["elapsed_s"] = round(time.perf_counter() - started, 1)
    return out


# ──────────────────────────────────────────────────────────────────
# 판정 (LLM-as-Judge + 결정적 검사)
# ──────────────────────────────────────────────────────────────────


class TraitCheck(BaseModel):
    item: str
    ok: bool
    why: str = Field(description="한국어 한 문장")


class Verdict(BaseModel):
    traits: list[TraitCheck] = Field(description="expected_traits 항목마다 충족 여부")
    violations: list[TraitCheck] = Field(description="forbidden 항목마다 위반 여부 (ok=true 면 위반함)")


_JUDGE = """당신은 에이전트 응답 채점관입니다. 아래 응답이 기대 특성을 충족하는지, 금지 항목을 위반했는지 판정하세요.
응답 상태(status)와 승인 대기 내용(pending)도 응답의 일부입니다. status=needs_approval 이면 에이전트가 실행 전에
사용자 승인을 요청한 것입니다. 엄격하게 판정하되, 표현이 달라도 의미가 같으면 충족으로 봅니다.

[질문] {question}
[응답 status] {status}
[승인 대기 내용 pending] {pending}
[응답 answer]
{answer}

[기대 특성 expected_traits] {traits}
[금지 항목 forbidden] {forbidden}
"""


def judge_case(item: dict[str, Any], resp: dict[str, Any], llm=None) -> dict[str, Any]:
    llm = llm or default_llm()
    prompt = _JUDGE.format(question=item["input"], status=resp.get("status"),
                           pending=json.dumps(resp.get("pending"), ensure_ascii=False)[:800],
                           answer=(resp.get("answer") or "")[:3000],
                           traits=item.get("expected_traits"), forbidden=item.get("forbidden"))
    v = invoke_structured(llm, Verdict, prompt)
    traits_ok = all(t.ok for t in v.traits) and len(v.traits) >= len(item.get("expected_traits", []))
    violated = [t.item for t in v.violations if t.ok]
    expected_tools = set(item.get("expected_tools") or [])
    tools_ok = expected_tools <= set(resp.get("tools") or []) if expected_tools else True
    # guardrail 케이스에서 needs_approval 을 기대하면 상태로 결정적 확인
    status_ok = True
    if any("needs_approval" in t for t in item.get("expected_traits", [])):
        status_ok = resp.get("status") == "needs_approval"
    passed = traits_ok and not violated and tools_ok and status_ok
    return {"passed": passed, "traits": [t.model_dump() for t in v.traits], "violated": violated,
            "tools_ok": tools_ok, "missing_tools": sorted(expected_tools - set(resp.get("tools") or [])),
            "status_ok": status_ok}


# ──────────────────────────────────────────────────────────────────
# RAGAS
# ──────────────────────────────────────────────────────────────────


def ragas_scores(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """L1 질의 케이스에 RAGAS 4종을 계산합니다. Bedrock LLM·임베딩을 그대로 씁니다."""
    from langchain_aws import BedrockEmbeddings
    from ragas import EvaluationDataset, SingleTurnSample, evaluate
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.llms import LangchainLLMWrapper
    from ragas.metrics import Faithfulness, LLMContextPrecisionWithReference, LLMContextRecall, ResponseRelevancy

    from src.llm import EMBED_ID, EMBED_REGION

    samples = [SingleTurnSample(user_input=r["input"], response=r["answer"], reference=r["reference"],
                                retrieved_contexts=[c["text"] for c in r["contexts"]] or [""]) for r in rows]
    if not samples:
        return {"n": 0}
    llm = LangchainLLMWrapper(default_llm(max_tokens=4096))
    emb = LangchainEmbeddingsWrapper(BedrockEmbeddings(model_id=EMBED_ID, region_name=EMBED_REGION))
    metrics = [LLMContextRecall(), LLMContextPrecisionWithReference(), Faithfulness(), ResponseRelevancy()]
    result = evaluate(EvaluationDataset(samples=samples), metrics=metrics, llm=llm, embeddings=emb,
                      show_progress=False, raise_exceptions=False)
    df = result.to_pandas()
    names = {"context_recall": "context_recall", "llm_context_precision_with_reference": "context_precision",
             "faithfulness": "faithfulness", "answer_relevancy": "answer_relevancy"}
    summary = {"n": len(samples)}
    for col, name in names.items():
        if col in df.columns:
            vals = df[col].dropna()
            summary[name] = round(float(vals.mean()), 3) if len(vals) else None
    summary["per_case"] = [{"id": rows[i]["id"], **{names[c]: (None if df[c].isna()[i] else round(float(df[c][i]), 3))
                                                    for c in names if c in df.columns}} for i in range(len(rows))]
    return summary


# ──────────────────────────────────────────────────────────────────
# L2 분석 정확도
# ──────────────────────────────────────────────────────────────────


def l2_scores() -> dict[str, Any]:
    from src.analyst.happy_path import load_happy_paths
    from src.analyst.score import score_unification
    from src.analyst.unification import load_decisions

    gold = json.loads((EVAL_DIR / "golden" / "screens.json").read_text(encoding="utf-8"))
    gold_fields = json.loads((EVAL_DIR / "golden" / "fields.json").read_text(encoding="utf-8"))
    inv = {}
    for dom in ("parabank.parasoft.com", "legacy-fixture.example"):
        p = ROOT / "data" / "analysis" / dom / "screen_inventory.json"
        inv[dom] = json.loads(p.read_text(encoding="utf-8"))["screens"] if p.exists() else []
    biz = {s["screen_id"] for ss in inv.values() for s in ss if s["is_business"]}
    g_all = set(gold["real"]) | set(gold["fixture"])
    found_fields = {s["screen_id"]: {f["name"] for f in s["fields"]} for ss in inv.values() for s in ss}
    f_total = sum(len(v) for v in gold_fields.values())
    f_hit = sum(len(set(v) & found_fields.get(k, set())) for k, v in gold_fields.items())
    uni = score_unification(load_decisions("legacy-fixture.example"))
    flows = load_happy_paths("parabank.parasoft.com")
    seqs = [[s["screen_id"] for s in f["steps"]] for f in flows]
    expected_flows = [("overview", "activity"), ("transfer", "__result")]
    hp_fit = sum(any(any(a in x for x in q) and any(b in x for x in q) for q in seqs) for a, b in expected_flows)
    return {"screen_recall": round(len(biz & g_all) / len(g_all), 3), "field_recall": round(f_hit / f_total, 3),
            "variant_group_recall": round(uni["variant_group_recall"], 3),
            "decision_accuracy": round(uni["decision_accuracy"], 3), "over_unification": uni["over_unification"],
            "reason_coverage": round(uni["reason_coverage"], 3), "happy_path_fit": f"{hp_fit}/{len(expected_flows)}"}


# ──────────────────────────────────────────────────────────────────
# 실행
# ──────────────────────────────────────────────────────────────────


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--round", type=int, required=True)
    ap.add_argument("--ids", default="")
    ap.add_argument("--no-ragas", action="store_true")
    args = ap.parse_args()

    from app import get_graph
    from src.config import settings

    if settings()["crawl"]["snapshot_mode"] != "replay":
        print("⚠ 평가는 스냅샷 재생 모드에서 실행해야 재현됩니다 (config crawl.snapshot_mode=replay).")
    cases = json.loads((EVAL_DIR / "test_queries.json").read_text(encoding="utf-8"))
    if args.ids:
        wanted = {int(x) for x in args.ids.split(",")}
        cases = [c for c in cases if c["id"] in wanted]
    # 분석·생성 케이스는 공유 분석 산출물·결과물을 다시 만들므로, 다른 케이스의 근거가 실행 도중 바뀌지 않게 맨 뒤에 실행
    from src.agent import route_question
    cases.sort(key=lambda c: route_question(c["input"]) in ("analyze", "generate"))
    references = json.loads((EVAL_DIR / "golden" / "references.json").read_text(encoding="utf-8"))["references"]
    graph = get_graph()
    by_question = {c["input"]: c for c in cases}
    records: dict[int, dict[str, Any]] = {}

    def answer_fn(question: str) -> dict[str, Any]:
        item = by_question[question]
        resp = ask(item, graph)
        verdict = judge_case(item, resp)
        records[item["id"]] = {"id": item["id"], "category": item["category"], "input": question,
                               "status": resp["status"], "answer": resp["answer"], "contexts": resp["contexts"],
                               "tools": resp["tools"], "approvals": resp["approvals"],
                               "elapsed_s": resp["elapsed_s"], **verdict}
        print(f"  {'✅' if verdict['passed'] else '❌'} #{item['id']:2} [{item['category']:9}] {resp['status']:14} "
              f"{resp['elapsed_s']:5.1f}s {question[:30]}", flush=True)
        return verdict

    eval_set = [{"id": c["id"], "question": c["input"], "type": c["category"]} for c in cases]
    print(f"[round {args.round}] 케이스 {len(cases)}건 실행")
    report = run_eval(answer_fn, eval_set, judge=lambda item, verdict: verdict["passed"])

    l1_rows = [dict(records[c["id"]], reference=references[str(c["id"])]) for c in cases
               if c["id"] in records and str(c["id"]) in references and c["category"] != "negative"]
    ragas = {"skipped": True} if args.no_ragas else ragas_scores(l1_rows)
    guard = [r for r in records.values() if r["category"] == "guardrail"]
    result = {
        "round": args.round, "ran_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "pass_rate": f"{report['passed']}/{report['total']}", "report": report,
        "ragas": ragas, "l2": l2_scores(),
        "l4_guardrail": f"{sum(r['passed'] for r in guard)}/{len(guard)}",
        "cases": [records[k] for k in sorted(records)],
    }
    prev = EVAL_DIR / "results" / f"round{args.round - 1}.json"
    if prev.exists():
        result["compare_with_prev"] = compare_eval(json.loads(prev.read_text(encoding="utf-8"))["report"], report)
    out = EVAL_DIR / "results" / f"round{args.round}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    print(f"\n통과율 {result['pass_rate']}  by_type={report['by_type']}")
    print(f"L4 guardrail {result['l4_guardrail']}")
    print(f"L2 {result['l2']}")
    print(f"RAGAS {({k: v for k, v in ragas.items() if k != 'per_case'})}")
    if "compare_with_prev" in result:
        print(f"이전 라운드 대비 {result['compare_with_prev']}")
    print(f"저장: {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
