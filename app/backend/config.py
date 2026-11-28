from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent
REPO_ROOT = BACKEND_DIR.parent.parent
DATA_DIR = REPO_ROOT / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
CACHE_DIR = DATA_DIR / "cache"
# Saved AI replies for the synthetic demo papers. Committed to the repo, read-only.
DEMO_CACHE_DIR = DATA_DIR / "demo_cache"
RESOURCES_DIR = BACKEND_DIR / "resources"
DB_PATH = BACKEND_DIR / "medikiosk.db"

load_dotenv(BACKEND_DIR / ".env")


class Settings:
    nvidia_api_key: str = os.getenv("NVIDIA_API_KEY", "").strip()
    nvidia_base_url: str = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1").rstrip("/")
    nvidia_parse_model: str = os.getenv("NVIDIA_PARSE_MODEL", "nvidia/nemotron-3.5-super-vl-120b-a12b")
    nvidia_text_model: str = os.getenv("NVIDIA_TEXT_MODEL", "nvidia/nemotron-3.5-lightning-30b-a3b")
    nvidia_vision_model: str = os.getenv("NVIDIA_VISION_MODEL", "nvidia/nemotron-3.5-super-vl-120b-a12b")
    # Second reader: re-reads each value line from a zoomed crop and flags disagreements. Empty turns it off.
    nvidia_verify_model: str = os.getenv("NVIDIA_VERIFY_MODEL", "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning").strip()
    nvidia_asr_function_id: str = os.getenv("NVIDIA_ASR_FUNCTION_ID", "").strip()
    nvidia_asr_lang: str = os.getenv("NVIDIA_ASR_LANG", "hi-IN").strip()
    demo_today_str: str = os.getenv("DEMO_TODAY", "").strip()
    # Public demo site: no live NVIDIA calls and no uploads, so strangers cannot spend the key.
    public_demo: bool = os.getenv("PUBLIC_DEMO", "").strip().lower() in {"1", "true", "yes"}
    # "cached" or "scripted": load the demo patient at startup when the database has no patients.
    auto_seed_demo: str = os.getenv("AUTO_SEED_DEMO", "").strip().lower()
    # Extra browser origins allowed to call the API (the Vercel address), comma separated.
    cors_origins: str = os.getenv("CORS_ORIGINS", "").strip()

    @property
    def cors_origin_list(self) -> list[str]:
        extra = [o.strip().rstrip("/") for o in self.cors_origins.split(",") if o.strip()]
        return ["http://localhost:5173", "http://127.0.0.1:5173", *extra]

    @property
    def nvidia_key_present(self) -> bool:
        return bool(self.nvidia_api_key and not self.nvidia_api_key.endswith("your-key-here"))

    @property
    def today(self) -> date:
        if self.demo_today_str:
            try:
                return date.fromisoformat(self.demo_today_str)
            except ValueError:
                raise ValueError(f"DEMO_TODAY must look like 2026-10-14, got {self.demo_today_str!r}") from None
        return date.today()


settings = Settings()
