"""FastAPI 앱. T03은 상태 확인만, /query와 SSE는 T04에서 붙인다."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import __version__
from .config import AgentConfig, load_config


class HealthResponse(BaseModel):
    status: str
    version: str
    llm_calls_per_run: int


def create_app(config: AgentConfig | None = None) -> FastAPI:
    cfg = config or load_config()
    app = FastAPI(title="Legacy2Next Agent", version=__version__)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    app.state.config = cfg

    @app.get("/health")
    def health() -> HealthResponse:
        return HealthResponse(
            status="ok", version=__version__, llm_calls_per_run=cfg.limits.llm_calls_per_run
        )

    return app
