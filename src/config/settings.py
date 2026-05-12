from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    load_dotenv = None


@dataclass(frozen=True)
class Settings:
    discord_webhook_url: str
    discord_webhook_hardware: str
    discord_webhook_setup: str
    discord_webhook_absurdas: str
    database_url: str
    min_discount_percent: float
    min_score: int
    request_timeout_seconds: int
    max_results_per_store: int
    enable_playwright_fallback: bool
    max_retries: int
    verbose_logs: bool

    @property
    def database_path(self) -> Path:
        url = self.database_url.strip()
        if url.startswith("sqlite:///"):
            return Path(url.replace("sqlite:///", "", 1))
        return Path(url or "data/radar_setup.sqlite3")

    @classmethod
    def from_env(cls) -> "Settings":
        load_environment()
        return cls(
            discord_webhook_url=os.getenv("DISCORD_WEBHOOK_URL", "").strip(),
            discord_webhook_hardware=os.getenv("DISCORD_WEBHOOK_HARDWARE", "").strip(),
            discord_webhook_setup=os.getenv("DISCORD_WEBHOOK_SETUP", "").strip(),
            discord_webhook_absurdas=os.getenv("DISCORD_WEBHOOK_ABSURDAS", "").strip(),
            database_url=os.getenv("DATABASE_URL", "sqlite:///data/radar_setup.sqlite3"),
            min_discount_percent=float(os.getenv("MIN_DISCOUNT_PERCENT", "25")),
            min_score=int(os.getenv("MIN_SCORE", "70")),
            request_timeout_seconds=int(os.getenv("REQUEST_TIMEOUT_SECONDS", "20")),
            max_results_per_store=int(os.getenv("MAX_RESULTS_PER_STORE", "5")),
            enable_playwright_fallback=env_bool(
                "USE_PLAYWRIGHT_FALLBACK",
                fallback_key="ENABLE_PLAYWRIGHT_FALLBACK",
                default=False,
            ),
            max_retries=int(os.getenv("MAX_RETRIES", "2")),
            verbose_logs=env_bool("VERBOSE_LOGS", default=True),
        )


def load_environment() -> None:
    if load_dotenv is not None:
        load_dotenv()
        return

    env_path = Path(".env")
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def env_bool(key: str, *, fallback_key: str | None = None, default: bool = False) -> bool:
    raw = os.getenv(key)
    if raw is None and fallback_key:
        raw = os.getenv(fallback_key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "sim", "on"}
