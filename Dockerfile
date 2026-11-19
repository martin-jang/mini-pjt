# Legacy2Next 클린 환경 재현용 이미지 (선택 산출물, ASSIGNMENT.md §4-1)
#
# 빌드:  docker build -t legacy2next .
# 실행:  docker run --rm --env-file .env -p 127.0.0.1:8000:8000 legacy2next
#        → 브라우저 http://127.0.0.1:8000/ (콘솔 UI), API POST http://127.0.0.1:8000/query
#
# - .env(AWS 키, 데모 계정)는 이미지에 넣지 않고 실행 시 --env-file 로만 전달합니다.
# - 컨테이너 안에서는 0.0.0.0 에 바인딩하지만, 호스트 쪽은 127.0.0.1 로만 열어 G5(로컬 전용)를 지킵니다.
# - 벡터 인덱스(chroma_db)는 커밋하지 않으므로, 컨테이너에서 처음에 "URL 분석해줘"를 한 번 요청해 적재합니다
#   (settings.yaml 의 snapshot_mode: replay 이면 data/snapshots 의 저장 화면으로 분석, 실제 사이트 접속 없음).
# - 로컬 eGov 샘플(localhost:8080)은 호스트에서 도는 서버라 컨테이너 안에서는 접근하지 않습니다.

FROM python:3.14-slim

# 생성 앱 빌드·Storybook·Playwright 흐름 검증에 Node.js 22 가 필요합니다
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates gnupg \
 && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
 && apt-get install -y --no-install-recommends nodejs \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 1) Python 의존성 + 크롤러용 Chromium
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
 && python -m playwright install --with-deps chromium

# 2) 생성 앱 고정 템플릿 의존성 (버전 고정 lock 파일 기준) + 흐름 검증용 Chromium
COPY templates/tobe-app/package.json templates/tobe-app/package-lock.json templates/tobe-app/
RUN cd templates/tobe-app && npm ci && npx playwright install --with-deps chromium

# 3) 소스·데이터·평가셋
COPY . .

ENV PYTHONIOENCODING=utf-8 \
    PYTHONUNBUFFERED=1 \
    LEGACY2NEXT_HOST=0.0.0.0

EXPOSE 8000
CMD ["python", "app.py"]
