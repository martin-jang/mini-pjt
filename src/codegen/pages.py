"""Page Builder (T16): Happy Path 화면(LLM) + 라우트·메뉴·플레이스홀더(결정적).

- Happy Path 화면은 공통 컴포넌트와 src/api/client.ts 함수만 써서 LLM이 작성합니다. antd 직접 import 금지.
- 화면이 지켜야 할 data-testid·이동 경로·호출할 API 함수는 프롬프트에 정확히 넘깁니다 (계약).
- 나머지 업무 화면은 '구현 예정' 플레이스홀더, 생성에 실패한 화면은 '구현 실패' 플레이스홀더 (LLM 미사용).
- 로그인 후 이동할 곳은 ?next= 쿼리 (없으면 Happy Path 의 로그인 다음 화면).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from src.analyst import naming
from src.analyst.happy_path import load_happy_paths
from src.codegen.components import SPECS
from src.guardrails import check_write_path, find_forbidden_code
from src.llm import default_llm, invoke_structured


def pascal(slug: str) -> str:
    return slug[:1].upper() + slug[1:]


def page_component(slug: str) -> str:
    return f"{pascal(slug)}Page"


def screen_plan(domain: str, contract: dict[str, Any]) -> dict[str, Any]:
    """화면별 생성 계획: 라우트, Happy Path 여부, 지켜야 할 testid·이동."""
    flows = load_happy_paths(domain)
    eps = {e["slug"]: e for e in contract["endpoints"]}
    login_slug = next((e["slug"] for e in contract["endpoints"] if e["kind_api"] == "login"), None)
    plans: dict[str, dict[str, Any]] = {}
    for slug, ep in eps.items():
        plans[slug] = {"slug": slug, "title": ep["title"], "route": naming.route_path(slug, login_slug),
                       "endpoint": ep, "happy_path": False, "page_testid": naming.page_testid(slug),
                       "submit_testid": None, "fields": {}, "links": {}, "after_submit": None, "after_login": None}
    for f in flows:
        steps = f["steps"]
        for i, st in enumerate(steps):
            p = plans.get(st["slug"])
            if not p:
                continue
            p["happy_path"] = True
            for fld in st["fields"]:
                p["fields"][fld["name"]] = fld["testid"]
            nxt = steps[i + 1]["slug"] if i + 1 < len(steps) else None
            if not st["action_testid"] or not nxt:
                continue
            if st["action"] == "login":
                p["submit_testid"] = st["action_testid"]
                p["after_login"] = p["after_login"] or plans[nxt]["route"]
            elif st["action"] == "fill_submit":
                p["submit_testid"] = st["action_testid"]
                p["after_submit"] = plans[nxt]["route"] if nxt in plans else None
            else:
                p["links"][st["action_testid"]] = plans[nxt]["route"] if nxt in plans else f"/{nxt}"
    menu = [{"path": p["route"], "label": p["title"]} for p in plans.values()
            if p["endpoint"]["kind_api"] in ("list", "submit") and not p["endpoint"].get("result_of")]
    return {"login_slug": login_slug, "plans": plans, "menu": menu}


# ──────────────────────────────────────────────────────────────────
# 결정적 파일: 메뉴·라우트·플레이스홀더
# ──────────────────────────────────────────────────────────────────


def render_menu(plan: dict[str, Any]) -> str:
    return ("// Legacy2Next가 결정적으로 생성하는 메뉴입니다.\nimport type { MenuItem } from './components/PageLayout'\n\n"
            f"export const menu: MenuItem[] = {json.dumps(plan['menu'], ensure_ascii=False, indent=2)}\n")


def render_routes(plan: dict[str, Any]) -> str:
    plans = plan["plans"]
    imports = "\n".join(f"import {page_component(s)} from './pages/{page_component(s)}'" for s in plans)
    default = plan["plans"][plan["login_slug"]]["route"] if plan["login_slug"] else next(iter(plans.values()))["route"]
    entries = ",\n".join(f"  {{ path: '{p['route']}', title: '{p['title']}', element: <{page_component(s)} /> }}"
                         for s, p in plans.items())
    return f"""// Legacy2Next가 결정적으로 생성하는 라우트입니다.
import type {{ ReactElement }} from 'react'
import {{ Navigate }} from 'react-router'
{imports}

export interface AppRoute {{ path: string; title: string; element: ReactElement }}

