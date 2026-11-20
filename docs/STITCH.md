# STITCH.md — Stitch 디자인 작업 규칙

Stitch 사용법은 공식 스킬(`google-labs-code/stitch-skills`, `.claude/skills/stitch-*`)을 따른다. 이 문서는 **이 프로젝트에만 해당하는 규칙**만 담는다. 공식 스킬과 이 문서가 충돌하면 이 문서와 CLAUDE.md를 따른다.

## 대상과 저장 위치

| 대상 | Stitch 프로젝트 이름 | 저장 위치 |
|---|---|---|
| 콘솔 UI | `Legacy2Next-console` | `ui/design/` |
| 생성 결과물 | `Legacy2Next-<별칭>` | `next-pjt/<별칭>/design/` |

`design/` 폴더 구성:
- `DESIGN.md` — 디자인 시스템 규칙 (색·타이포·간격·컴포넌트 톤). 이후 화면 생성 프롬프트의 기준
- `reference/` — Stitch에 올린 레퍼런스 기반 DESIGN.md 원본
- `archive/` — 교체된 이전 디자인 (버전별 폴더)
- `screens/<화면명>.html`, `screens/<화면명>.png` — 화면별 Stitch HTML과 스크린샷

## 작업 순서와 사용할 스킬

1. **디자인 시스템 생성** — 텍스트로 톤만 설명하지 말고 **레퍼런스 DESIGN.md에서 시작**한다. [awesome-design-md](https://github.com/VoltAgent/awesome-design-md)에서 성격이 맞는 제품을 하나 골라 받고, 브랜드 고유 요소(그라데이션·로고 등)는 빼고 한글 폰트·상태 색·금지 패턴을 더해 고친 뒤 `upload_design_md` → `create_design_system_from_design_md`로 등록한다. 고친 원본은 `design/reference/`에 둔다. 생성 결과물이면 Analyst의 사이트 성격 추론 결과로 레퍼런스를 고른다
   - 화면 생성 프롬프트에는 화면 구조·실제 문구와 함께 **금지 목록**(장식용 영문 모노 라벨, 가짜 배지, 박스 중첩, 같은 카드 나열 등)을 넣는다
2. **DESIGN.md 정리** — `stitch-design-md`로 `design/DESIGN.md` 작성
3. **화면 생성** — `stitch-enhance-prompt`로 프롬프트를 다듬고 `stitch-generate-design`으로 생성. 프롬프트에는 DESIGN.md 내용을 넣는다
4. **사용자 확인** — 화면 HTML·스크린샷을 `design/screens/`에 저장하고 확인받는다. **승인 전에는 코드를 만들지 않는다**
5. **React 변환** — `stitch-react-components`로 공통 컴포넌트 → 화면 순으로 변환

화면을 추가할 때(점진 확장)는 1~2를 건너뛰고 기존 `DESIGN.md`로 3부터 진행한다.

## Tailwind 맞추기

- `DESIGN.md`의 색·폰트·간격 토큰을 Tailwind 테마(`tailwind.config` 또는 CSS `@theme`)에 옮기고, 컴포넌트는 그 토큰 클래스만 쓴다
- `className`에 hex 색상을 직접 쓰지 않는다 (`stitch-react-components`의 검증 스크립트가 잡는다)
- 컴포넌트 구조·네이밍은 CLAUDE.md 코딩 컨벤션을 따른다

## 참고

- 공식 스킬은 원본에서 `name`만 이 프로젝트 형식(`stitch-<스킬명>`)으로 바꿨다. 업데이트할 때 같은 방식으로 다시 받는다
- `stitch-manage-design-system`이 언급하는 `upload-to-stitch` 스크립트는 설치하지 않았다. Stitch MCP 도구로 처리한다
- Stitch 프롬프트 가이드: https://stitch.withgoogle.com/docs/learn/prompting/
- Stitch HTML 주의: Tailwind `fontFamily`가 `"\"Geist, 'Noto Sans KR', …\""`처럼 문자열 하나로 나와 폰트가 적용되지 않을 때가 있다. 저장 전에 배열로 고치고, 아이콘이 글자(`chat_bubble_outline`)로 보이는지 렌더링해서 확인한다
- 생성이 타임아웃 나면 `list_screens`가 새 화면을 바로 보여주지 않을 수 있다. 제목이 같은 v1 화면과 헷갈리지 않게 HTML의 폰트·색으로 버전을 확인한다
