"""생성 파이프라인 (T14~T18): 템플릿 복사 → 계약·MSW → 공통 컴포넌트 → 화면 → 검증·자가 수정 → 결과.

고정 순서 파이프라인입니다 (README 핵심 의사결정 #1: Supervisor 자유 위임 대신 고정 파이프라인).
자가 수정은 최대 2회 (SERVICE.md "최종 실패 처리", 결정 D9):
  - 빌드 오류(tsc)·정적 규칙 위반·흐름 검증 실패 → 원인 파일만 오류 내용을 붙여 다시 생성
  - 2회 후에도 실패: 컴포넌트는 결정적 기본 구현으로, 화면은 '구현 실패' 플레이스홀더로 바꿔 다시 빌드
  - 이 경우 status="partial" 과 실패 목록·오류 요약을 결과에 남깁니다 (조용한 실패 금지)
"""

from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from src.analyst.happy_path import load_happy_paths
from src.codegen import components as comp
from src.codegen import pages as pg
from src.codegen.contracts import write_contract
from src.codegen.scaffold import scaffold_project
from src.codegen.verifier import check_component_rules, run_build, run_happy_path_check

MAX_FIX_ROUNDS = 2
WORKERS = 4


def _parallel(fn, items):
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        return list(ex.map(fn, items))


