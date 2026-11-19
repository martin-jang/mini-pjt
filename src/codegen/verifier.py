"""Verifier (T17): 빌드 · Storybook 빌드 · 정적 규칙 · Happy Path 흐름 검증(Playwright).

- run_build            : npm run build:mock (tsc + vite, MSW 활성), npm run build-storybook
- check_component_rules: pages 의 antd 직접 import, 허용 목록 밖 import, 금지 패턴, testid 누락, 스토리 부족, 라우트 누락
- run_happy_path_check : happy_paths.json 으로 Playwright 스펙을 결정적으로 생성해 vite preview + MSW 에서 실행
도구는 예외 대신 결과 dict 를 돌려줍니다 (실패도 그대로 보고).
"""

from __future__ import annotations

import json
import re
import socket
import subprocess
from pathlib import Path
from typing import Any

from src.guardrails import find_forbidden_code

_TS_ERR = re.compile(r"(src/[\w/.\-]+\.tsx?)\(\d+,\d+\): error (TS\d+: .+)")


def _npm(cmd: str, project: Path, env: dict[str, str] | None = None, timeout: int = 600) -> tuple[int, str]:
    import os
    full_env = {**os.environ, **(env or {})}
    r = subprocess.run(cmd, cwd=project, shell=True, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=full_env, timeout=timeout)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def run_build(project: Path, storybook: bool = True) -> dict[str, Any]:
    """앱 빌드(MSW 모드)와 Storybook 빌드. 실패하면 파일별 TS 오류를 모아 돌려줍니다."""
    code, out = _npm("npm run build:mock", project)
    errors: dict[str, list[str]] = {}
    for f, msg in _TS_ERR.findall(out.replace("\\", "/")):
        errors.setdefault(f, []).append(msg)
    result = {"app_ok": code == 0, "app_errors": errors, "app_log_tail": out[-1500:] if code else ""}
    if storybook and code == 0:
        sb_code, sb_out = _npm("npm run build-storybook", project)
        result.update(storybook_ok=sb_code == 0, storybook_log_tail=sb_out[-1500:] if sb_code else "")
    elif storybook:
        result.update(storybook_ok=False, storybook_log_tail="앱 빌드 실패로 건너뜀")
    return result


