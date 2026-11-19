"""생성 코드에서 쓰는 이름 규칙 (화면 slug, TS 식별자, data-testid).

Analyst(Happy Path testid 계약)와 코드 생성(API 계약·화면·Playwright)이 같은 규칙을 써야 하므로 한곳에 둡니다.
사이트 고유 값은 없습니다. 모든 이름은 URL·필드명에서 기계적으로 만듭니다.
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlsplit


def screen_slug(url_pattern: str, result_of: str | None = None) -> str:
    """URL 경로의 마지막 파일명(확장자 제외)을 camelCase로. 결과 화면은 '{slug}Result'."""
    p = urlsplit("https:" + url_pattern if url_pattern.startswith("//") else url_pattern)
    base = re.sub(r"[^a-zA-Z0-9]+", "_", Path(p.path).stem).strip("_") or "home"
    slug = re.sub(r"_([a-z0-9])", lambda m: m.group(1).upper(), base.lower())
    return f"{slug}Result" if result_of else slug


def _camel(parts: list[str]) -> str:
    return parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:])


def slug_map(screens) -> dict[str, str]:
    """화면 목록 전체에서 겹치지 않는 slug 를 정합니다 (screen_id → slug, 결정적).

    파일명이 같은 화면(예: 관리자용·사용자용 목록이 디렉터리만 다른 경우, 쿼리만 다른 경우)은
    slug 가 겹쳐 API 함수·화면 컴포넌트 이름이 충돌합니다. 겹치면 경로의 상위 디렉터리 이름을 앞에 붙이고,
    그래도 겹치면 url_pattern 순서대로 2, 3 … 을 붙입니다. 같은 화면 목록에는 언제나 같은 결과가 나옵니다.
    Analyst(Happy Path testid)와 코드 생성(API 계약·화면)이 반드시 이 함수 하나로 slug 를 얻어야 합니다.
    """
    base = {s.screen_id: screen_slug(s.url_pattern, s.result_of) for s in screens}
    groups: dict[str, list] = {}
    for s in screens:
        groups.setdefault(base[s.screen_id], []).append(s)
    out: dict[str, str] = {}
    for slug, group in groups.items():
        if len(group) == 1:
            out[group[0].screen_id] = slug
            continue
        dirs = {}
        for s in group:
            p = urlsplit("https:" + s.url_pattern if s.url_pattern.startswith("//") else s.url_pattern)
            dirs[s.screen_id] = [re.sub(r"[^a-z0-9]", "", d.lower()) for d in Path(p.path).parent.parts if d.strip("/\\")]
        chosen = None
        for k in range(1, max(len(d) for d in dirs.values()) + 1):
            cand = {sid: _camel([x for x in d[-k:] if x] + [slug]) for sid, d in dirs.items()}
            if len(set(cand.values())) == len(cand):
                chosen = cand
                break
        if chosen is None:  # 디렉터리까지 같으면 순번
            chosen = {}
            for i, s in enumerate(sorted(group, key=lambda x: x.url_pattern)):
                chosen[s.screen_id] = slug if i == 0 else f"{slug}{i + 1}"
        out.update(chosen)
    # 접두어를 붙인 결과가 다른 화면의 slug 와 우연히 같아지는 경우까지 막습니다
    seen: dict[str, int] = {}
    for sid in sorted(out, key=lambda x: x):
        v = out[sid]
        if v in seen:
            seen[v] += 1
            out[sid] = f"{v}{seen[v]}"
        else:
            seen[v] = 1
    return out


def ident(name: str) -> str:
    """필드명·헤더를 TS 식별자로 (예: 'Debit (-)' → debit, 'payee.name' → payeeName)."""
    parts = re.findall(r"[A-Za-z0-9]+", name)
    if not parts:
        return "value"
    out = parts[0].lower() + "".join(p[:1].upper() + p[1:].lower() for p in parts[1:])
    return out if not out[0].isdigit() else "f" + out


def route_path(slug: str, login_slug: str | None = None) -> str:
    """앱 라우트 경로. 로그인 화면은 /login, 나머지는 /{slug}."""
    return "/login" if slug == login_slug else f"/{slug}"


# data-testid 계약 (화면 단위: 여러 흐름이 같은 화면을 지나도 ID가 같음)
def page_testid(slug: str) -> str:
    return f"{slug}-page"


def field_testid(slug: str, field_name: str) -> str:
    return f"{slug}-field-{ident(field_name)}"


def submit_testid(slug: str) -> str:
    return f"{slug}-submit"


def link_testid(slug: str, target_slug: str) -> str:
    return f"{slug}-to-{target_slug}"
