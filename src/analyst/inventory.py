"""Analyst ① 화면 인벤토리 (T07, 도구 build_screen_inventory).

스냅샷(크롤링 결과 또는 합성 픽스처)을 화면·필드·액션·테이블·화면 전환 구조로 정리합니다.
이후 변이 분석(T08), Happy Path(T09), RAG(T10), 코드 생성(T14~)이 모두 이 결과를 씁니다.

역할 분담:
  - 규칙(결정적): 필드·버튼·테이블·링크 추출, 같은 화면 묶기, 화면 간 연결
  - LLM: 화면 성격(조회/입력/결과/안내/관리) · 업무 화면 여부 · 한 줄 목적 판단만
사이트 고유 값은 코드에 없습니다. 판단 근거는 모두 스냅샷 데이터에서 옵니다.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urljoin

from pydantic import BaseModel, Field

from src.config import path as cfg_path
from src.crawler_core import clean_url, screen_id, url_pattern
from src.guardrails import wrap_as_data, DATA_BLOCK_RULE
from src.llm import default_llm, invoke_structured

ScreenKind = Literal["조회", "입력", "결과", "안내", "관리", "인증"]


# ──────────────────────────────────────────────────────────────────
# 스키마
# ──────────────────────────────────────────────────────────────────


class Field_(BaseModel):
    name: str
    label: str = ""
    type: str = "text"
    required: bool = False
    options_sample: list[str] = []


class Table(BaseModel):
    headers: list[str]
    row_count: int = 0
    sample_row: list[str] = []
    date_format: str | None = None
    has_total_row: bool | None = None


class Screen(BaseModel):
    """화면 1개의 인벤토리 항목."""

    screen_id: str
    domain: str
    url: str
    url_pattern: str
    title: str
    title_ko: str = Field("", description="한국어 화면명 (한국어 질의 검색용)")
    headings: list[str] = []
    requires_login: bool
    kind: ScreenKind = "안내"
    is_business: bool = True
    purpose: str = ""
    fields: list[Field_] = []
    buttons: list[str] = []
    tables: list[Table] = []
    links_to: list[str] = Field(default_factory=list, description="이 화면에서 링크로 이동하는 화면 ID")
    layout: dict[str, Any] = {}
    flow: dict[str, Any] = {}
    result_of: str | None = None


class ScreenJudgement(BaseModel):
    """LLM 판단 결과 (화면 1개)."""

    screen_id: str = Field(description="입력에 주어진 screen_id 그대로")
    kind: ScreenKind = Field(description="조회=데이터 목록·상세를 보여줌, 입력=사용자가 값을 넣고 제출, "
                                         "결과=제출 후 처리 결과, 안내=정적 소개·도움말, 관리=시스템 관리자용, 인증=로그인·가입·계정찾기")
    is_business: bool = Field(description="최종 사용자가 차세대 앱에서도 쓰게 될 화면이면 true. "
                                          "로그인·가입·계정 찾기 같은 인증 화면과 로그인 입구가 있는 첫 화면도 true. "
                                          "관리자 도구·API 문서·뉴스·회사 소개·사이트맵·문의처럼 업무와 무관한 화면은 false")
    purpose: str = Field(description="화면 목적을 한국어 한 문장으로")
    title_ko: str = Field(description="한국어 화면명. 사용자가 부를 법한 짧은 이름 (예: 계좌 개요, 계좌 상세(거래내역))")


class InventoryJudgement(BaseModel):
    screens: list[ScreenJudgement]


# ──────────────────────────────────────────────────────────────────
# 규칙 기반 추출
# ──────────────────────────────────────────────────────────────────


def _clean_title(title: str) -> str:
    """'사이트명 | 화면명 | ...' 형태 제목에서 화면명 부분을 고릅니다 (사이트명 하드코딩 없이)."""
    parts = [p.strip() for p in (title or "").split("|") if p.strip()]
    return parts[1] if len(parts) >= 2 else (parts[0] if parts else "")


def extract_screen(snap: dict[str, Any]) -> Screen:
    """스냅샷 1개를 규칙 기반으로 Screen 으로 바꿉니다 (LLM 판단 필드는 기본값)."""
    fields, buttons = [], []
    for form in snap.get("forms", []):
        for f in form.get("fields", []):
            if not f.get("name") and not f.get("label"):
                continue
            fields.append(Field_(name=f.get("name") or "", label=f.get("label") or "", type=f.get("type") or "text",
                                 required=bool(f.get("required")), options_sample=(f.get("options") or [])[:3]))
        buttons += [b for b in form.get("buttons", []) if b]
    for f in snap.get("loose_fields", []):
        fields.append(Field_(name=f.get("name") or "", label=f.get("label") or "", type=f.get("type") or "text"))
    buttons += [b for b in snap.get("buttons", []) if b]

    tables = [Table(headers=t.get("headers", []), row_count=t.get("row_count", 0),
                    sample_row=(t.get("sample_rows") or [[]])[0] if t.get("sample_rows") else [],
                    date_format=t.get("date_format"), has_total_row=t.get("has_total_row"))
              for t in snap.get("tables", [])]

    domain = snap["url"].split("//", 1)[-1].split("/", 1)[0]
    return Screen(
        screen_id=snap["screen_id"], domain=domain, url=snap["url"], url_pattern=snap["url_pattern"],
        title=_clean_title(snap.get("title", "")), requires_login=bool(snap.get("requires_login")),
        headings=[h for h in snap.get("headings", []) if h][:8],
        fields=fields, buttons=list(dict.fromkeys(buttons)), tables=tables,
        layout=snap.get("layout") or {}, flow=snap.get("flow") or {}, result_of=snap.get("result_of"),
    )


def link_screens(screens: list[Screen], snaps: list[dict[str, Any]]) -> None:
    """스냅샷의 링크를 화면 ID로 바꿔 links_to 를 채웁니다 (같은 도메인, 수집된 화면만)."""
    by_pattern = {s.url_pattern: s.screen_id for s in screens}
    by_id = {s.screen_id: s for s in screens}
    for snap in snaps:
        targets = []
        for link in snap.get("links", []):
            href = clean_url(urljoin(snap["url"], link.get("href", "")))
            sid = by_pattern.get(url_pattern(href))
            if sid and sid != snap["screen_id"]:
                targets.append(sid)
        if snap["screen_id"] in by_id:
            by_id[snap["screen_id"]].links_to = list(dict.fromkeys(targets))


# ──────────────────────────────────────────────────────────────────
# LLM 판단
# ──────────────────────────────────────────────────────────────────

_JUDGE_PROMPT = """당신은 레거시 웹 시스템을 분석하는 아키텍트입니다.
아래는 크롤링한 화면들의 구조 요약입니다. 화면마다 성격(kind), 최종 사용자 업무 화면인지(is_business),
목적(purpose, 한국어 한 문장)을 판단하세요. 모든 screen_id에 대해 빠짐없이 답하세요.

