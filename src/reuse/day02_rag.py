"""Day 2 RAG 재사용 (sds-ax-training/day02/practice/starter/submission.py 에서 복사).

assess_retrieval(근거 부족 판정, LLM 미호출)과 Kiwi 토크나이저를 그대로 옮겼습니다.
이 프로젝트용 보강(범용어 제외)은 src/retriever.py 에서 합니다.
"""

from __future__ import annotations

from functools import lru_cache

def assess_retrieval(docs, question: str) -> dict:
    """검색 결과가 이 질문에 답하기에 쓸만한지 판정합니다.

    이 함수는 LLM을 호출하지 않습니다. 같은 입력에 항상 같은 출력을 내야 합니다.

    판정 방법은 자유입니다. 예를 들면
      - 질문에서 핵심어를 뽑아 문서 본문에 몇 개나 등장하는지 센다
      - 검색된 문서 개수와 길이를 본다
      - 특정 임계값을 넘는지 확인한다

    Returns:
        {"usable": bool, "reason": str, "matched": int} 형태의 dict.
        usable이 False면 build_rag_chain은 모델을 부르지 않고 거절해야 합니다.
    """
    # ── 판정 방식: BM25 + 핵심어 적중률 ─────────────────────────────
    # 1) 질문과 검색된 문서를 Kiwi 형태소 분석기로 토큰화합니다.
    #    명사·영문·숫자·어근만 남겨 "이월되나요" → "이월", "연차는" → "연차"처럼
    #    조사·어미를 떼고, "어떻게/되나요" 같은 의미 없는 말을 버립니다.
    # 2) 검색된 문서들로 BM25 색인을 만들고 질문의 BM25 점수를 계산합니다.
    #    BM25Okapi가 아니라 BM25Plus를 씁니다. 판정 대상은 검색된 문서 2~3개뿐이라
    #    질문어가 모든 문서에 들어 있으면 Okapi의 IDF가 음수가 되어
    #    "관련 문서인데 점수가 음수"인 역전이 생기기 때문입니다.
    #    BM25Plus는 IDF가 항상 양수라 이런 작은 문서 집합에서도 안정적입니다.
    # 3) usable 조건 (둘 다 만족해야 함)
    #    - BM25 최고점 > 0           : 질문어가 어느 문서에든 걸렸다
    #    - 적중률 >= MIN_MATCH_RATIO : 핵심어의 절반 이상이 본문에 등장한다
    #    적중률 조건을 두는 이유: "사내 헬스장 운영 시간"이 온콜 문서 제목의
    #    "운영" 한 단어로 점수가 0보다 커지는 것을 막기 위해서입니다.
    # 모든 계산이 결정적이므로 같은 입력에는 항상 같은 출력이 나옵니다.
    docs = list(docs or [])
    if not docs:
        return {"usable": False, "reason": "검색된 문서가 없음", "matched": 0}

    q_terms = list(dict.fromkeys(_tokenize(question or "")))  # 순서 유지 중복 제거
    if not q_terms:
        return {"usable": False, "reason": "질문에서 핵심어를 찾지 못함", "matched": 0}

    corpus = [_tokenize(d.page_content or "") for d in docs]
    vocab = {t for toks in corpus for t in toks}
    matched = sum(1 for t in q_terms if t in vocab)

    max_score = 0.0
    if vocab:
        from rank_bm25 import BM25Plus

        # 빈 토큰 목록이 섞이면 평균 길이 계산이 0이 될 수 있어 자리표시 토큰을 넣습니다.
        bm25 = BM25Plus([toks or ["_"] for toks in corpus])
        max_score = float(max(bm25.get_scores(q_terms)))

    ratio = matched / len(q_terms)
    usable = max_score > 0 and ratio >= MIN_MATCH_RATIO
    reason = (
        f"BM25 최고점 {max_score:.2f}, 핵심어 {len(q_terms)}개 중 {matched}개 등장"
        f" (기준: 점수>0, 적중률>={MIN_MATCH_RATIO:.0%})"
    )
    return {"usable": usable, "reason": reason, "matched": matched}


# 핵심어 가운데 이 비율 이상이 검색 문서에 등장해야 usable로 봅니다.
MIN_MATCH_RATIO = 0.5

# 핵심어로 남길 Kiwi 품사 태그입니다.
#   NNG/NNP: 일반·고유명사, SL: 영문(SLA, DBA 등), SN: 숫자, XR: 어근
# 동사·형용사(VV/VA)는 "되다/어떻다/있다"처럼 어느 질문에나 나오는 말이 많아 뺍니다.
_KEEP_TAGS = ("NNG", "NNP", "SL", "SN", "XR")


@lru_cache(maxsize=1)
def _kiwi():
    """Kiwi 객체는 생성 비용이 커서 한 번만 만들어 재사용합니다."""
    from kiwipiepy import Kiwi

    return Kiwi()


def _tokenize(text: str) -> list[str]:
    """텍스트를 BM25용 핵심어 토큰 목록으로 바꿉니다. 영문은 소문자로 통일합니다."""
    if not text.strip():
        return []
    return [
        tok.form.lower()
        for tok in _kiwi().tokenize(text)
        if tok.tag in _KEEP_TAGS
    ]


