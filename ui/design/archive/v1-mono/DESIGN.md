# DESIGN.md — Legacy2Next 콘솔 디자인 규칙

Stitch 프로젝트 `Legacy2Next-console` (`projects/226818788639833589`), 디자인 시스템 `Legacy2Next Console Mono Light` (`assets/13611052727867864415`).
화면 원본: `screens/*.html` (Stitch 생성 HTML), `screens/*.png` (로컬 렌더링, 1440px 폭).

## 톤

모던 백오피스. 밝은 모노톤(zinc 계열) 위주, 강조색은 차분한 슬레이트 하나만. 상태 색은 작은 점으로만 쓰고 면을 칠하지 않는다. 그림자·그라데이션·발광·펄스 없음.

## 토큰 (Tailwind 테마로 옮길 값)

| 토큰 | 값 | 용도 |
|---|---|---|
| `page` | `#FCFCFC` | 페이지 배경 |
| `card` | `#FFFFFF` | 카드·패널 |
| `subtle` | `#F7F7F8` | 활성 메뉴, 입력, 로그 패널, 아이콘 박스, 테이블 헤더 |
| `line` | `#ECECEF` | 1px 테두리 |
| `ink` | `#27272A` | 본문 글자 |
| `ink-2` | `#71717A` | 보조 글자 |
| `ink-3` | `#A1A1AA` | 흐린 글자·타임스탬프 |
| `primary` | `#3F3F46` | 주요 버튼(흰 글자), 활성 탭 |
| `accent` | `#64748B` | 활성 메뉴 왼쪽 바, 진행 바, 포커스, 링크 |
| 상태 점 success / waiting / error / pending | `#5E8C6E` / `#B8904F` / `#B05250` / `#C4C4CC` | 완료 / 승인 대기 / 차단·오류 / 대기 |
| 폰트 | `Noto Sans KR`, 로그·경로는 `JetBrains Mono` | |
| 모서리 | 4px | 카드·버튼·배지 |

아이콘: Material Symbols Outlined (색은 `ink-2`).

## 컴포넌트 규칙

- 주요 버튼: `primary` 배경 + 흰 글자. 보조 버튼: 흰 배경 + `line` 테두리 + `primary` 글자. 위험 동작(중단 등): 흰 배경 + 테두리 + `error` 글자
- 상태 배지: 흰 배경 + `line` 테두리 + `primary` 글자 + 작은 상태 점. 배경을 상태 색으로 칠하지 않는다
- 경고·안내 박스: `subtle` 배경 + 왼쪽 테두리(상태 색)
- 로그 뷰어: `subtle` 배경 monospace. 경고·차단 줄은 왼쪽 테두리 색으로만 표시

## 레이아웃

- 좌측 고정 사이드바 256px: 로고 → "+ 새 요청" → 사이트 목록(상태 배지) → 하단 "질의". 활성 항목은 `subtle` 배경 + 왼쪽 2px `accent` 바
- 상단 고정 헤더 64px, 본문은 `page` 배경 위 흰 카드(1px 테두리, 그림자 없음)

## 화면

| 파일 | 화면 |
|---|---|
| `01-new-request` | 새 요청 (URL·별칭·요청 유형, 프로세스 개요) |
| `02-progress` | 실행 진행 상황 (단계 스테퍼, SSE 로그, 요약, 가드레일 이벤트) |
| `03-analysis-review` | 분석 리뷰 승인 (사이트 성격, Happy Path, 데이터 방식, 변이 통일) |
| `04-design-review` | 디자인 확인 승인 (화면 목록, ASIS·TOBE 비교, 대폭 변경 개별 승인) |
| `05-result` | 결과 (지표, 생성 화면, 공통 컴포넌트, 결정, 검증) |
| `06-query` | 질의 (추천 질문, 채팅, 범위 밖 거절) |

## 구현 시 바로잡을 예시 문구

Stitch가 프롬프트를 고쳐 쓰며 넣은 내용 중 기획과 다른 것. **레이아웃·구성·톤만 따르고**, 아래 문구는 T02 구현 때 기획에 맞게 바꾼다.

- "Next.js" 표기 전부 (01 헤더 배지·④ 단계 설명, 04 TOBE 라벨, 06 답변·표 헤더) → 생성 스택은 Vite + React + TS + Tailwind
- 05 결과물 경로 `workspace/artifacts/vite-pjt/…` → `next-pjt/<별칭>/`
- 05 "Radix UI", "웹 접근성(A11y)", "반응형 뷰포트" 검사 → 우리 Verifier 항목(빌드, Happy Path 흐름, 기능 보존, 계정 원문 검색, 가드레일)으로
- 05 "코드 저장소" 버튼, 02 "브라우저 실시간 미리보기" 버튼 → 기획에 없음, 제외
- 02·03 가드레일 예시(CDN 스크립트 격리, 토큰 오버라이드 승인 등) → GUARDRAILS.md G1~G9 이벤트로
- 03 "MSW v2.0", "Swagger", "TanStack Table", "VPN" 등 기술 단정 문구 → 일반 표현으로
- React 버전 표기 불일치(18 / 19) → 표기하지 않음
- 헤더의 사용자 이름·이메일 예시 → 실제 사용자 정보 없이 단순화
- 화면별로 Tailwind 설정의 색 이름이 제각각이다 → 구현 시 위 토큰 표 하나로 통일
