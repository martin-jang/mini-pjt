"""API 계약 + MSW 핸들러 + mock 데이터의 결정적 생성 (T14, 결정 D7·D13).

LLM을 쓰지 않습니다. 화면 인벤토리와 Happy Path에서 규칙으로 만들기 때문에, LLM이 작성하는 화면 코드와
mock이 서로 어긋나 '빌드는 되는데 실행하면 빈 화면'이 되는 실패를 원천 차단합니다.

규칙 (사이트 고유 값 없음):
  - 화면 slug: URL 경로의 마지막 파일명 (확장자 제외), 결과 화면은 '{입력 slug}Result'
  - 데이터 테이블: 헤더가 모두 있고 ':'로 끝나지 않는 테이블 → rows
  - 상세 테이블: 첫 헤더가 ':'로 끝나는 '항목: 값' 테이블 → details
  - 인증 화면(비밀번호 입력란) → POST /api/auth/login
  - 조회 화면 → GET /api/{slug}         → { rows, details }
  - 입력 화면 → GET /api/{slug}/options → { [select 필드]: 옵션[] },  POST /api/{slug} → { ok, message, submitted }
  - mock 값: 마스킹 표식([ACCOUNT] 등)은 더미 값 풀에서 결정적으로 채움, 날짜는 통일 결정의 표준 형식 적용
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from src.analyst import naming
from src.analyst.happy_path import load_happy_paths
from src.analyst.inventory import Screen, load_inventory
from src.analyst.unification import load_decisions
from src.analyst.variants import detect_date_format

NOTE = "// 교육용 더미 데이터입니다. 이 파일은 Legacy2Next가 결정적으로 생성합니다 (LLM 작성 금지)."


# ──────────────────────────────────────────────────────────────────
# 이름 규칙
# ──────────────────────────────────────────────────────────────────


def screen_slug(s: Screen) -> str:
    return naming.screen_slug(s.url_pattern, s.result_of)


ident = naming.ident


def pascal(slug: str) -> str:
    return slug[:1].upper() + slug[1:]


# ──────────────────────────────────────────────────────────────────
# mock 값
# ──────────────────────────────────────────────────────────────────

_PLACEHOLDER = re.compile(r"\[(ACCOUNT|EMAIL|PHONE|SSN|CARD|EMPLOYEE_ID|JWT|AWS_KEY)\]")
_DUMMY = {"ACCOUNT": lambda n: f"{10001 + n}", "EMAIL": lambda n: f"user{n + 1}@example.com",
          "PHONE": lambda n: f"010-0000-{1000 + n:04d}", "SSN": lambda n: "000-00-0000",
          "CARD": lambda n: "0000-0000-0000-0000", "EMPLOYEE_ID": lambda n: f"E{n:06d}",
          "JWT": lambda n: "dummy-token", "AWS_KEY": lambda n: "DUMMYKEY"}


def dummy(value: str, n: int = 0) -> str:
    """마스킹 표식을 결정적 더미 값으로 바꿉니다 (n: 순번, 같은 순번은 같은 값)."""
    return _PLACEHOLDER.sub(lambda m: _DUMMY[m.group(1)](n), value or "")


def standard_date_format(domain: str) -> str | None:
    for d in load_decisions(domain):
        if d["element_type"] == "date_format" and d["decision"] == "unify" and d.get("standard"):
            return d["standard"]
    return None


def to_format(value: str, fmt: str | None) -> str:
    """날짜 셀을 표준 형식으로 바꿉니다 (판별되는 날짜만)."""
    src = detect_date_format(value)
    if not fmt or not src:
        return value
    digits = re.findall(r"\d+", value)
    order = {"YYYY-MM-DD": "ymd", "YYYY/MM/DD": "ymd", "YYYYMMDD": "ymd", "MM-DD-YYYY": "mdy",
             "MM/DD/YYYY": "mdy", "DD.MM.YYYY": "dmy"}[src]
    if src == "YYYYMMDD":
        y, m, d = value[:4], value[4:6], value[6:8]
    else:
        parts = dict(zip(order, digits))
        y, m, d = parts["y"], parts["m"], parts["d"]
    return fmt.replace("YYYY", y).replace("MM", m).replace("DD", d)


def _vary(cell: str, i: int) -> str:
    """샘플 1행으로 여러 행을 만들 때 금액을 결정적으로 조금씩 바꿉니다.

    '$'가 붙은 금액만 바꿉니다. 계좌번호 같은 식별 숫자를 바꾸면 화면 간 더미 계좌가 어긋납니다.
    """
    m = re.fullmatch(r"(-?\$)(\d[\d,]*)(\.\d+)?", cell)
    if m and i:
        num = int(m.group(2).replace(",", "")) + 37 * i
        return f"{m.group(1)}{num}{m.group(3) or ''}"
    return cell


# ──────────────────────────────────────────────────────────────────
# 계약 만들기
# ──────────────────────────────────────────────────────────────────


def _data_table(s: Screen):
    for t in s.tables:
        if len(t.headers) >= 2 and all(h.strip() for h in t.headers) and not t.headers[0].strip().endswith(":"):
            return t
    return None


def _detail_tables(s: Screen):
    return [t for t in s.tables if t.headers and t.headers[0].strip().endswith(":")]


def _unique_keys(keys: list[str], prefix: str) -> list[str]:
    """TS 객체 키가 겹치지 않게 합니다. 영문이 없는 이름(한글 헤더 등)은 ident 가 'value' 가 되므로
    '{prefix}{순번}' 으로 바꾸고, 같은 키가 또 나오면 뒤에 2, 3 … 을 붙입니다."""
    out: list[str] = []
    for i, k in enumerate(keys, start=1):
        k = f"{prefix}{i}" if k == "value" else k
        base, n = k, 2
        while k in out:
            k, n = f"{base}{n}", n + 1
        out.append(k)
    return out


def _dedupe_by_name(fields):
    """같은 name 을 공유하는 입력(라디오 버튼 묶음 등)은 값 하나를 보내는 필드 하나로 봅니다."""
    seen, out = set(), []
    for f in fields:
        if f.name and f.name in seen:
            continue
        if f.name:
            seen.add(f.name)
        out.append(f)
    return out


def build_contract(domain: str) -> dict[str, Any]:
    """도메인의 업무 화면 → API 계약(dict). 코드 생성(TS 렌더링)과 화면 생성 프롬프트가 함께 씁니다."""
    screens = [s for s in load_inventory(domain) if s.is_business]
    slugs = naming.slug_map(screens)  # 파일명이 같은 화면도 겹치지 않는 이름 (Happy Path 계약과 같은 규칙·같은 화면 목록)
    fmt = standard_date_format(domain)
    hp_ids = {st["screen_id"] for f in load_happy_paths(domain) for st in f["steps"]}
    counter = {"n": 0}

    def next_dummy(v: str) -> str:
        out = dummy(v, counter["n"])
        if out != v:
            counter["n"] += 1
        return out

    endpoints = []
    for s in screens:
        # 화면마다 같은 순서로 더미 값을 채워, 앱 전체에서 같은 계좌들이 보이게 합니다 (10001, 10002, ...)
        counter["n"] = 0
        slug = slugs[s.screen_id]
        uniq_fields = _dedupe_by_name(s.fields)
        field_labels = {ident(f.label.strip(" :")) for f in s.fields if f.label}
        ep: dict[str, Any] = {"screen_id": s.screen_id, "slug": slug, "title": s.title_ko or s.title,
                              "kind": s.kind, "happy_path": s.screen_id in hp_ids, "result_of": s.result_of}
        # 로그인: 아이디·비밀번호만 있는 인증 화면 (레거시는 모든 화면 옆에 로그인 폼이 붙어 있어
        # 비밀번호 입력란만으로는 가입·계정 찾기 화면과 구분되지 않음)
        named = [f for f in s.fields if f.name]
        if s.kind == "인증" and any(f.type == "password" for f in named) and len(named) <= 3:
            ep.update(method="POST", path="/api/auth/login", kind_api="login",
                      request=[{"key": ident(f.name), "name": f.name, "label": f.label, "type": f.type}
                               for f in s.fields if f.name in ("username", "password") or f.type == "password"])
        elif s.kind == "조회":
            t = _data_table(s)
            headers = t.headers if t else []
            cols = [{"key": k, "header": h} for k, h in zip(_unique_keys([ident(h) for h in headers], "col"), headers)]
            rows = []
            if t:
                base = t.sample_row or [""] * len(cols)
                for i in range(3):
                    rows.append({c["key"]: to_format(_vary(next_dummy(base[j] if j < len(base) else ""), i), fmt)
                                 for j, c in enumerate(cols)})
            details = {}
            for dt in _detail_tables(s):
                for k, v in [(dt.headers[0], dt.headers[1] if len(dt.headers) > 1 else "")] + \
                            [(dt.sample_row[0], dt.sample_row[1] if len(dt.sample_row) > 1 else "")]:
                    # 조회조건 입력란과 같은 라벨은 상세 정보가 아니라 필터이므로 뺍니다
                    if k.strip().endswith(":") and v.strip() and ident(k.strip(" :")) not in field_labels:
                        key = _unique_keys(list(details) + [ident(k)], "item")[-1]
                        details[key] = {"label": k.strip(" :"), "value": to_format(next_dummy(v), fmt)}
            filters = [{"key": ident(f.name), "name": f.name, "label": f.label, "type": f.type} for f in uniq_fields]
            ep.update(method="GET", path=f"/api/{slug}", kind_api="list", columns=cols, rows=rows,
                      details=details, filters=filters)
        elif s.kind in ("입력", "인증"):
            fields = [{"key": ident(f.name), "name": f.name, "label": f.label, "type": f.type,
                       "options": [next_dummy(o) for o in f.options_sample] or (["1", "2"] if f.type == "select" else [])}
                      for f in uniq_fields if f.name]
            ep.update(method="POST", path=f"/api/{slug}", kind_api="submit", fields=fields,
                      options_path=f"/api/{slug}/options")
        else:  # 결과·안내 화면은 API 없음 (결과는 제출 응답으로 표시)
            ep.update(kind_api="none")
        for key in ("fields", "filters"):  # 서로 다른 name 이 같은 TS 키가 되는 경우(영문 없는 name 등) 방지
            if ep.get(key):
                for item, k in zip(ep[key], _unique_keys([x["key"] for x in ep[key]], "field")):
                    item["key"] = k
        endpoints.append(ep)
    return {"domain": domain, "date_format": fmt, "endpoints": endpoints}


# ──────────────────────────────────────────────────────────────────
# TS 렌더링
# ──────────────────────────────────────────────────────────────────


def render_client(contract: dict[str, Any]) -> str:
    """src/api/client.ts: 타입 + fetch 함수. 화면 코드는 이 파일만 import 합니다."""
    out = [NOTE, "",
           "export type SubmitResult = { ok: boolean; message: string; submitted: Record<string, string> }",
           "export type Detail = { label: string; value: string }",
           "export type LoginRequest = { username: string; password: string }",
           "export type LoginResult = { ok: boolean; message: string; user?: string }", "",
           "async function call<T>(path: string, init?: RequestInit): Promise<T> {",
           "  const res = await fetch(path, { headers: { 'Content-Type': 'application/json' }, ...init })",
           "  const body = await res.json().catch(() => ({}))",
           "  if (!res.ok) throw new Error(body.message ?? `HTTP ${res.status}`)",
           "  return body as T",
           "}", "",
           "export function login(req: LoginRequest): Promise<LoginResult> {",
           "  return call<LoginResult>('/api/auth/login', { method: 'POST', body: JSON.stringify(req) })",
           "}", ""]
    for ep in contract["endpoints"]:
        name = pascal(ep["slug"])
        if ep["kind_api"] == "list":
            cols = "; ".join(f"{c['key']}: string" for c in ep["columns"]) or "[key: string]: string"
            out += [f"/** {ep['title']} 목록 행 */", f"export type {name}Row = {{ {cols} }}",
                    f"export type {name}Data = {{ rows: {name}Row[]; details: Record<string, Detail> }}",
                    f"export function get{name}(params: Record<string, string> = {{}}): Promise<{name}Data> {{",
                    f"  const q = new URLSearchParams(params).toString()",
                    f"  return call<{name}Data>('{ep['path']}' + (q ? `?${{q}}` : ''))", "}", ""]
        elif ep["kind_api"] == "submit":
            fields = "; ".join(f"{f['key']}: string" for f in ep["fields"]) or "[key: string]: string"
            out += [f"/** {ep['title']} 제출 값 */", f"export type {name}Request = {{ {fields} }}",
                    f"export function get{name}Options(): Promise<Record<string, string[]>> {{",
                    f"  return call<Record<string, string[]>>('{ep['options_path']}')", "}",
                    f"export function submit{name}(req: {name}Request): Promise<SubmitResult> {{",
                    f"  return call<SubmitResult>('{ep['path']}', {{ method: 'POST', body: JSON.stringify(req) }})",
                    "}", ""]
    return "\n".join(out)


def render_data(contract: dict[str, Any]) -> str:
    """src/mocks/data.ts: mock 데이터 (마스킹 → 더미, 날짜 표준 형식)."""
    lists = {ep["slug"]: {"rows": ep["rows"], "details": ep["details"]}
             for ep in contract["endpoints"] if ep["kind_api"] == "list"}
    options = {ep["slug"]: {f["key"]: f["options"] for f in ep["fields"] if f["type"] == "select"}
               for ep in contract["endpoints"] if ep["kind_api"] == "submit"}
    return "\n".join([NOTE, "",
                      f"export const listData: Record<string, {{ rows: Record<string, string>[]; details: Record<string, {{ label: string; value: string }}> }}> = "
                      f"{json.dumps(lists, ensure_ascii=False, indent=2)}", "",
                      f"export const optionData: Record<string, Record<string, string[]>> = "
                      f"{json.dumps(options, ensure_ascii=False, indent=2)}", ""])


def render_handlers(contract: dict[str, Any]) -> str:
    """src/mocks/handlers.ts: MSW 핸들러 (로그인·목록·옵션·제출)."""
    out = [NOTE, "import { http, HttpResponse } from 'msw'", "import { listData, optionData } from './data'", "",
           "export const handlers = [",
           "  http.post('/api/auth/login', async ({ request }) => {",
           "    const body = (await request.json()) as Record<string, string>",
           "    if (!body.username || !body.password) {",
           "      return HttpResponse.json({ ok: false, message: '아이디와 비밀번호를 입력하세요.' }, { status: 400 })",
           "    }",
           "    return HttpResponse.json({ ok: true, message: '로그인되었습니다.', user: body.username })",
           "  }),"]
    for ep in contract["endpoints"]:
        if ep["kind_api"] == "list":
            out.append(f"  http.get('{ep['path']}', () => HttpResponse.json(listData['{ep['slug']}'])),")
        elif ep["kind_api"] == "submit":
            out += [f"  http.get('{ep['options_path']}', () => HttpResponse.json(optionData['{ep['slug']}'] ?? {{}})),",
                    f"  http.post('{ep['path']}', async ({{ request }}) => {{",
                    "    const body = (await request.json()) as Record<string, string>",
                    "    const empty = Object.entries(body).filter(([, v]) => !String(v ?? '').trim()).map(([k]) => k)",
                    "    if (empty.length) {",
                    "      return HttpResponse.json({ ok: false, message: `입력이 필요합니다: ${empty.join(', ')}`, submitted: body }, { status: 400 })",
                    "    }",
                    f"    return HttpResponse.json({{ ok: true, message: '{ep['title']} 처리가 완료되었습니다.', submitted: body }})",
                    "  }),"]
    out += ["]", ""]
    return "\n".join(out)


def write_contract(domain: str, project: Path) -> dict[str, Any]:
    """계약을 만들고 생성 프로젝트의 src/api·src/mocks 에 씁니다. 계약 JSON도 함께 남깁니다."""
    contract = build_contract(domain)
    (project / "src" / "api").mkdir(parents=True, exist_ok=True)
    (project / "src" / "mocks").mkdir(parents=True, exist_ok=True)
    (project / "src" / "api" / "client.ts").write_text(render_client(contract), encoding="utf-8")
    (project / "src" / "mocks" / "data.ts").write_text(render_data(contract), encoding="utf-8")
    (project / "src" / "mocks" / "handlers.ts").write_text(render_handlers(contract), encoding="utf-8")
    (project / "contract.json").write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")
    return contract
