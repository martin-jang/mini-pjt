"""Happy Path 근거 검증·testid 계약 테스트 (가짜 LLM)."""

from src.analyst import happy_path as hp
from src.analyst.inventory import Field_, Screen


def _s(sid, kind, login=False, links=(), fields=(), result_of=None):
    # 실제 크롤러처럼 결과 화면은 입력 화면 URL 패턴 + '#result'
    pattern = f"//x/{sid.split('__')[0]}" + ("#result" if result_of else "")
    return Screen(screen_id=sid, domain="x", url=f"https://x/{sid}", url_pattern=pattern, title=sid,
                  requires_login=login, kind=kind, is_business=True, purpose="p", links_to=list(links),
                  fields=[Field_(name=n, type=t) for n, t in fields], result_of=result_of)


SCREENS = [
    _s("home", "안내", fields=[("username", "text"), ("password", "password")]),
    _s("list", "조회", login=True, links=["detail", "pay"]),
    _s("detail", "조회", login=True),
    _s("send", "입력", login=True, fields=[("amount", "text")]),
    _s("send__result", "결과", login=True, result_of="send"),
    _s("pay", "입력", login=True, fields=[("payee", "text")]),
]


def _flow(*steps):
    return hp.ProposedFlow(name="n", why="w", steps=[hp.ProposedStep(screen_id=s, action=a, description="d")
                                                     for s, a in steps])


def test_valid_flows():
    assert hp.validate_flow(_flow(("home", "login"), ("list", "navigate"), ("detail", "view")), SCREENS)[0]
    assert hp.validate_flow(_flow(("home", "login"), ("send", "fill_submit"), ("send__result", "view")), SCREENS)[0]


def test_rejects_ungrounded_flows():
    # 결과 화면 근거가 없는 제출 흐름
    ok, why = hp.validate_flow(_flow(("home", "login"), ("pay", "fill_submit")), SCREENS)
    assert not ok and "결과 화면" in why
    # 수집되지 않은 화면
    assert not hp.validate_flow(_flow(("home", "login"), ("ghost", "view")), SCREENS)[0]
    # 이어지지 않는 단계
    assert not hp.validate_flow(_flow(("detail", "view"), ("list", "view")), SCREENS)[0]


def test_contract_testids_are_screen_scoped():
    c = hp.build_contract(1, _flow(("home", "login"), ("send", "fill_submit"), ("send__result", "view")), SCREENS)
    s1, s2, s3 = c["steps"]
    assert s1["page_testid"] == "home-page" and s1["action_testid"] == "home-submit"
    assert [f["testid"] for f in s1["fields"]] == ["home-field-username", "home-field-password"]
    assert s2["action_testid"] == "send-submit" and s2["next_slug"] == "sendResult"
    assert s3["action_testid"] is None
    c2 = hp.build_contract(2, _flow(("home", "login"), ("list", "navigate"), ("detail", "view")), SCREENS)
    assert c2["steps"][0]["page_testid"] == s1["page_testid"]  # 같은 화면은 흐름이 달라도 같은 ID
    assert c2["steps"][1]["action_testid"] == "list-to-detail"
