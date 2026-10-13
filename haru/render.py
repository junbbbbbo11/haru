"""HTML 렌더링: data/*.json → site/ 폴더.

매번 data/ 에 쌓인 모든 호를 다시 그린다. 그래서 디자인(템플릿)을 고치면
지난 호들도 다음 발행 때 새 디자인으로 바뀐다.

site/
├── index.html              최신호 (고정 URL)
├── archive/index.html      지난 호 목록
├── archive/YYYY-MM-DD.html 날짜별 호
└── data/YYYY-MM-DD.json    원본 데이터 (카드뉴스 등에 재사용)
"""
import json
import logging
import shutil
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .config import DATA_DIR, ROOT, WEEKDAYS

log = logging.getLogger("haru.render")
SITE_DIR = ROOT / "site"

# 섹션별 포인트 컬러(라이트/다크), 영문 라벨, 지면 레이아웃
SECTION_STYLE = {
    "domestic":  {"en": "Nation",    "light": "#1f3a5f", "dark": "#93b4dc", "layout": "classic"},
    "world":     {"en": "World",     "light": "#2d5b4e", "dark": "#86c2ae", "layout": "split"},
    "economy":   {"en": "Money",     "light": "#8a6a12", "dark": "#e0c26e", "layout": "tint"},
    "tech":      {"en": "Tech",      "light": "#3b39c9", "dark": "#a9a7ff", "layout": "pull"},
    "fashion":   {"en": "Fashion",   "light": "#a8123a", "dark": "#ff8aa5", "layout": "block"},
    "beauty":    {"en": "Beauty",    "light": "#b8506f", "dark": "#f2a7bf", "layout": "tint"},
    "lifestyle": {"en": "Living",    "light": "#5f7330", "dark": "#bcd27e", "layout": "classic"},
    "culture":   {"en": "Culture",   "light": "#71399a", "dark": "#cfa6ec", "layout": "split"},
    "sports":    {"en": "Sports",    "light": "#c94c14", "dark": "#ff9a6a", "layout": "pull"},
}
DEFAULT_STYLE = {"en": "News", "light": "#333333", "dark": "#cccccc", "layout": "classic"}

ZODIAC_HANJA = {"쥐": "子", "소": "丑", "호랑이": "寅", "토끼": "卯", "용": "辰", "뱀": "巳",
                "말": "午", "양": "未", "원숭이": "申", "닭": "酉", "개": "戌", "돼지": "亥"}


def _korean_date(d: str) -> str:
    x = date.fromisoformat(d)
    return f"{x.year}년 {x.month}월 {x.day}일"


def _env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(ROOT / "templates"),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["kdate"] = _korean_date
    env.filters["weekday"] = lambda d: WEEKDAYS[date.fromisoformat(d).weekday()]
    env.globals.update(SECTION_STYLE=SECTION_STYLE, DEFAULT_STYLE=DEFAULT_STYLE, ZODIAC_HANJA=ZODIAC_HANJA)
    return env


def load_editions() -> list[dict]:
    editions = []
    for p in sorted(DATA_DIR.glob("????-??-??.json")):
        try:
            with open(p, encoding="utf-8") as f:
                editions.append(json.load(f))
        except Exception:
            log.exception("%s 읽기 실패 → 건너뜀", p.name)
    return editions


def _sparklines(window: list[dict]) -> dict:
    """{지표 id: {'points': 'x,y x,y …', 'n': 개수}} — 값이 3개 이상 모인 지표만."""
    series: dict[str, list[float]] = {}
    for e in window:
        for t in e.get("indicators", []):
            if t.get("ok"):
                series.setdefault(t["id"], []).append(float(t["value"]))
    out = {}
    for key, vals in series.items():
        if len(vals) < 3:
            continue
        lo, hi = min(vals), max(vals)
        span = (hi - lo) or 1.0
        step = 60 / (len(vals) - 1)
        pts = " ".join(f"{i * step:.1f},{16 - (v - lo) / span * 14:.1f}" for i, v in enumerate(vals))
        out[key] = {"points": pts, "n": len(vals)}
    return out


def build_site(site_url: str = "", cards: bool = False) -> Path:
    editions = load_editions()
    if not editions:
        raise RuntimeError("data/ 폴더에 발행할 호가 없습니다")

    if SITE_DIR.exists():
        shutil.rmtree(SITE_DIR)
    (SITE_DIR / "archive").mkdir(parents=True)
    (SITE_DIR / "data").mkdir()
    (SITE_DIR / ".nojekyll").write_text("")
    # 아이콘·매니페스트 등 고정 파일 (홈 화면 앱)
    static = ROOT / "templates" / "static"
    if static.exists():
        for f in static.iterdir():
            shutil.copy(f, SITE_DIR / f.name)

    env = _env()
    page = env.get_template("edition.html")
    dates = [e["date"] for e in editions]

    # 착샷 이미지 복사. 파일이 지워진(오래된) 호는 일러스트로 보이게 photo 정보를 뺀다
    looks = DATA_DIR / "looks"
    if looks.exists():
        shutil.copytree(looks, SITE_DIR / "looks")
    for e in editions:
        for look in (e.get("ootd") or {}).get("looks", []):
            if look.get("photo") and not (DATA_DIR / look["photo"]).exists():
                look.pop("photo")

    # 지표 7일 추이(미니 그래프): 그 호까지의 최근 7개 호 값으로 그린다
    for i, e in enumerate(editions):
        e["_spark"] = _sparklines(editions[max(0, i - 6): i + 1])

    for i, e in enumerate(editions):
        ctx = {
            "e": e,
            "prev_date": dates[i - 1] if i > 0 else None,
            "next_date": dates[i + 1] if i + 1 < len(dates) else None,
            "site_url": site_url,
        }
        (SITE_DIR / "archive" / f"{e['date']}.html").write_text(
            page.render(base="../", is_latest=False, **ctx), encoding="utf-8")
        shutil.copy(DATA_DIR / f"{e['date']}.json", SITE_DIR / "data" / f"{e['date']}.json")

    latest = editions[-1]
    (SITE_DIR / "index.html").write_text(
        page.render(e=latest, base="", is_latest=True, site_url=site_url, show_cards=cards,
                    prev_date=dates[-2] if len(dates) > 1 else None, next_date=None),
        encoding="utf-8")
    shutil.copy(DATA_DIR / f"{latest['date']}.json", SITE_DIR / "data" / "latest.json")

    (SITE_DIR / "archive" / "index.html").write_text(
        env.get_template("archive.html").render(editions=list(reversed(editions)), base="../",
                                                title=latest.get("title", "하루 한 장")),
        encoding="utf-8")

    log.info("웹페이지 생성: 최신호 %s + 지난 호 %d개 → %s", latest["date"], len(editions), SITE_DIR)
    return SITE_DIR
