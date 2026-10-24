"""App settings from the environment, read once in create_app. Model settings live in app.llm.settings."""

import os
from dataclasses import dataclass
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parents[3]
DEFAULT_CORS = "http://localhost:5173,http://127.0.0.1:5173"


def _int(name: str, default: int) -> int:
    value = os.environ.get(name, "").strip()
    return int(value) if value else default


@dataclass(frozen=True)
class Config:
    cors_origins: tuple[str, ...]
    cookie_secure: bool  # also on whenever the request itself came over HTTPS
    samples_dir: Path
    max_upload: int  # bytes
    scan_workers: int  # scans running at once in this process; more wait their turn
    chunk_workers: int  # T1 calls running at once within one scan

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            cors_origins=tuple(o for o in os.environ.get("VEIL_CORS", DEFAULT_CORS).split(",") if o),
            cookie_secure=os.environ.get("VEIL_COOKIE_SECURE", "false").lower() == "true",
            samples_dir=Path(os.environ.get("VEIL_SAMPLES_DIR", REPO_DIR / "data" / "synthetic" / "pdfs")),
            max_upload=20 * 1024 * 1024,
            scan_workers=_int("VEIL_SCAN_WORKERS", 8),
            chunk_workers=_int("VEIL_CHUNK_WORKERS", 6),
        )