{rule}

{data}
"""


def _summary(s: Screen) -> dict[str, Any]:
    return {"screen_id": s.screen_id, "title": s.title, "headings": s.headings[:5], "requires_login": s.requires_login,
            "fields": [f.label or f.name for f in s.fields][:10], "buttons": s.buttons[:6],
            "tables": [t.headers for t in s.tables][:3], "result_of": s.result_of}


def judge_screens(screens: list[Screen], llm=None) -> None:
    """LLM으로 kind·is_business·purpose 를 채웁니다. 결과 화면(result_of)은 규칙으로 '결과' 고정."""
    if not screens:
        return
    llm = llm or default_llm()
    data = wrap_as_data(json.dumps([_summary(s) for s in screens], ensure_ascii=False))
    out = invoke_structured(llm, InventoryJudgement, _JUDGE_PROMPT.format(rule=DATA_BLOCK_RULE, data=data))
    judged = {j.screen_id: j for j in out.screens}
    for s in screens:
        j = judged.get(s.screen_id)
        if j:
            s.kind, s.is_business, s.purpose, s.title_ko = j.kind, j.is_business, j.purpose, j.title_ko
        if s.result_of:
            s.kind = "결과"


# ──────────────────────────────────────────────────────────────────
# 진입점
# ──────────────────────────────────────────────────────────────────


def load_source(domain: str) -> list[dict[str, Any]]:
    """도메인의 화면 스냅샷을 읽습니다. 크롤링 스냅샷 → 없으면 합성 픽스처 순으로 찾습니다."""
    for base in (cfg_path("snapshots"), cfg_path("fixtures")):
        d = base / domain
        if d.is_dir():
            return [json.loads(f.read_text(encoding="utf-8")) for f in sorted(d.glob("*.json"))
                    if not f.name.startswith("_")]
    return []


def inventory_path(domain: str) -> Path:
    return cfg_path("analysis") / domain / "screen_inventory.json"


def build_screen_inventory(domain: str, llm=None) -> dict[str, Any]:
    """도메인의 화면 인벤토리를 만들고 data/analysis/{domain}/screen_inventory.json 에 저장합니다.

    언제 쓰나: 크롤링(또는 픽스처 준비)이 끝난 뒤, 분석·RAG·생성의 첫 단계로.
    언제 쓰지 않나: 스냅샷이 없을 때 → 크롤링부터 하라는 안내를 돌려줍니다.
    """
    snaps = load_source(domain)
    if not snaps:
        return {"error": f"'{domain}' 의 화면 스냅샷이 없습니다. 먼저 크롤링하세요.", "screens": []}
    screens = [extract_screen(s) for s in snaps]
    link_screens(screens, snaps)
    judge_screens(screens, llm=llm)
    result = {"domain": domain, "screen_count": len(screens),
              "business_count": sum(s.is_business for s in screens),
              "screens": [s.model_dump() for s in screens]}
    out = inventory_path(domain)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def load_inventory(domain: str) -> list[Screen]:
    p = inventory_path(domain)
    if not p.exists():
        return []
    return [Screen.model_validate(s) for s in json.loads(p.read_text(encoding="utf-8"))["screens"]]
