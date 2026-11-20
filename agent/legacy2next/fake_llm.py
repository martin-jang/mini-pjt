"""테스트용 가짜 LLM 클라이언트 (`--fake-llm`). 실제 Bedrock 없이 E2E·개발 확인을 하기 위함.

흉내 내는 것:
- Router 분류: URL이 있으면 신규 생성(확장 단어가 있으면 확장), 사이트 관련 단어가 있으면 질의,
  그 외는 범위 밖
- 로그인 화면 판별(`<page_content>` 요청): 입력란 이름·버튼 이름·인증 단어로 판단
- 유스케이스 후보(`<sitemap>`): 표·폼이 있는 화면으로 검색·상세 조회 후보를 만든다
- 흐름 걷기(`<flow_goal>`): 상세 조회는 표 안 첫 링크 클릭, 검색은 검색어 입력 → 조회 버튼
실제 판단 품질은 실제 LLM으로 평가 샘플을 돌려 확인한다.
"""

from __future__ import annotations

import json
import re
from types import SimpleNamespace
from typing import Any

URL_PATTERN = re.compile(r"https?://[^\s<>\"']+")
QUERY_WORDS = (
    "화면",
    "컴포넌트",
    "happy",
    "분석",
    "디자인",
    "데이터",
    "목업",
    "결정",
    "승인",
    "진행",
    "결과",
    "변이",
    "사이트",
)
EXTEND_WORDS = ("확장", "추가", "더 만들", "이어서")


def _between(text: str, tag: str) -> str:
    match = re.search(rf"<{tag}>(.*?)</{tag}>", text, re.S)
    return match.group(1).strip() if match else ""


def classify(user_message: str) -> dict[str, Any]:
    request = _between(user_message, "user_request")
    sites = [s.strip() for s in _between(user_message, "known_sites").split(",")]
    selected = _between(user_message, "selected_site")
    lowered = request.lower()
    url_match = URL_PATTERN.search(request)
    named = next((s for s in sites if s and s in lowered), None)
    if url_match or (named and any(w in request for w in EXTEND_WORDS)):
        intent = "extend" if any(w in request for w in EXTEND_WORDS) else "new"
        return {
            "intent": intent,
            "url": url_match.group(0) if url_match else None,
            "alias": named,
            "reason": "(가짜 LLM) URL 또는 확장 요청 단어",
        }
    if named or any(w in lowered for w in QUERY_WORDS):
        return {
            "intent": "query",
            "url": None,
            "alias": named or selected or None,
            "reason": "(가짜 LLM) 사이트 관련 단어",
        }
    return {
        "intent": "out_of_scope",
        "url": None,
        "alias": None,
        "reason": "(가짜 LLM) 서비스와 관련 없는 요청",
    }


USERNAME_WORDS = ("아이디", "사번", "사용자", "id", "이메일", "email", "user")
PASSWORD_WORDS = ("비밀번호", "패스워드", "password", "pw")
SUBMIT_WORDS = ("로그인", "login", "sign in")
ELEMENT = re.compile(
    r'- (?P<role>textbox|button|link) "(?P<name>[^"]*)"[^\n]*\[ref=(?P<ref>[a-z0-9_]+)\]'
)


def detect_login(user_message: str) -> dict[str, Any]:
    page = _between(user_message, "page_content")
    username = password = submit = None
    for m in ELEMENT.finditer(page):
        name = m.group("name").lower()
        if m.group("role") == "textbox":
            if password is None and any(w in name for w in PASSWORD_WORDS):
                password = m.group("ref")
            elif username is None and any(w in name for w in USERNAME_WORDS):
                username = m.group("ref")
        elif submit is None and any(w in name for w in SUBMIT_WORDS):
            submit = m.group("ref")
    if username and password and submit:
        return {
            "kind": "id_pw",
            "username_ref": username,
            "password_ref": password,
            "submit_ref": submit,
            "reason": "(가짜 LLM) 아이디·비밀번호 입력란과 로그인 버튼",
        }
    if "인증서" in page or "간편인증" in page:
        kind = "simple_auth" if "간편인증" in page else "certificate"
        reason = "(가짜 LLM) 인증 안내 문구"
    else:
        kind, reason = "none", "(가짜 LLM) 로그인 입력란 없음"
    return {
        "kind": kind,
        "username_ref": None,
        "password_ref": None,
        "submit_ref": None,
        "reason": reason,
    }


SCREEN_LINE = re.compile(r"^- screen (\S+) \| ([^|]*) \|", re.M)
# ref는 페이지를 여러 번 열면 f4e37처럼 앞에 글자가 붙는다
REF_LINE = re.compile(r'- (?P<role>[a-z]+) "(?P<name>[^"]*)"[^\n]*\[ref=(?P<ref>[a-z0-9_]+)\]')


def _score(menu: int, completeness: int, domain: int, reuse: int) -> dict[str, int]:
    return {"menu": menu, "completeness": completeness, "domain": domain, "reuse": reuse}


