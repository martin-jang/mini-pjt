"""RAG 적재·검색·근거 없음 판단 (T10, 결정 D18).

채점 핵심인 L1 질의응답 경로입니다.
  - 문서 단위: 화면 1개 = 문서 1개, 통일 결정 1건 = 문서 1개, Happy Path 1개 = 문서 1개 (+ 선정 규칙 문서)
  - 문서 본문은 한국어 틀로 씁니다. 질문은 한국어인데 레거시 화면 라벨은 영어인 경우가 많아,
    한국어 목적·성격·머리말을 넣어야 검색과 근거 판단이 맞물립니다.
  - 검색: 벡터(Chroma, Titan v2) + BM25(Kiwi 토큰) 결과를 RRF로 합치는 하이브리드
  - 근거 판단: Day 2 assess_retrieval (LLM 미호출). 부족하면 모델을 부르지 않고 '근거 없음'
  - contexts 에는 검색된 문서를 그대로 담아 RAGAS가 측정합니다.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from langchain_core.documents import Document

from src.analyst.happy_path import load_happy_paths
from src.analyst.inventory import Screen, load_inventory
from src.analyst.unification import load_decisions
from src.analyst.variants import field_label
from src.config import path as cfg_path
from src.llm import default_embeddings, default_llm, get_text
from src.reuse.day02_rag import MIN_MATCH_RATIO, _tokenize
from src.reuse.day02_rag import assess_retrieval as _day2_assess

COLLECTION = "legacy2next"
NO_ANSWER = "수집된 화면과 분석 결과에서 근거를 찾을 수 없습니다."
TOP_K = 4  # 질문 하나가 보통 화면 1개 + 관련 결정·흐름 1~2개를 필요로 해서 4로 둠

# 이 서비스의 어느 질문에나 나오는 범용어. 근거 판단 핵심어에서 빼야 '주식 매매 화면'처럼
# 없는 기능 질문이 '화면' 한 단어로 근거 있음으로 통과하지 않습니다.
GENERIC_TERMS = {"화면", "필드", "입력", "항목", "정보", "차세대", "레거시", "시스템", "기능", "구성",
                 "컴포넌트", "버튼", "목록", "어떤", "무엇", "뭐", "알려", "어디", "사용", "변경", "asis", "tobe"}


# ──────────────────────────────────────────────────────────────────
# 문서 만들기
# ──────────────────────────────────────────────────────────────────


def screen_doc(s: Screen) -> Document:
    fields = ", ".join(f"{field_label(f)}({f.name}, {f.type})" for f in s.fields) or "없음"
    tables = " | ".join(" / ".join(t.headers) + (f" (날짜 형식 {t.date_format})" if t.date_format else "")
                        for t in s.tables) or "없음"
    fixture = "fixture" in s.domain
    lines = [
        f"화면: {s.title_ko or s.title} (원래 제목 '{s.title}') [{s.kind} 화면{', 로그인 필요' if s.requires_login else ''}]",
        f"시스템: {s.domain}" + (" (교육용 합성 픽스처 시스템, 실제 사이트 아님)" if fixture else " (크롤링한 실제 레거시 시스템)"),
        f"목적: {s.purpose}",
        f"화면 머리글: {', '.join(s.headings) or '없음'}",
        f"주소: {s.url}",
        f"입력 필드: {fields}",
        f"버튼: {', '.join(s.buttons) or '없음'}",
        f"테이블 컬럼: {tables}",
        f"이동 가능 화면: {', '.join(s.links_to[:12]) or '없음'}",
    ]
    if "{value}" in s.url_pattern:
        lines.append(f"URL 패턴: {s.url_pattern} — 쿼리 값(계좌번호 등)만 다른 여러 URL을 같은 화면 1개로 묶었습니다.")
    if s.result_of:
        lines.append(f"이 화면은 '{s.result_of}' 제출 후 표시되는 결과 화면입니다.")
    return Document(page_content="\n".join(lines),
                    metadata={"doc_id": f"screen:{s.screen_id}", "type": "screen", "domain": s.domain,
                              "screen_id": s.screen_id, "source": s.url})


def decision_doc(domain: str, d: dict[str, Any], titles: dict[str, str]) -> Document:
    variants = ", ".join(f"'{v['value']}'({titles.get(v['screen_id'], v['screen_id'])})" for v in d["asis_variants"])
    label = {"unify": "통일", "keep_variant": "변형 유지", "hold": "보류"}[d["decision"]]
    lines = [
        f"통일 결정: {d['role']} [{label}]",
        f"레거시(ASIS) 변이: {variants}",
        f"차세대(TOBE) 표준: {d['standard'] or '표준 없음 (화면별 차이 유지)'}",
        f"근거: {d['reason']} (근거 유형 {d['basis']}, 확신도 {d['confidence']})",
    ]
    if d.get("guard_note"):
        lines.append(f"과잉 통일 방지: {d['guard_note']}")
    return Document(page_content="\n".join(lines),
                    metadata={"doc_id": f"decision:{domain}:{d['group_id']}", "type": "decision", "domain": domain,
                              "source": f"unification_decisions.json#{d['group_id']}"})


def happy_path_docs(domain: str, screens: list[Screen]) -> list[Document]:
    docs = []
    titles = {s.screen_id: s.title for s in screens}
    for f in load_happy_paths(domain):
        steps = " → ".join(f"{titles.get(st['screen_id'], st['screen_id'])}({st['action']})" for st in f["steps"])
        docs.append(Document(
            page_content=f"핵심 업무 흐름(Happy Path): {f['name']}\n단계: {steps}\n선정 이유: {f['why']}",
            metadata={"doc_id": f"happy_path:{domain}:{f['flow_id']}", "type": "happy_path", "domain": domain,
                      "source": f"happy_paths.json#{f['flow_id']}"}))
    # 선정 규칙과, 결과 화면 근거가 없어 흐름에서 제외된 입력 화면 (결정적으로 계산)
    has_result = {s.result_of for s in screens if s.result_of}
    excluded = [s.title for s in screens if s.is_business and s.kind == "입력"
                and not any(s.screen_id.endswith(r) or r in s.screen_id for r in has_result)
                and not any(t.result_of and t.screen_id.startswith(s.screen_id) for t in screens)]
    if docs:
        docs.append(Document(
            page_content=("Happy Path 선정 규칙: 크롤링 근거가 있는 화면으로만 흐름을 만들고, 값을 제출하는 흐름은 "
                          "제출 결과 화면을 실제로 수집한 경우에만 포함합니다. 결과 화면을 수집하려면 상태를 바꾸는 "
                          "제출이 필요하므로 사용자 승인을 받은 이체 1회만 실행했습니다.\n"
                          f"결과 화면 근거가 없어 Happy Path에서 제외된 입력 화면(청구서 납부 등): {', '.join(excluded)}"),
            metadata={"doc_id": f"happy_path:{domain}:rules", "type": "happy_path", "domain": domain,
                      "source": "happy_paths.json#rules"}))
    return docs


def is_fixture(domain: str) -> bool:
    """합성 픽스처 도메인인지 (설정의 fixtures 경로에만 있는 도메인)."""
    return (cfg_path("fixtures") / domain).is_dir() and not (cfg_path("snapshots") / domain).is_dir()


def build_documents(domain: str) -> list[Document]:
    screens = load_inventory(domain)
    biz = [s for s in screens if s.is_business]
    titles = {s.screen_id: s.title for s in screens}
    # 합성 픽스처 화면은 실제 화면의 복제라 화면 질문 검색을 가로챕니다. 픽스처의 정보 가치는 변이에 있고
    # 변이는 통일 결정 문서에 담기므로, 픽스처 도메인은 화면 문서 없이 결정 문서만 적재합니다.
    docs = [] if is_fixture(domain) else [screen_doc(s) for s in biz]
    docs += [decision_doc(domain, d, titles) for d in load_decisions(domain)]
    docs += happy_path_docs(domain, screens)
    return docs


# ──────────────────────────────────────────────────────────────────
# 하이브리드 검색
# ──────────────────────────────────────────────────────────────────


def _vectorstore(embeddings=None):
    from langchain_chroma import Chroma

    return Chroma(collection_name=COLLECTION, embedding_function=embeddings or default_embeddings(),
                  persist_directory=str(cfg_path("chroma")))


def index_documents(domains: list[str], embeddings=None) -> dict[str, Any]:
    """도메인들의 분석 결과를 문서로 만들어 Chroma에 다시 적재합니다 (전체 교체).

    언제 쓰나: 분석(T07~T09)이 끝났거나 다시 돌린 뒤. 질의응답 전에 한 번.
    """
    docs = [d for dom in domains for d in build_documents(dom)]
    vs = _vectorstore(embeddings)
    existing = vs.get().get("ids", [])
    if existing:
        vs.delete(ids=existing)
    if docs:
        vs.add_documents(docs, ids=[d.metadata["doc_id"] for d in docs])
    (cfg_path("chroma") / "_docs.json").write_text(
        json.dumps([{"page_content": d.page_content, "metadata": d.metadata} for d in docs], ensure_ascii=False),
        encoding="utf-8")
    return {"documents": len(docs), "by_type": {t: sum(d.metadata["type"] == t for d in docs)
                                                for t in ("screen", "decision", "happy_path")}}


@dataclass
class HybridRetriever:
    """벡터 검색 + BM25 를 RRF(Reciprocal Rank Fusion)로 합치는 검색기."""

    vectorstore: Any
    documents: list[Document]
    k: int = TOP_K
    _bm25: Any = field(default=None, init=False)

    def __post_init__(self) -> None:
        from rank_bm25 import BM25Plus

        self._bm25 = BM25Plus([_tokenize(d.page_content) or ["_"] for d in self.documents]) if self.documents else None

    def invoke(self, question: str) -> list[Document]:
        if not question.strip() or not self.documents:
            return []
        rrf: dict[str, float] = {}
        by_id = {d.metadata["doc_id"]: d for d in self.documents}
        vec = self.vectorstore.similarity_search(question, k=self.k * 2)
        for rank, d in enumerate(vec):
            rrf[d.metadata["doc_id"]] = rrf.get(d.metadata["doc_id"], 0) + 1 / (60 + rank)
        scores = self._bm25.get_scores(_tokenize(question))
        for rank, i in enumerate(sorted(range(len(scores)), key=lambda i: -scores[i])[: self.k * 2]):
            if scores[i] > 0:
                did = self.documents[i].metadata["doc_id"]
                rrf[did] = rrf.get(did, 0) + 1 / (60 + rank)
        top = sorted(rrf, key=lambda k: -rrf[k])[: self.k]
        return [by_id[i] for i in top if i in by_id]


def load_retriever(embeddings=None, k: int = TOP_K) -> HybridRetriever:
    p = cfg_path("chroma") / "_docs.json"
    docs = [Document(**d) for d in json.loads(p.read_text(encoding="utf-8"))] if p.exists() else []
    return HybridRetriever(vectorstore=_vectorstore(embeddings), documents=docs, k=k)


# ──────────────────────────────────────────────────────────────────
# 근거 판단 + 답변
# ──────────────────────────────────────────────────────────────────


def assess(docs: list[Document], question: str) -> dict[str, Any]:
    """Day 2 assess_retrieval 에 범용어 제외를 더한 판정. 범용어만 있는 질문은 원래 판정을 그대로 씀."""
    core = [t for t in dict.fromkeys(_tokenize(question)) if t not in GENERIC_TERMS]
    if not core:
        return _day2_assess(docs, question)
    vocab = {t for d in docs for t in _tokenize(d.page_content)}
    matched = sum(t in vocab for t in core)
    ratio = matched / len(core)
    return {"usable": bool(docs) and ratio >= MIN_MATCH_RATIO, "matched": matched,
            "reason": f"핵심어 {core} 중 {matched}개 등장 (기준 {MIN_MATCH_RATIO:.0%})"}


_ANSWER_SYSTEM = (
    "당신은 레거시 시스템 분석 결과를 설명하는 아키텍트입니다. 반드시 [근거 문서]에 있는 내용만 사용해 "
    "한국어 존댓말로 답하세요. 화면에 대한 답에는 근거 화면의 주소(URL)를 함께 적으세요. "
    "질문의 일부만 근거가 있으면 확인된 범위에서 답하고, 질문과 근거가 다른 부분(예: 질문에 나온 라벨이 실제 변이 목록에 없음)은 "
    "그렇다고 밝히세요. 교육용 합성 픽스처 시스템의 근거를 쓸 때는 그 사실을 밝히세요. "
    "질문에 쓴 화면 이름은 문서의 한국어 화면명과 다를 수 있습니다(예: '계좌 상세'와 '계좌 활동 내역'). "
    "원래 제목·화면 머리글·목적을 보고 같은 화면이면 그 화면으로 답하고, 어떤 화면으로 판단했는지 밝히세요. "
    "근거 문서에 관련 내용이 전혀 없으면 추측하지 말고 '" + NO_ANSWER + "'라고만 답하세요."
)


def answer_question(question: str, retriever: HybridRetriever | None = None, llm=None) -> dict[str, Any]:
    """질문에 근거 기반으로 답합니다. 근거가 부족하면 모델을 부르지 않습니다.

    Returns: {"answer", "contexts": [{"doc_id","text"}], "sources", "grounded", "assessment"}
    """
    retriever = retriever or load_retriever()
    docs = retriever.invoke(question)
    verdict = assess(docs, question)
    contexts = [{"doc_id": d.metadata["doc_id"], "text": d.page_content} for d in docs]
    if not verdict["usable"]:
        return {"answer": NO_ANSWER, "contexts": contexts, "sources": [], "grounded": False, "assessment": verdict}
    llm = llm or default_llm()
    context = "\n\n".join(f"[{d.metadata['doc_id']}]\n{d.page_content}" for d in docs)
    answer = get_text(llm.invoke([("system", _ANSWER_SYSTEM),
                                  ("human", f"[근거 문서]\n{context}\n\n[질문]\n{question}")])).strip()
    if NO_ANSWER in answer:
        return {"answer": NO_ANSWER, "contexts": contexts, "sources": [], "grounded": False, "assessment": verdict}
    sources = list(dict.fromkeys(d.metadata.get("source") for d in docs if d.metadata.get("source")))
    return {"answer": answer, "contexts": contexts, "sources": sources, "grounded": True, "assessment": verdict}
