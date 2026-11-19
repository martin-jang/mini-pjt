"""RAG 근거 판단·답변 배선 테스트 (가짜 검색기·가짜 LLM, 네트워크 없음)."""

from langchain_core.documents import Document

from src import retriever as rt


class FakeRetriever:
    def __init__(self, docs):
        self.docs = docs

    def invoke(self, q):
        return self.docs


class FakeChat:
    def __init__(self, text):
        self.text, self.calls = text, 0

    def invoke(self, messages):
        self.calls += 1
        return type("M", (), {"content": self.text})()


DOC = Document(page_content="화면: Transfer Funds [입력 화면]\n목적: 계좌 간 자금을 이체하는 화면\n"
                            "주소: https://x.example/transfer\n입력 필드: Amount(input, text)",
               metadata={"doc_id": "screen:t", "type": "screen", "source": "https://x.example/transfer"})


def test_generic_terms_do_not_make_unrelated_question_usable():
    # '화면·필드'만 겹치고 핵심어(주식·매매)는 없음 → 근거 없음
    assert rt.assess([DOC], "주식 매매 화면에 어떤 필드가 있어?")["usable"] is False
    assert rt.assess([DOC], "이체 화면에 어떤 입력 필드가 있어?")["usable"] is True


def test_no_model_call_without_grounds():
    llm = FakeChat("x")
    r = rt.answer_question("주식 매매 화면 필드?", retriever=FakeRetriever([DOC]), llm=llm)
    assert r["answer"] == rt.NO_ANSWER and llm.calls == 0 and r["grounded"] is False


def test_grounded_answer_has_contexts_and_sources():
    llm = FakeChat("이체 화면의 입력 필드는 Amount입니다. (https://x.example/transfer)")
    r = rt.answer_question("이체 화면 입력 필드", retriever=FakeRetriever([DOC]), llm=llm)
    assert r["grounded"] and r["contexts"][0]["doc_id"] == "screen:t" and r["sources"] == ["https://x.example/transfer"]


def test_model_refusal_becomes_no_answer():
    r = rt.answer_question("이체 화면 입력 필드", retriever=FakeRetriever([DOC]), llm=FakeChat(rt.NO_ANSWER))
    assert r["grounded"] is False and r["sources"] == []
