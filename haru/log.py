"""실행 로그: 화면 + logs/YYYY-MM-DD.log 파일에 동시에 남긴다."""
import logging
import sys

from .config import LOG_DIR, now_kst


def setup_logging() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOG_DIR / f"{now_kst():%Y-%m-%d}.log"

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S")
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    root.addHandler(console)

    file = logging.FileHandler(log_file, encoding="utf-8")
    file.setFormatter(fmt)
    root.addHandler(file)

    # 라이브러리들의 잡다한 로그는 숨긴다
    for noisy in ("urllib3", "yfinance", "httpx", "openai"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    return logging.getLogger("haru")
