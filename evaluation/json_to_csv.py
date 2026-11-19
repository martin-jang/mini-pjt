"""test_queries.json → test_queries.csv 변환 스크립트.

작성은 읽기 쉬운 JSON으로 하고, 제출 규약(ASSIGNMENT.md §4-4)이 요구하는 CSV는 이 스크립트로 만든다.

사용법:
    python evaluation/json_to_csv.py                       # test_queries.json → test_queries.csv
    python evaluation/json_to_csv.py 입력.json 출력.csv

변환 규칙:
- 리스트 필드(expected_traits, forbidden, expected_tools)는 세미콜론("; ")으로 이어 붙인다.
- 컬럼은 과제 표준 7개만 씁니다 (ASSIGNMENT.md §4-4 스키마).
  평가 하네스 전용 필드(auto_approve: 승인 요청 자동 승인 여부)는 JSON에만 두고 CSV에는 내보내지 않습니다.
"""

import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
COLUMNS = ["id", "category", "input", "expected_traits", "forbidden",
           "expected_tools", "note"]
LIST_FIELDS = {"expected_traits", "forbidden", "expected_tools"}
CATEGORIES = {"positive", "negative", "edge", "guardrail"}


def _cell(key: str, value) -> str:
    """JSON 값 하나를 CSV 셀 문자열로 바꾼다."""
    if key in LIST_FIELDS:
        return "; ".join(value or [])
    return "" if value is None else str(value)


def convert(src: Path, dst: Path) -> int:
    """src JSON을 읽어 dst CSV로 쓴다. 필수 값이 비면 어느 케이스인지 알려주고 멈춘다."""
    cases = json.loads(src.read_text(encoding="utf-8"))
    for case in cases:
        missing = [k for k in ("id", "category", "input", "expected_traits") if not case.get(k)]
        if missing:
            sys.exit(f"id={case.get('id')} 필수 값 누락: {', '.join(missing)}")
        if case["category"] not in CATEGORIES:
            sys.exit(f"id={case['id']} category 오류: {case['category']}")

    # 엑셀에서 한글이 깨지지 않도록 BOM 포함 UTF-8로 저장
    with dst.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(COLUMNS)
        for case in cases:
            writer.writerow([_cell(k, case.get(k)) for k in COLUMNS])
    return len(cases)


if __name__ == "__main__":
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "test_queries.json"
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else src.with_suffix(".csv")
    print(f"{convert(src, dst)}건 변환: {src.name} → {dst.name}")
