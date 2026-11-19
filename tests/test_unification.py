"""변이 클러스터링·통일 결정 배선 테스트 (가짜 임베딩·가짜 LLM)."""

from src.analyst import unification as un
from src.analyst import variants as va
from src.analyst.inventory import Screen, Table
from tests.fakes import FakeStructuredLLM


class FakeEmbeddings:
    """라벨에 'search' 계열 단어가 있으면 같은 방향 벡터를 돌려주는 가짜 임베딩."""

    def embed_documents(self, texts):
        def vec(t):
            t = t.lower()
            if any(w in t for w in ("'go'", "'search'", "'조회'")):
                return [1.0, 0.0]
            return [0.0, 1.0]
        return [vec(t) for t in texts]


def _screen(sid, buttons=(), date=None, flow=None):
    return Screen(screen_id=sid, domain="x.example", url=f"https://x.example/{sid}", url_pattern=f"//x.example/{sid}",
                  title=sid, requires_login=True, kind="조회", is_business=True, purpose="p", buttons=list(buttons),
                  tables=[Table(headers=["Date", "Amount"], sample_row=[date or "", "$1"])] if date else [],
                  flow=flow or {})


SCREENS = [
    _screen("a", ["Go"], "12-11-2025", {"confirm_step": True}),
    _screen("b", ["Search"], "2025/12/11", {"confirm_step": False}),
    _screen("c", ["조회"], "2025/12/11"),
]


def test_collect_groups_buttons_dates_flow():
    groups = va.collect_groups(SCREENS, embeddings=FakeEmbeddings())
    types = {g.element_type: g for g in groups}
    assert set(types) == {"action_button", "date_format", "flow"}
    assert sorted(m.value for m in types["action_button"].members) == ["Go", "Search", "조회"]
    assert set(types["date_format"].distinct_values) == {"MM-DD-YYYY", "YYYY/MM/DD"}


def test_same_screen_elements_never_merge():
    clusters = va.cluster([[1, 0], [1, 0]], 0.5, owners=["s1", "s1"])
    assert clusters == [[0], [1]]


def test_protected_group_is_never_unified():
    groups = va.collect_groups(SCREENS, embeddings=FakeEmbeddings())

    def responder(schema, prompt):  # 모델이 모든 그룹을 통일하라고 '잘못' 답하는 경우
        return un.Decisions(decisions=[
            un.GroupDecision(group_id=g.group_id, role="r", decision="unify", standard="X", basis="majority",
                             reason="r", confidence=0.9) for g in groups])

    records = {r["element_type"]: r for r in un.decide(groups, llm=FakeStructuredLLM(responder))}
    assert records["flow"]["decision"] == "keep_variant" and records["flow"]["guard_note"]
    assert records["action_button"]["decision"] == "unify"


def test_missing_model_answer_becomes_hold():
    groups = va.collect_groups(SCREENS, embeddings=FakeEmbeddings())
    records = un.decide(groups, llm=FakeStructuredLLM(lambda s, p: un.Decisions(decisions=[])))
    assert all(r["decision"] == "hold" for r in records)
