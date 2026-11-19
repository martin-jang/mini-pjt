# T01 · 프로젝트 골격과 `/query` 스텁

- **예상**: 30분 · **일정**: Day 9 오전 · **의존**: 없음
- **관련**: `SERVICE.md` §3 API 계약, `ASSIGNMENT.md` §4-1·4-2

## 목표
과제 폴더 구조를 만들고, `POST /query`가 규약대로 응답하는 스텁을 띄웁니다. 이후 모든 기능은 이 진입점에 붙습니다.

## 작업
- [ ] 폴더 생성: `src/`, `src/analyst/`, `src/codegen/`, `mcp_server/`, `config/`, `data/snapshots/`, `data/fixtures/`, `evaluation/golden/`, `tests/`, `output/`
- [ ] `requirements.txt`: `sds-ax-training/requirements.txt` + `ragas`, `playwright`, `fastapi`, `uvicorn`, `pyyaml`
- [ ] `.env.example`: AWS 키, 데모 계정 값을 **빈 값**으로
- [ ] `config/settings.yaml`: `allowed_domains`, `start_url`, `demo_account_env`(환경변수 이름), `snapshot_mode` — 사이트 고유 값은 여기만
- [ ] `src/config.py`: 설정 로더
- [ ] `app.py`: FastAPI `POST /query`
  - Body: `question`(필수), `thread_id`·`approval`(선택)
  - Response: `answer`, `contexts`, `trace`, `status`, `pending`
  - `127.0.0.1`에만 바인딩
  - 지금은 고정 응답(`status="ok"`) 반환

## 산출물
`app.py`, `src/config.py`, `config/settings.yaml`, `requirements.txt`, `.env.example`

## 완료 기준
- `uvicorn app:app --host 127.0.0.1` 기동 후 `curl -X POST 127.0.0.1:8000/query -d '{"question":"hi"}'`가 5개 필드를 담은 JSON 반환
- `question` 누락 시 422

## 주의
- 모델은 함수 안에서 만듭니다 (`llm = llm or _default_llm()`).