export const routes: AppRoute[] = [
  {{ path: '/', title: '시작', element: <Navigate to="{default}" replace /> }},
{entries},
]
"""


def render_placeholder(p: dict[str, Any], reason: str) -> str:
    label = "구현 실패" if reason == "failed" else "구현 예정"
    note = ("자동 생성에 실패해 플레이스홀더로 대체했습니다." if reason == "failed"
            else "핵심 업무 흐름(Happy Path) 밖의 화면이라 이번 POC에서는 구조만 제공합니다.")
    return f"""// {label} 플레이스홀더 (Legacy2Next 결정적 생성)
import {{ PageLayout }} from '../components/PageLayout'
import {{ menu }} from '../menu'

export default function {page_component(p['slug'])}() {{
  return (
    <PageLayout title="{p['title']}" testId="{p['page_testid']}" menu={{menu}}>
      <p data-testid="{p['slug']}-placeholder">[{label}] {note}</p>
    </PageLayout>
  )
}}
"""


# ──────────────────────────────────────────────────────────────────
# LLM 화면 생성
# ──────────────────────────────────────────────────────────────────


class GeneratedPage(BaseModel):
    code: str = Field(description="화면 .tsx 파일 전체 코드")


_PROMPT = """당신은 React + TypeScript 화면 개발자입니다. 레거시 화면 '{title}' 을 차세대 화면으로 구현하세요.
반드시 아래 공통 컴포넌트와 API 함수만 사용합니다.

[파일] src/pages/{component}.tsx — `export default function {component}()` 하나

[사용 가능한 import — 이 밖은 금지 (antd 직접 import 금지)]
- import {{ useEffect, useState }} from 'react'
- import {{ useNavigate, useLocation, useSearchParams }} from 'react-router'  (react-router-dom 아님)
- import {{ menu }} from '../menu'
- 공통 컴포넌트: {components}  (각각 `import {{ 이름 }} from '../components/이름'`)
- API: `import {{ ... }} from '../api/client'` 에서 아래 함수만

[공통 컴포넌트 props]
{props}

[이 화면의 API (src/api/client.ts 발췌)]
{api}

[이 화면의 계약 — 반드시 지킬 것]
- 최상위는 <PageLayout title="{title}" testId="{page_testid}" menu={{menu}}>
{contract_rules}

[데이터]
{data_rules}