def check_component_rules(project: Path, plan: dict[str, Any], flows: list[dict[str, Any]]) -> dict[str, Any]:
    """정적 규칙 검사. violations: [{file, rule, detail}]"""
    allowed = set(json.loads((project / "allowed-deps.json").read_text(encoding="utf-8"))["imports"])
    allowed_roots = {a.split("/")[0] if not a.startswith("@") else "/".join(a.split("/")[:2]) for a in allowed}
    violations = []
    imp = re.compile(r"""from\s+['"]([^'"]+)['"]""")
    for f in sorted((project / "src").rglob("*.ts*")):
        rel = f.relative_to(project).as_posix()
        code = f.read_text(encoding="utf-8")
        for mod in imp.findall(code):
            if mod.startswith("."):
                continue
            root = mod.split("/")[0] if not mod.startswith("@") else "/".join(mod.split("/")[:2])
            if root not in allowed_roots and root != "react":
                violations.append({"file": rel, "rule": "허용 목록 밖 의존성", "detail": mod})
            if rel.startswith("src/pages/") and root == "antd":
                violations.append({"file": rel, "rule": "화면에서 antd 직접 import", "detail": mod})
        for bad in find_forbidden_code(code):
            violations.append({"file": rel, "rule": "금지 패턴", "detail": bad})
    # 스토리: 공통 컴포넌트마다 2개 이상
    for comp in sorted((project / "src" / "components").glob("*.tsx")):
        if comp.name.endswith(".stories.tsx"):
            continue
        story = comp.with_name(comp.stem + ".stories.tsx")
        n = len(re.findall(r"export const \w+\s*:\s*Story", story.read_text(encoding="utf-8"))) if story.exists() else 0
        if n < 2:
            violations.append({"file": comp.relative_to(project).as_posix(), "rule": "스토리 부족", "detail": f"{n}개"})
    # Happy Path testid: 화면 파일에 계약 ID 문자열이 있어야 함
    for fl in flows:
        for st in fl["steps"]:
            page = project / "src" / "pages" / f"{st['slug'][:1].upper() + st['slug'][1:]}Page.tsx"
            code = page.read_text(encoding="utf-8") if page.exists() else ""
            for tid in [st["page_testid"], st["action_testid"], *[x["testid"] for x in st["fields"]]]:
                if tid and tid not in code:
                    violations.append({"file": page.relative_to(project).as_posix(), "rule": "data-testid 누락", "detail": tid})
    routes = (project / "src" / "routes.tsx").read_text(encoding="utf-8")
    missing = [p["route"] for p in plan["plans"].values() if f"path: '{p['route']}'" not in routes]
    if missing:
        violations.append({"file": "src/routes.tsx", "rule": "라우트 누락", "detail": ",".join(missing)})
    total = len(plan["plans"])
    return {"ok": not violations, "violations": violations,
            "route_coverage": (total - len(missing)) / total if total else 0.0}


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def render_happy_path_spec(flows: list[dict[str, Any]], plan: dict[str, Any]) -> str:
    """happy_paths.json → Playwright 스펙 (결정적). testid 로만 조작합니다."""
    plans = plan["plans"]
    out = ["// Legacy2Next가 happy_paths.json 에서 결정적으로 생성한 흐름 검증입니다.",
           "import { expect, test } from '@playwright/test'", ""]
    for fl in flows:
        steps = fl["steps"]
        first = plans[steps[0]["slug"]]["route"]
        if steps[0]["action"] == "login" and len(steps) > 1:
            first += f"?next={plans[steps[1]['slug']]['route']}"
        out.append(f"test('{fl['flow_id']} {fl['name']}', async ({{ page }}) => {{")
        out.append(f"  await page.goto('{first}')")
        for st in steps:
            out.append(f"  // {st['step_id']} {st['screen_title']} ({st['action']})")
            out.append(f"  await expect(page.getByTestId('{st['page_testid']}')).toBeVisible()")
            for fld in st["fields"]:
                if fld["type"] == "select":
                    out.append(f"  await page.getByTestId('{fld['testid']}').click()")
                    # 닫힌 드롭다운도 DOM에 남으므로, 가장 최근에 열린(숨김 아님) 드롭다운의 첫 옵션을 고릅니다
                    out.append("  await page.locator('.ant-select-dropdown:not(.ant-select-dropdown-hidden)').last()"
                               ".locator('.ant-select-item-option').first().click()")
                else:
                    value = "demo" if any(k in fld["name"].lower() for k in ("user", "pass", "name")) else "1"
                    out.append(f"  await page.getByTestId('{fld['testid']}').fill('{value}')")
            if st["action_testid"]:
                out.append(f"  await page.getByTestId('{st['action_testid']}').first().click()")
                if st["action"] == "fill_submit":
                    # 확인 단계가 켜진 폼이면 확인 버튼을 누름 (없으면 건너뜀)
                    out.append("  const ok = page.locator('.ant-modal:visible .ant-btn-primary')")
                    out.append("  if (await ok.count()) await ok.first().click()")
        last = steps[-1]
        if plans[last["slug"]]["endpoint"].get("result_of"):
            out.append("  await expect(page.getByText('완료').first()).toBeVisible()")
        out += ["})", ""]
    return "\n".join(out)


def run_happy_path_check(project: Path, flows: list[dict[str, Any]], plan: dict[str, Any]) -> dict[str, Any]:
    """vite preview(MSW 활성) + Playwright 로 Happy Path 를 클릭해 따라갑니다. 흐름별 통과 여부를 돌려줍니다."""
    spec = project / "e2e" / "happy_path.spec.ts"
    spec.parent.mkdir(exist_ok=True)
    spec.write_text(render_happy_path_spec(flows, plan), encoding="utf-8")
    port = _free_port()
    code, out = _npm("npx playwright test e2e/happy_path.spec.ts", project, env={"PREVIEW_PORT": str(port)}, timeout=300)
    results = {}
    rep = project / "e2e-results.json"
    if rep.exists():
        data = json.loads(rep.read_text(encoding="utf-8"))

        def walk(suite):
            for s in suite.get("specs", []):
                ok = all(t.get("status") == "expected" for t in s.get("tests", []))
                err = ""
                for t in s.get("tests", []):
                    for r in t.get("results", []):
                        # 시간 초과처럼 짧은 메시지만으로는 원인을 알 수 없으므로 errors·snippet 까지 모읍니다
                        for e in ([r["error"]] if r.get("error") else []) + list(r.get("errors") or []):
                            msg = (e.get("message") or "") + "\n" + (e.get("snippet") or "")
                            err = (err + "\n" + re.sub(r"\x1b\[[0-9;]*m", "", msg)).strip()[:900]
                results[s["title"]] = {"ok": ok, "error": err}
            for child in suite.get("suites", []):
                walk(child)
        for suite in data.get("suites", []):
            walk(suite)
    return {"ok": code == 0 and bool(results) and all(r["ok"] for r in results.values()), "flows": results,
            "log_tail": out[-1200:] if code else ""}
