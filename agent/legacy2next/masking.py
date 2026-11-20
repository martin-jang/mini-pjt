"""비밀값 마스킹 (G3). 등록된 계정·키 값을 로그와 LLM 입력에서 *** 로 바꾼다."""

from __future__ import annotations

import logging
import threading

MASK = "***"
# 너무 짧은 값은 일반 글자와 겹쳐 오탐이 나므로 가리지 않는다
MIN_SECRET_LENGTH = 3


class SecretRegistry:
    """마스킹할 비밀값 목록. 스레드 안전."""

    def __init__(self) -> None:
        self._values: set[str] = set()
        self._lock = threading.Lock()

    def register(self, *values: str | None) -> None:
        with self._lock:
            for value in values:
                if value and len(value) >= MIN_SECRET_LENGTH:
                    self._values.add(value)

    def clear(self) -> None:
        with self._lock:
            self._values.clear()

    def mask(self, text: str) -> str:
        """등록된 값을 모두 가린다. 긴 값부터 바꿔 부분 겹침을 피한다."""
        with self._lock:
            values = sorted(self._values, key=len, reverse=True)
        for value in values:
            if value in text:
                text = text.replace(value, MASK)
        return text


# 프로세스 전체에서 쓰는 기본 레지스트리
secrets = SecretRegistry()


class SecretMaskingFilter(logging.Filter):
    """로그 레코드의 최종 메시지에서 비밀값을 가린다."""

    def __init__(self, registry: SecretRegistry = secrets) -> None:
        super().__init__()
        self._registry = registry

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        masked = self._registry.mask(message)
        if masked != message:
            record.msg = masked
            record.args = None
        return True


def setup_logging(level: int = logging.INFO, registry: SecretRegistry = secrets) -> None:
    """루트 로거에 마스킹 필터를 단 콘솔 핸들러를 붙인다."""
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))
    handler.addFilter(SecretMaskingFilter(registry))
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
