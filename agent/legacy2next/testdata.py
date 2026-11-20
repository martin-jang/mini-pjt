"""빈 화면용 합성 데이터 (T07e, G11).

data_schema.json이 inferred(구조만 봤음)인 화면에 대해 LLM 없이 규칙으로 레코드를 만든다.
- 값은 타입별 형식만 맞춘 가짜 값이다 (G5 자리표시자 형식). 수집한 실제 값은 복사하지 않는다
- 모든 레코드에 source="synthetic"이 붙는다 (FixtureRecord 모델에서 필수)
- 저장은 crawl/fixtures/에만 하고, 저장하면 그 화면 data_schema의 출처가 synthetic이 된다
"""

from __future__ import annotations

from datetime import date, timedelta

from .crawl import CrawlStore, DataEntity, DataField, FixtureRecord, FixtureSet, now_iso

RECORDS = 5
BASE_DATE = date(2026, 1, 1)


def synthetic_value(field: DataField, n: int) -> str | int:
    """n번째(1부터) 레코드의 합성 값. 같은 입력이면 같은 값이 나온다."""
    match field.type:
        case "number":
            return n
        case "money":
            return 10000 * n
        case "date":
            return (BASE_DATE + timedelta(days=7 * (n - 1))).isoformat()
        case "phone":
            return f"010-0000-{n:04d}"
        case "email":
            return f"user{n}@example.com"
        case "name":
            return f"테스트사용자{n}"
        case "code":
            return f"CODE-{n:04d}"
        case _:
            return f"{field.label or field.name} 예시 {n}"


def synthesize(screen_id: str, entity: DataEntity, count: int = RECORDS) -> FixtureSet:
    records = [
        FixtureRecord(
            source="synthetic",
            values={f.name: synthetic_value(f, n) for f in entity.fields},
        )
        for n in range(1, count + 1)
    ]
    return FixtureSet(
        screen_id=screen_id,
        entity=entity.name,
        source="synthetic",
        generated_at=now_iso(),
        fields=entity.fields,
        records=records,
    )


def fill_empty_screens(store: CrawlStore, screen_ids: list[str]) -> list[FixtureSet]:
    """구조만 본(inferred) 화면마다 첫 목록·상세 묶음에 합성 데이터를 만든다."""
    made: list[FixtureSet] = []
    for screen_id in screen_ids:
        schema = store.load_data_schema(screen_id)
        if schema is None or schema.source != "inferred":
            continue
        entity = next(
            (e for e in schema.entities if e.kind in ("list", "detail") and e.fields), None
        )
        if entity is None:
            continue
        fixture = synthesize(screen_id, entity)
        store.save_fixture(fixture)
        made.append(fixture)
    return made
