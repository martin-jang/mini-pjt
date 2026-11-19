"""생성 프로젝트 준비 (도구 scaffold_project, 결정 D8 고정 템플릿).

templates/tobe-app 을 output/{프로젝트}/ 로 복사합니다. node_modules 는 복사하지 않고 디렉터리 링크로 연결해
매번 npm install 을 하지 않습니다 (Windows는 관리자 권한이 필요 없는 디렉터리 정션 사용).
템플릿의 샘플 화면은 지우고, 라우트는 비어 있는 상태로 둡니다 (Page Builder가 채움).
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from src.config import path as cfg_path

_SKIP = {"node_modules", "dist", "storybook-static", "test-results", "playwright-report", "e2e-results.json"}

EMPTY_ROUTES = """// Page Builder가 생성하는 라우트 목록입니다.
import type { ReactElement } from 'react'

export interface AppRoute {
  path: string
  title: string
  element: ReactElement
  menu?: boolean
}

export const routes: AppRoute[] = []
"""


def _link_node_modules(src: Path, dst: Path) -> None:
    if dst.exists():
        return
    if os.name == "nt":
        subprocess.run(["cmd", "/c", "mklink", "/J", str(dst), str(src)], check=True, capture_output=True)
    else:
        dst.symlink_to(src, target_is_directory=True)


def project_dir(name: str) -> Path:
    return cfg_path("output") / name


def scaffold_project(name: str, overwrite_approved: bool = False) -> dict:
    """템플릿을 복사해 생성 프로젝트를 만듭니다.

    언제 쓰나: 생성 파이프라인 시작 시 1회.
    언제 쓰지 않나: 같은 이름의 결과물이 있는데 덮어쓰기 승인(H4)이 없을 때 → 복사하지 않고 안내 반환.
    """
    template = cfg_path("template")
    dst = project_dir(name)
    if dst.exists():
        if not overwrite_approved:
            return {"error": f"기존 결과물이 있습니다 ({dst.name}). 덮어쓰기 승인이 필요합니다.", "path": str(dst)}
        link = dst / "node_modules"
        if link.exists() and os.name == "nt":
            os.rmdir(link)  # 정션은 링크만 지움 (템플릿 node_modules 보존)
        elif link.is_symlink():
            link.unlink()
        shutil.rmtree(dst)
    shutil.copytree(template, dst, ignore=lambda d, names: [n for n in names if n in _SKIP])
    _link_node_modules(template / "node_modules", dst / "node_modules")
    sample = dst / "src" / "pages" / "SamplePage.tsx"
    if sample.exists():
        sample.unlink()
    (dst / "src" / "routes.tsx").write_text(EMPTY_ROUTES, encoding="utf-8")
    (dst / "e2e" / "smoke.spec.ts").unlink(missing_ok=True)
    return {"path": str(dst), "name": name}