- 모든 표시 문구는 한국어. 로딩 중·오류는 화면에 표시 (오류는 FormSection error 또는 ResultPanel status='error').
- 외부 URL·dangerouslySetInnerHTML·eval 금지. any 대신 Record<string, string> 사용.
{feedback}"""


def _api_excerpt(client_ts: str, slug: str) -> str:
    name = pascal(slug)
    keep, take = [], False
    for line in client_ts.splitlines():
        if line.startswith(("export type SubmitResult", "export type Detail", "export type Login",
                            "export function login")):
            keep.append(line)
        if any(k in line for k in (f"{name}Row", f"{name}Data", f"{name}Request", f"get{name}(", f"get{name}Options",
                                    f"submit{name}(")):
            take = True
        if take:
            keep.append(line)
            if line.strip() == "}" or line.startswith("export type"):
                take = False
    return "\n".join(dict.fromkeys(keep))


def _rules(p: dict[str, Any], plans: dict[str, Any]) -> tuple[str, str]:
    ep = p["endpoint"]
    rules, data = [], []
    if ep["kind_api"] == "login":
        rules.append(f"- FormSection 으로 아이디·비밀번호 입력. 필드 testId: {json.dumps(p['fields'], ensure_ascii=False)} "
                     f"(키=필드 name). 제출 버튼 submitTestId='{p['submit_testid']}'")
        rules.append(f"- 제출 시 login({{username, password}}) 호출. ok 이면 navigate(searchParams.get('next') ?? '{p['after_login']}')")
        data.append("- 로그인 실패 메시지는 FormSection error 로 표시")
    elif ep["kind_api"] == "list":
        if ep.get("filters"):
            data.append(f"- 조회조건이 있으면 SearchPanel 을 DataTable 위에 둠 (조회조건 필드: {[f['name'] for f in ep['filters']]}). "
                        f"onSearch 시 get{pascal(p['slug'])}(values) 재호출")
        data.append(f"- 마운트 시 get{pascal(p['slug'])}(Object.fromEntries(searchParams)) 호출 → rows 는 DataTable, "
                    "details 는 DetailList(items=Object.values(details))")
        data.append(f"- DataTable columns: {json.dumps([{'key': c['key'], 'title': c['header']} for c in ep['columns']], ensure_ascii=False)}")
        for testid, route in p["links"].items():
            target = route.strip("/")
            if target in plans and plans[target]["endpoint"]["kind_api"] == "list":
                rules.append(f"- DataTable linkColumn='{ep['columns'][0]['key'] if ep['columns'] else ''}', linkTestId='{testid}', "
                             f"onLinkClick=(row) => navigate('{route}?id=' + row['{ep['columns'][0]['key'] if ep['columns'] else 'id'}'])")
            else:
                rules.append(f"- 화면 상단에 '{plans.get(target, {}).get('title', target)}' 로 가는 버튼을 두고 "
                             f"data-testid='{testid}', 클릭 시 navigate('{route}'). (공통 컴포넌트에 버튼이 없으면 "
                             f"<button> 대신 PageLayout 안의 <a href> 가 아니라 navigate 를 쓰는 <button type=\"button\"> 사용)")
    elif ep["kind_api"] == "submit":
        fields = [{"name": f["key"], "label": f["label"].strip(" :#$") or f["name"], "type": f["type"],
                   "testId": p["fields"].get(f["name"]), "required": True} for f in ep["fields"]]
        rules.append(f"- FormSection fields={json.dumps(fields, ensure_ascii=False)} (select 의 options 는 "
                     f"get{pascal(p['slug'])}Options() 결과[field.name] 로 채움)")
        rules.append(f"- 제출 버튼 submitTestId='{p['submit_testid'] or naming.submit_testid(p['slug'])}'")
        if p["after_submit"]:
            rules.append(f"- 제출 시 submit{pascal(p['slug'])}(values) 호출. ok 이면 navigate('{p['after_submit']}', "
                         "{ state: result }) 로 결과 화면 이동 (result 는 SubmitResult)")
        else:
            rules.append(f"- 제출 시 submit{pascal(p['slug'])}(values) 호출, 결과를 ResultPanel 로 같은 화면에 표시")
    elif ep.get("result_of"):
        data.append("- useLocation().state 를 SubmitResult 로 읽어 ResultPanel 로 표시: status=ok?'success':'error', "
                    "title='처리 결과', message=result.message, items=Object.entries(result.submitted).map(([label, value]) => ({label, value}))")
        data.append(f"- ResultPanel testId='{p['slug']}-result'. state 가 없으면 status='error', title='표시할 결과가 없습니다'")
    return "\n".join(rules) or "- (추가 계약 없음)", "\n".join(data) or "- (데이터 없음)"


def generate_page(p: dict[str, Any], plans: dict[str, Any], client_ts: str, feedback: str = "", llm=None) -> str:
    llm = llm or default_llm(max_tokens=8192)
    contract_rules, data_rules = _rules(p, plans)
    props = "\n\n".join(s["props"] for s in SPECS)
    fb = f"\n[이전 코드의 오류 — 반드시 고치세요]\n{feedback}\n" if feedback else ""
    out = invoke_structured(llm, GeneratedPage, _PROMPT.format(
        title=p["title"], component=page_component(p["slug"]), components=", ".join(s["name"] for s in SPECS),
        props=props, api=_api_excerpt(client_ts, p["slug"]), page_testid=p["page_testid"],
        contract_rules=contract_rules, data_rules=data_rules, feedback=fb))
    return out.code


def write_page(project: Path, slug: str, code: str) -> list[str]:
    rel = f"src/pages/{page_component(slug)}.tsx"
    ok, why = check_write_path(rel, project)
    if not ok:
        return [why]
    (project / rel).write_text(code, encoding="utf-8")
    bad = find_forbidden_code(code)
    return [f"{rel}: 금지 패턴 {bad}"] if bad else []


def write_static(project: Path, plan: dict[str, Any]) -> None:
    (project / "src" / "menu.ts").write_text(render_menu(plan), encoding="utf-8")
    (project / "src" / "routes.tsx").write_text(render_routes(plan), encoding="utf-8")
    for slug, p in plan["plans"].items():
        if not p["happy_path"]:
            write_page(project, slug, render_placeholder(p, "planned"))