def hypothesize(user_message: str) -> dict[str, Any]:
    sitemap = _between(user_message, "sitemap")
    candidates: list[dict[str, Any]] = []
    others: list[dict[str, Any]] = []
    for line in sitemap.splitlines():
        m = SCREEN_LINE.match(line)
        if not m:
            continue
        screen_id, title = m.group(1), m.group(2).strip()
        base = {"start_screen_id": screen_id, "reason": "(가짜 LLM) 화면 구성 규칙"}
        if "표(" in line and "폼:" in line:
            candidates.append(
                {
                    **base,
                    "name": f"{title} 검색",
                    "goal": "검색어를 넣고 조회해 결과 목록을 본다",
                    "kind": "search",
                    "expected_steps": ["검색어 입력", "조회", "결과 목록"],
                    "score": _score(4, 4, 4, 4),
                }
            )
        if "표(" in line:
            candidates.append(
                {
                    **base,
                    "name": f"{title} 상세 조회",
                    "goal": "목록에서 글 하나를 눌러 상세 내용을 본다",
                    "kind": "view",
                    "expected_steps": ["목록", "제목 클릭", "상세"],
                    "score": _score(4, 5, 4, 3),
                }
            )
        else:
            others.append(
                {
                    **base,
                    "name": f"{title} 보기",
                    "goal": "화면 내용을 본다",
                    "kind": "other",
                    "expected_steps": [title],
                    "score": _score(2, 1, 2, 1),
                }
            )
    candidates += others[: max(0, 5 - len(candidates))]
    return {
        "site": {
            "domain": "(가짜 LLM) 업무 포털",
            "users": "내부 직원",
            "core_tasks": ["공지 조회", "검색"],
        },
        "candidates": candidates[:7],
    }


def _walk_answer(action: str, reason: str, **fields: Any) -> dict[str, Any]:
    base = {"target_ref": None, "text": None, "input_kind": None, "fail_kind": None}
    return {**base, "action": action, "reason": f"(가짜 LLM) {reason}", **fields}


def walk_step(user_message: str) -> dict[str, Any]:
    goal = _between(user_message, "flow_goal")
    kind = next(
        (ln.split(":", 1)[1].strip() for ln in goal.splitlines() if ln.startswith("kind:")), ""
    )
    done = sum(1 for ln in _between(user_message, "steps_so_far").splitlines() if ln[:1].isdigit())
    page = _between(user_message, "page_content")
    elements = [m.groupdict() for m in REF_LINE.finditer(page)]
    table_at = page.find("- table")
    table_links = [
        m.groupdict()
        for m in REF_LINE.finditer(page)
        if m.group("role") == "link" and table_at >= 0 and m.start() > table_at
    ]
    if kind == "view":
        if done == 0 and table_links:
            return _walk_answer("click", "표 안 첫 링크", target_ref=table_links[0]["ref"])
        if done >= 1:
            return _walk_answer("done", "상세 화면 도착")
        return _walk_answer("give_up", "표 링크 없음", fail_kind="no_data")
    if kind == "search":
        if done == 0:
            box = next(
                (e for e in elements if e["role"] == "textbox" and "검색어" in e["name"]),
                next((e for e in elements if e["role"] == "textbox"), None),
            )
            if box is None:
                return _walk_answer("give_up", "검색어 입력란 없음", fail_kind="not_found")
            word = table_links[0]["name"][:2] if table_links else "안내"
            return _walk_answer(
                "type", "검색어 입력", target_ref=box["ref"], text=word, input_kind="검색어"
            )
        if done == 1:
            button = next(
                (e for e in elements if e["role"] == "button" and e["name"] in ("조회", "검색")),
                None,
            )
            if button is None:
                return _walk_answer("press_enter", "조회 버튼 없음")
            return _walk_answer("click", "조회", target_ref=button["ref"])
        if "결과가 없습니다" in page:
            return _walk_answer("give_up", "검색 결과 없음", fail_kind="no_data")
        return _walk_answer("done", "검색 결과 도착")
    return _walk_answer("give_up", "걸을 단계가 정해지지 않음", fail_kind="not_found")


class _FakeMessages:
    async def create(self, **kwargs: Any) -> Any:
        content = kwargs["messages"][-1]["content"]
        text = (
            content
            if isinstance(content, str)
            else "".join(b.get("text", "") for b in content if isinstance(b, dict))
        )
        if "<flow_goal>" in text:
            answer = walk_step(text)
        elif "<sitemap>" in text:
            answer = hypothesize(text)
        elif "<page_content>" in text:
            answer = detect_login(text)
        else:
            answer = classify(text)
        return SimpleNamespace(
            model="fake-llm",
            stop_reason="end_turn",
            stop_details=None,
            usage=SimpleNamespace(input_tokens=0, output_tokens=0),
            content=[SimpleNamespace(type="text", text=json.dumps(answer, ensure_ascii=False))],
        )


class FakeLlmClient:
    """LlmGateway가 쓰는 client.beta.messages.create 모양만 맞춘다."""

    def __init__(self) -> None:
        self.beta = SimpleNamespace(messages=_FakeMessages())
