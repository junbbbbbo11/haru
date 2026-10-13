"""설정 파일 읽기, 경로, 한국 시간 도우미."""
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
LOG_DIR = ROOT / "logs"

KST = timezone(timedelta(hours=9), "KST")
WEEKDAYS = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]


def load_yaml(name: str) -> dict:
    with open(ROOT / name, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_config() -> dict:
    return load_yaml("config.yaml")


def load_sources() -> dict:
    return load_yaml("sources.yaml")


def now_kst() -> datetime:
    return datetime.now(KST)
