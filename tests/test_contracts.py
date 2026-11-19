"""API 계약 결정적 생성 테스트 (LLM·네트워크 없음)."""

from src.analyst.inventory import Field_, Screen, Table
from src.codegen import contracts as ct


def test_dummy_and_date_format():
    assert ct.dummy("[ACCOUNT]", 0) == "10001" and ct.dummy("[ACCOUNT]", 2) == "10003"
    assert ct.to_format("12-11-2025", "YYYY-MM-DD") == "2025-12-11"
    assert ct.to_format("20251211", "YYYY-MM-DD") == "2025-12-11"
    assert ct.to_format("Check # 1111", "YYYY-MM-DD") == "Check # 1111"


def test_vary_changes_money_only():
    assert ct._vary("$100.00", 1) == "$137.00"
    assert ct._vary("10001", 1) == "10001"


def test_ident_and_slug():
    assert ct.ident("Debit (-)") == "debit" and ct.ident("payee.name") == "payeeName"
    s = Screen(screen_id="x", domain="d", url="https://d/app/activity.htm?id=1", url_pattern="//d/app/activity.htm?id={value}",
               title="t", requires_login=True)
    assert ct.screen_slug(s) == "activity"
    s.result_of = "transfer"
    assert ct.screen_slug(s) == "activityResult"


def test_render_is_deterministic():
    contract = {"domain": "d", "date_format": None, "endpoints": [
        {"slug": "overview", "title": "계좌 개요", "kind_api": "list", "path": "/api/overview",
         "columns": [{"key": "account", "header": "Account"}], "rows": [{"account": "10001"}], "details": {}},
        {"slug": "transfer", "title": "계좌 이체", "kind_api": "submit", "path": "/api/transfer",
         "options_path": "/api/transfer/options",
         "fields": [{"key": "fromAccountId", "type": "select", "options": ["10001"]}]}]}
    a, b = ct.render_client(contract), ct.render_client(contract)
    assert a == b and "export function getOverview" in a and "export function submitTransfer" in a
    h = ct.render_handlers(contract)
    assert "http.get('/api/overview'" in h and "http.post('/api/transfer'" in h and "LLM 작성 금지" in h


def test_slug_map_resolves_same_file_names():
    """파일명이 같은 화면(디렉터리만 다름·쿼리만 다름)도 slug 가 겹치지 않아야 API 함수·화면 이름이 충돌하지 않음."""
    from types import SimpleNamespace as NS

    from src.analyst.naming import slug_map

    screens = [NS(screen_id="a", url_pattern="//h/x/bbs/selectList.do?id={value}", result_of=None),
               NS(screen_id="b", url_pattern="//h/x/bbs/admin/selectList.do?id={value}", result_of=None),
               NS(screen_id="c", url_pattern="//h/x/role/list.do", result_of=None),
               NS(screen_id="d", url_pattern="//h/x/role/list.do?page={value}", result_of=None),
               NS(screen_id="e", url_pattern="//h/x/other.do", result_of=None)]
    m = slug_map(screens)
    assert len(set(m.values())) == len(m)
    assert m["e"] == "other"
    assert m == slug_map(list(reversed(screens)))  # 순서와 무관하게 결정적


def test_unique_keys_for_non_ascii_headers():
    from src.codegen.contracts import _unique_keys
    from src.analyst.naming import ident

    keys = _unique_keys([ident(h) for h in ["번호", "제목", "Date", "date"]], "col")
    assert keys == ["col1", "col2", "date", "date2"]
