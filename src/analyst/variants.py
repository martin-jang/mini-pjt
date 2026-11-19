"""Analyst ② 변이 클러스터링 (T08, 도구 cluster_ui_variants).

화면 간 '같은 역할로 보이는' UI 요소를 묶어 변이 그룹을 만듭니다. 묶는 근거는 SERVICE.md 설계대로
  1) 구조: 요소 종류별로 먼저 나눔 (버튼 / 테이블 컬럼 / 날짜 형식 / 배치 / 흐름 / 테이블 기능)
  2) 의미: 버튼·테이블 컬럼은 '라벨 + 화면 맥락'을 임베딩해 코사인 유사도로 묶음 (평균 연결 군집)
  3) 맥락: 임베딩 문장에 화면 목적·주변 필드를 넣어, 같은 라벨이라도 역할이 다르면 떨어지게 함
같은 화면 안의 요소끼리는 변이로 보지 않고, 실제로 값이 서로 다른 그룹만 남깁니다.
사이트 고유 값은 없습니다. 모든 기준은 인벤토리 데이터에서 계산합니다.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any, Literal

from pydantic import BaseModel

from src.analyst.inventory import Screen
from src.llm import default_embeddings

ElementType = Literal["action_button", "table_columns", "date_format", "layout", "flow", "table_feature"]

# 동작·정보 차이를 만드는 요소 종류: 자동 통일 금지 대상 (과잉 통일 방지)
PROTECTED_TYPES: set[str] = {"flow", "table_feature"}

# 실험값: 같은 역할 버튼 0.55~0.79, 다른 역할 0.26~0.38 → 두 구간 사이(0.45)로 두어 화면 목적 문장이
# 조금 바뀌어도 같은 역할 버튼이 떨어지지 않게 함 (0.50은 경계선이라 재실행마다 흔들렸음)
BUTTON_THRESHOLD = 0.45
COLUMN_THRESHOLD = 0.70


class Member(BaseModel):
    screen_id: str
    value: Any
    context: str = ""


class VariantGroup(BaseModel):
    group_id: str
    element_type: ElementType
    role_hint: str
    members: list[Member]

    @property
    def distinct_values(self) -> list[Any]:
        return list(dict.fromkeys(str(m.value) for m in self.members))


# ──────────────────────────────────────────────────────────────────
# 유틸
# ──────────────────────────────────────────────────────────────────


def _cos(a: list[float], b: list[float]) -> float:
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(y * y for y in b))
    return sum(x * y for x, y in zip(a, b)) / (na * nb) if na and nb else 0.0


def cluster(vectors: list[list[float]], threshold: float, owners: list[str]) -> list[list[int]]:
    """평균 연결 응집 군집. 두 군집의 평균 유사도가 threshold 이상이면 합칩니다.

    owners: 각 요소가 속한 화면 ID. 같은 화면 요소만으로 이뤄진 군집끼리는 합치지 않습니다
    (같은 화면 안의 서로 다른 버튼은 변이가 아니라 다른 기능).
    """
    clusters = [[i] for i in range(len(vectors))]
    sim = [[_cos(vectors[i], vectors[j]) for j in range(len(vectors))] for i in range(len(vectors))]
    while True:
        best, pair = threshold, None
        for a in range(len(clusters)):
            for b in range(a + 1, len(clusters)):
                if {owners[i] for i in clusters[a]} & {owners[i] for i in clusters[b]}:
                    continue  # 같은 화면 요소가 섞이면 합치지 않음
                s = sum(sim[i][j] for i in clusters[a] for j in clusters[b]) / (len(clusters[a]) * len(clusters[b]))
                if s >= best:
                    best, pair = s, (a, b)
        if pair is None:
            return clusters
        a, b = pair
        clusters[a] += clusters.pop(b)


_DATE_PATTERNS = [
    ("YYYY-MM-DD", r"\d{4}-\d{2}-\d{2}"), ("MM-DD-YYYY", r"\d{2}-\d{2}-\d{4}"),
    ("YYYY/MM/DD", r"\d{4}/\d{2}/\d{2}"), ("MM/DD/YYYY", r"\d{2}/\d{2}/\d{4}"),
    ("DD.MM.YYYY", r"\d{2}\.\d{2}\.\d{4}"), ("YYYYMMDD", r"(19|20)\d{6}"),
]


def detect_date_format(cell: str) -> str | None:
    """셀 값의 날짜 표기 형식을 규칙으로 판별합니다."""
    for name, pat in _DATE_PATTERNS:
        if re.fullmatch(pat, (cell or "").strip()):
            return name
    return None


def field_label(f) -> str:
    """사람이 읽을 필드 이름. 레거시 화면에서 라벨이 ':'·'and' 같은 조각으로 잡히면 필드 name을 씁니다."""
    label = (f.label or "").strip(" :*#$")
    return label if len(label) >= 3 and label.lower() not in {"and", "between", "or", "to"} else (f.name or label)


def _ctx(s: Screen) -> str:
    fields = ", ".join(field_label(f) for f in s.fields[:6])
    return f"화면 '{s.title}' ({s.kind}: {s.purpose}) 필드: {fields}"


# ──────────────────────────────────────────────────────────────────
# 요소 수집 → 그룹
# ──────────────────────────────────────────────────────────────────


def _semantic_groups(kind: ElementType, elems: list[tuple[str, str, str]], threshold: float,
                     embeddings, prefix: str) -> list[VariantGroup]:
    """(screen_id, value, 임베딩 문장) 목록을 임베딩 군집으로 묶습니다."""
    if len(elems) < 2:
        return []
    vectors = embeddings.embed_documents([e[2] for e in elems])
    groups = []
    for idx, members in enumerate(cluster(vectors, threshold, [e[0] for e in elems])):
        ms = [Member(screen_id=elems[i][0], value=elems[i][1], context=elems[i][2]) for i in members]
        groups.append(VariantGroup(group_id=f"{prefix}{idx + 1}", element_type=kind,
                                   role_hint="" if kind != "table_columns" else "테이블 컬럼 구성", members=ms))
    return groups


def collect_groups(screens: list[Screen], embeddings=None) -> list[VariantGroup]:
    """업무 화면들에서 변이 그룹을 만듭니다. 실제로 값이 2가지 이상인 그룹만 돌려줍니다."""
    biz = [s for s in screens if s.is_business and s.kind != "결과"]
    embeddings = embeddings or default_embeddings()
    groups: list[VariantGroup] = []

    # 1) 실행 버튼: 라벨 + 화면 맥락 임베딩
    buttons = [(s.screen_id, b, f"button '{b}' on {_ctx(s)}") for s in biz for b in s.buttons]
    groups += _semantic_groups("action_button", buttons, BUTTON_THRESHOLD, embeddings, "BTN")

    # 2) 테이블 컬럼 구성: 컬럼 수가 같은 테이블끼리, 헤더 + 맥락 임베딩
    by_width: dict[int, list[tuple[str, str, str]]] = {}
    for s in biz:
        for t in s.tables:
            if len(t.headers) >= 2 and all(t.headers):
                cols = " / ".join(t.headers)
                by_width.setdefault(len(t.headers), []).append((s.screen_id, cols, f"table columns [{cols}] on {_ctx(s)}"))
    for width, elems in by_width.items():
        groups += _semantic_groups("table_columns", elems, COLUMN_THRESHOLD, embeddings, f"COL{width}_")

    # 3) 날짜 표기 형식: 규칙 판별 (명시값 우선, 없으면 샘플 행에서 판별)
    dates = []
    for s in biz:
        for t in s.tables:
            fmt = t.date_format or next((f for c in t.sample_row if (f := detect_date_format(c))), None)
            if fmt:
                dates.append(Member(screen_id=s.screen_id, value=fmt, context=_ctx(s)))
    if dates:
        groups.append(VariantGroup(group_id="DATE1", element_type="date_format", role_hint="날짜 표기 형식", members=dates))

    # 4) 배치 · 5) 흐름 · 6) 테이블 기능: 스냅샷에 구조 정보가 있을 때만
    for key, etype, hint, getter in [
        ("search_panel", "layout", "조회조건 영역 위치", lambda s: s.layout.get("search_panel")),
        ("confirm_step", "flow", "제출 전 확인 단계", lambda s: s.flow.get("confirm_step")),
        ("has_total_row", "table_feature", "목록 합계 행",
         lambda s: next((t.has_total_row for t in s.tables if t.has_total_row is not None), None)),
    ]:
        ms = [Member(screen_id=s.screen_id, value=v, context=_ctx(s)) for s in biz if (v := getter(s)) is not None]
        if ms:
            groups.append(VariantGroup(group_id=key.upper(), element_type=etype, role_hint=hint, members=ms))

    # 서로 다른 화면 2곳 이상 + 값 2가지 이상인 그룹만 '변이'
    return [g for g in groups if len({m.screen_id for m in g.members}) >= 2 and len(g.distinct_values) >= 2]


def majority(values: list[Any]) -> Any:
    """다수결 값 (동률이면 먼저 나온 값)."""
    return Counter(str(v) for v in values).most_common(1)[0][0] if values else None
