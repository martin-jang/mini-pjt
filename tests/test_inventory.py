"""화면 인벤토리 배선 테스트 (가짜 LLM, 네트워크 없음)."""

from src.analyst import inventory as inv
from tests.fakes import FakeStructuredLLM

SNAPS = [
    {"screen_id": "a_list", "url": "https://x.example/app/list.htm", "url_pattern": "//x.example/app/list.htm",
     "title": "Site | Account List", "requires_login": True,
     "forms": [], "tables": [{"headers": ["Account", "Balance"], "row_count": 3, "sample_rows": [["[ACCOUNT]", "$1"]]}],
     "links": [{"text": "detail", "href": "https://x.example/app/detail.htm?id=[ACCOUNT]"},
               {"text": "admin", "href": "https://x.example/app/admin.htm"}]},
    {"screen_id": "a_detail", "url": "https://x.example/app/detail.htm?id=[ACCOUNT]",
     "url_pattern": "//x.example/app/detail.htm?id={value}", "title": "Site | Detail", "requires_login": True,
     "forms": [{"fields": [{"name": "month", "type": "select", "label": "Period:"}], "buttons": ["Go"]}],
     "tables": [], "links": []},
    {"screen_id": "a_admin", "url": "https://x.example/app/admin.htm", "url_pattern": "//x.example/app/admin.htm",
     "title": "Site | Administration", "requires_login": False, "forms": [], "tables": [], "links": []},
]


def _responder(schema, prompt):
    assert "CRAWLED_DATA" in prompt  # 크롤링 데이터는 데이터 블록으로만 전달 (G4)
    return inv.InventoryJudgement(screens=[
        inv.ScreenJudgement(screen_id="a_list", title_ko="계좌 목록", kind="조회", is_business=True, purpose="계좌 목록"),
        inv.ScreenJudgement(screen_id="a_detail", title_ko="계좌 상세", kind="조회", is_business=True, purpose="계좌 상세"),
        inv.ScreenJudgement(screen_id="a_admin", title_ko="관리자", kind="관리", is_business=False, purpose="관리자"),
    ])


def test_extract_and_link():
    screens = [inv.extract_screen(s) for s in SNAPS]
    inv.link_screens(screens, SNAPS)
    by = {s.screen_id: s for s in screens}
    assert by["a_list"].title == "Account List"
    assert by["a_list"].links_to == ["a_detail", "a_admin"]  # 마스킹된 링크도 같은 화면 패턴으로 연결
    assert by["a_detail"].fields[0].label == "Period:" and by["a_detail"].buttons == ["Go"]


def test_judge_fills_kind_with_single_call():
    screens = [inv.extract_screen(s) for s in SNAPS]
    fake = FakeStructuredLLM(_responder)
    inv.judge_screens(screens, llm=fake)
    assert len(fake.calls) == 1  # 화면 수와 무관하게 1회 호출
    assert {s.screen_id: s.is_business for s in screens} == {"a_list": True, "a_detail": True, "a_admin": False}


def test_missing_snapshots_returns_guidance():
    r = inv.build_screen_inventory("no-such-domain.example", llm=FakeStructuredLLM(_responder))
    assert "error" in r and r["screens"] == []
