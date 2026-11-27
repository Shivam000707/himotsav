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
RESOURCES_DIR = BACKEND_DIR / "resources"
DB_PATH = BACKEND_DIR / "medikiosk.db"

load_dotenv(BACKEND_DIR / ".env")


class Settings:
    nvidia_api_key: str = os.getenv("NVIDIA_API_KEY", "").strip()
    nvidia_base_url: str = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1").rstrip("/")
    nvidia_parse_model: str = os.getenv("NVIDIA_PARSE_MODEL", "nvidia/nemotron-parse")
    nvidia_text_model: str = os.getenv("NVIDIA_TEXT_MODEL", "meta/llama-3.3-70b-instruct")
    nvidia_vision_model: str = os.getenv("NVIDIA_VISION_MODEL", "meta/llama-3.2-90b-vision-instruct")
    nvidia_asr_function_id: str = os.getenv("NVIDIA_ASR_FUNCTION_ID", "").strip()
    nvidia_asr_lang: str = os.getenv("NVIDIA_ASR_LANG", "hi-IN").strip()
    demo_today_str: str = os.getenv("DEMO_TODAY", "").strip()

    @property
    def nvidia_key_present(self) -> bool:
        return bool(self.nvidia_api_key and not self.nvidia_api_key.endswith("your-key-here"))

    @property
    def today(self) -> date:
        if self.demo_today_str:
            return date.fromisoformat(self.demo_today_str)
        return date.today()


settings = Settings()
