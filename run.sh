#!/usr/bin/env bash
# Legacy2Next 실행 스크립트: 환경 확인 → API 서버 기동 (127.0.0.1:8000)
# 시연 전 체크리스트를 겸합니다. 하나라도 실패하면 이유를 보여주고 멈춥니다.
set -euo pipefail
cd "$(dirname "$0")"

PY=".venv/Scripts/python.exe"; [ -x "$PY" ] || PY=".venv/bin/python"
fail() { echo "❌ $1"; exit 1; }

[ -x "$PY" ] || fail "가상환경(.venv)이 없습니다. README 실행 방법 1) 참고"
echo "Python: $($PY --version)"
command -v node >/dev/null || fail "Node.js 가 필요합니다 (20 이상)"
echo "Node:   $(node --version)"
[ -f .env ] || fail ".env 가 없습니다 (.env.example 참고)"
[ -d templates/tobe-app/node_modules ] || fail "템플릿 의존성이 없습니다: cd templates/tobe-app && npm install"
[ -d data/snapshots ] || echo "⚠ 스냅샷이 없습니다. 분석 요청 시 실제 크롤링이 필요합니다."
grep -q "snapshot_mode: replay" config/settings.yaml && echo "모드: 스냅샷 재생 (시연·평가 기본)" || echo "모드: 실제 크롤링"

echo "UI: http://127.0.0.1:8000/   API: POST http://127.0.0.1:8000/query"
exec "$PY" app.py
