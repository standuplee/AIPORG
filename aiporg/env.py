"""경량 .env 로더 (외부 의존성 없음).

프로젝트 루트의 .env 파일을 읽어 os.environ 에 주입한다.
이미 설정된 환경변수는 덮어쓰지 않으므로(=inline 지정이 우선),
`NAVER_CLIENT_ID=... python -m aiporg.cli ...` 형태의 일회성 지정도 그대로 동작한다.
"""
from __future__ import annotations

import os


def project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_dotenv(path: str | None = None) -> list[str]:
    """.env 를 로드하고, 값이 채워진(빈 값 아님) 키 목록을 반환."""
    if path is None:
        path = os.path.join(project_root(), ".env")
    if not os.path.exists(path):
        return []

    loaded: list[str] = []
    with open(path, "r", encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            if key.startswith("export "):
                key = key[len("export "):].strip()
            val = val.strip().strip('"').strip("'")
            if not key:
                continue
            # inline 환경변수가 우선하도록 setdefault 사용
            os.environ.setdefault(key, val)
            if os.environ.get(key):
                loaded.append(key)
    return loaded
