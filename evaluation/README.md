# evaluation · 인-아웃 세트 작성 가이드

`test_queries.sample.json`은 **작성 예시**입니다. 실제 평가셋은 이 샘플을 참고해 `test_queries.json`으로 직접 작성합니다. (교육용 샘플이며 실제 업무 데이터는 없습니다.)

- **작성은 JSON**으로 합니다. 리스트 필드는 배열로 씁니다.
- **제출 규약은 CSV**(`test_queries.csv`, ASSIGNMENT.md §4-4)이므로, 작성 후 아래 명령으로 변환합니다.

```bash
python evaluation/json_to_csv.py    # test_queries.json → test_queries.csv
```

변환 시 배열은 세미콜론으로 이어지고, `auto_approve`는 `true/false/null` → `yes/no/빈 칸`이 됩니다.

## 필드 (과제 표준 7개 + 1개)

| 컬럼 | 필수 | 설명 |
|---|:---:|---|
| `id` | ✅ | 1부터 |
| `category` | ✅ | `positive` / `negative` / `edge` / `guardrail` |
| `input` | ✅ | `/query`의 `question`에 그대로 들어갈 질의 |
| `expected_traits` | ✅ | 답변에 반드시 있어야 할 것. 문자열 배열 |
| `forbidden` | | 답변·행동에 나오면 안 되는 것. 문자열 배열 |
| `expected_tools` | | 호출되어야 할 도구. 문자열 배열, 없으면 `[]` |
| `note` | | 의도 메모 |
| `auto_approve` | | **추가 필드**. 생성·분석처럼 HITL이 걸리는 케이스는 `true`, guardrail 케이스는 `false`(승인 요청 자체를 검증), 질의 케이스는 `null` |

## 권장 구성 (20건 기준)

| category | 비율 | 건수 | 이 프로젝트에서 넣을 것 |
|---|:---:|:---:|---|
| positive | 40% | 8 | 화면 필드 질의, 화면→컴포넌트 매핑, 통일 결정 근거, 분석 요청, 생성 요청 |
| negative | 20% | 4 | ParaBank에 없는 기능, 수집하지 않은 화면 (→ "근거 없음") |
| edge | 25% | 5 | 모호한 지시, 합성 변이 픽스처 질의, 로그인 뒤 화면, 같은 화면 다른 URL |
| guardrail | 15% | 3 | SSRF(G1), 승인 없는 이체(G2), 인젝션(G4) — 가능하면 G3·G5도 |

## 작성 팁

- `expected_traits`는 **채점 가능한 문장**으로 씁니다. "좋은 답변" 대신 "출처 화면 URL 인용"처럼.
- 질의 케이스(`expected_tools`에 `retrieve_screens`)만 RAGAS 측정 대상입니다. 생성 케이스는 L3 결정적 검사로 봅니다.
- 실제 화면 필드명은 크롤링 후 스냅샷을 보고 채웁니다. 샘플의 필드 표현은 예시입니다.
- `docs/GUARDRAILS.md`의 G1~G5마다 guardrail 케이스가 최소 1건씩 있으면 가드레일 완성 기준을 검증할 수 있습니다.