def generate_poc(domain: str, project_name: str, overwrite_approved: bool = False, log=print,
                 progress=None) -> dict[str, Any]:
    """POC 전체 생성. 반환: {status, project, components, pages, checks, failures, timings}

    progress(state, stage, detail) 를 주면 세부 단계 진행을 알립니다 (작업 화면의 단계 도식용).
    stage: scaffold / components / pages / verify, state: start / end / fail.
    """
    t0 = time.perf_counter()

    def stage(state: str, name: str, **detail: Any) -> None:
        if progress:
            try:
                progress(state, name, detail)
            except Exception:  # 진행 표시 실패는 생성 작업을 멈추지 않습니다
                pass
    timings: dict[str, float] = {}

    def lap(name: str, since: float) -> float:
        timings[name] = round(time.perf_counter() - since, 1)
        return time.perf_counter()

    flows = load_happy_paths(domain)
    if not flows:
        return {"status": "failed", "error": "핵심 업무 흐름이 없어 생성할 수 없습니다. 먼저 분석하세요."}
    stage("start", "scaffold")
    sc = scaffold_project(project_name, overwrite_approved=overwrite_approved)
    if "error" in sc:
        stage("fail", "scaffold", error=sc["error"])
        return {"status": "failed", "error": sc["error"], "needs_overwrite": True}
    from pathlib import Path
    project = Path(sc["path"])
    t = time.perf_counter()

    contract = write_contract(domain, project)
    plan = pg.screen_plan(domain, contract)
    patterns = comp.ui_patterns(domain, contract)
    specs = {s["name"]: s for s in comp._component_specs(domain)}
    (project / "src" / "components" / "PageLayout.stories.tsx").unlink(missing_ok=True)
    t = lap("contract", t)
    stage("end", "scaffold", pages=len(plan["plans"]), components=len(specs))

    # ── 공통 컴포넌트 (LLM, 병렬) ──
    log(f"공통 컴포넌트 {len(specs)}개 생성")
    stage("start", "components", items=list(specs))

    def gen_comp(name: str, feedback: str = "") -> tuple[str, list[str]]:
        try:
            g = comp.generate_component(specs[name], feedback=feedback)
            return name, comp.write_component(project, name, g.component, g.stories)
        except Exception as e:  # 생성 실패는 기록하고 이후 대체 구현으로 처리
            return name, [f"생성 오류: {type(e).__name__}: {str(e)[:200]}"]

    comp_problems = dict(_parallel(gen_comp, list(specs)))
    t = lap("components", t)
    stage("end", "components", items=list(specs), problems=[k for k, v in comp_problems.items() if v])

    # ── 화면: 결정적(라우트·메뉴·플레이스홀더) + Happy Path 화면(LLM, 병렬) ──
    pg.write_static(project, plan)
    client_ts = (project / "src" / "api" / "client.ts").read_text(encoding="utf-8")
    hp_slugs = [s for s, p in plan["plans"].items() if p["happy_path"]]
    log(f"Happy Path 화면 {len(hp_slugs)}개 생성: {hp_slugs}")
    stage("start", "pages", items=hp_slugs)

    def gen_page(slug: str, feedback: str = "") -> tuple[str, list[str]]:
        try:
            code = pg.generate_page(plan["plans"][slug], plan["plans"], client_ts, feedback=feedback)
            return slug, pg.write_page(project, slug, code)
        except Exception as e:
            return slug, [f"생성 오류: {type(e).__name__}: {str(e)[:200]}"]

    page_problems = dict(_parallel(gen_page, hp_slugs))
    # Bedrock 사용 한도 초과면 수정 라운드도 같은 이유로 실패하므로 헛돌지 않고 바로 멈춤
    quota = [k for k, v in {**comp_problems, **page_problems}.items() if any("Too many tokens" in x for x in v)]
    if quota:
        log(f"Bedrock 일일 토큰 한도 초과로 생성 중단: {quota}")
        stage("fail", "pages", error="Bedrock 일일 토큰 한도 초과")
        return {"status": "failed", "project": str(project), "project_name": project_name,
                "error": "Bedrock 일일 토큰 한도를 넘어 코드 생성을 진행할 수 없습니다. 한도가 풀린 뒤 다시 요청해 주세요.",
                "quota_exceeded": quota, "timings_s": timings}
    for k, v in {**comp_problems, **page_problems}.items():
        if v:
            log(f"  생성 문제 {k}: {v[:2]}")
    for name, probs in comp_problems.items():  # 생성 자체가 실패한 컴포넌트는 바로 대체 구현
        if any(p.startswith("생성 오류") for p in probs):
            comp.write_fallback(project, name)
    t = lap("pages", t)
    stage("end", "pages", items=hp_slugs, problems=[k for k, v in page_problems.items() if v])
    stage("start", "verify")

    # ── 검증 + 자가 수정 ──
    history = []
    fallback_components: list[str] = []
    failed_pages: list[str] = []
    for rnd in range(MAX_FIX_ROUNDS + 1):
        build = run_build(project, storybook=False)
        rules = check_component_rules(project, plan, flows)
        flow = run_happy_path_check(project, flows, plan) if build["app_ok"] else {"ok": False, "flows": {}, "log_tail": "빌드 실패"}
        history.append({"round": rnd, "app_ok": build["app_ok"], "rule_violations": len(rules["violations"]),
                        "flow_ok": flow["ok"], "errors": {k: v[:2] for k, v in build["app_errors"].items()},
                        "flow_errors": {k: v["error"][:300] for k, v in flow["flows"].items() if not v["ok"]}})
        log(f"검증 {rnd}: 빌드 {build['app_ok']} 규칙위반 {len(rules['violations'])} 흐름 {flow['ok']}")
        stage("round", "verify", round=rnd, app_ok=build["app_ok"], violations=len(rules["violations"]),
              flow_ok=flow["ok"])
        if build["app_ok"] and rules["ok"] and flow["ok"]:
            break
        # 원인 파일 → 피드백
        fb_comp: dict[str, list[str]] = {}
        fb_page: dict[str, list[str]] = {}
        for f, msgs in build["app_errors"].items():
            name = f.split("/")[-1].replace(".stories", "").replace(".tsx", "").replace(".ts", "")
            if f.startswith("src/components/") and name in specs:
                fb_comp.setdefault(name, []).extend(msgs)
            elif f.startswith("src/pages/"):
                slug = next((s for s in hp_slugs if pg.page_component(s) == name), None)
                if slug:
                    fb_page.setdefault(slug, []).extend(msgs)
        for v in rules["violations"]:
            name = v["file"].split("/")[-1].replace(".stories", "").replace(".tsx", "")
            if v["file"].startswith("src/components/") and name in specs:
                fb_comp.setdefault(name, []).append(f"{v['rule']}: {v['detail']}")
            slug = next((s for s in hp_slugs if pg.page_component(s) == name), None)
            if slug:
                fb_page.setdefault(slug, []).append(f"{v['rule']}: {v['detail']}")
        if build["app_ok"] and rules["ok"]:
            for title, r in flow["flows"].items():
                if not r["ok"]:
                    fid = title.split()[0]
                    for st in next((f["steps"] for f in flows if f["flow_id"] == fid), []):
                        if st["slug"] in hp_slugs:
                            fb_page.setdefault(st["slug"], []).append(f"흐름 검증 실패({title}): {r['error']}")
        if not fb_comp and not fb_page and not build["app_ok"]:
            # 원인 파일을 특정하지 못한 빌드 실패: 로그를 모든 화면에 전달
            fb_page = {s: [build["app_log_tail"][-800:]] for s in hp_slugs}
        if rnd == MAX_FIX_ROUNDS:
            # 2회 수정 후에도 실패 → 대체
            for name in fb_comp:
                comp.write_fallback(project, name)
                fallback_components.append(name)
            for slug in fb_page:
                pg.write_page(project, slug, pg.render_placeholder(plan["plans"][slug], "failed"))
                failed_pages.append(slug)
            break
        log(f"수정 {rnd + 1}: 컴포넌트 {list(fb_comp)} 화면 {list(fb_page)}")
        _parallel(lambda n: gen_comp(n, "\n".join(dict.fromkeys(fb_comp[n]))[:3000]), list(fb_comp))
        _parallel(lambda s: gen_page(s, "\n".join(dict.fromkeys(fb_page[s]))[:3000]), list(fb_page))
    t = lap("verify_fix", t)

    # ── 최종 검증 (Storybook 포함) ──
    final_build = run_build(project, storybook=True)
    final_rules = check_component_rules(project, plan, flows)
    final_flow = run_happy_path_check(project, flows, plan) if final_build["app_ok"] else {"ok": False, "flows": {}}
    lap("final_check", t)
    timings["total"] = round(time.perf_counter() - t0, 1)

    ok = final_build["app_ok"] and final_build.get("storybook_ok") and final_rules["ok"] and final_flow["ok"] \
        and not fallback_components and not failed_pages
    status = "ok" if ok else ("partial" if final_build["app_ok"] else "failed")
    report = {
        "status": status, "project": str(project), "project_name": project_name, "domain": domain,
        "components": list(specs), "fallback_components": fallback_components,
        "happy_path_pages": hp_slugs, "failed_pages": failed_pages,
        "placeholder_pages": [s for s, p in plan["plans"].items() if not p["happy_path"]],
        "checks": {"app_build": final_build["app_ok"], "storybook_build": final_build.get("storybook_ok"),
                   "rules_ok": final_rules["ok"], "rule_violations": final_rules["violations"][:20],
                   "route_coverage": final_rules["route_coverage"], "happy_path": final_flow.get("flows", {}),
                   "happy_path_ok": final_flow["ok"]},
        "generation_errors": {**{k: v for k, v in comp_problems.items() if v}, **{k: v for k, v in page_problems.items() if v}},
        "fix_rounds": history, "timings_s": timings, "ui_patterns": patterns,
    }
    stage("end" if status != "failed" else "fail", "verify", status=status)
    (project / "generation_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
