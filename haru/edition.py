"""오늘 호(edition) JSON 만들기.

data/YYYY-MM-DD.json 이 웹페이지·카드뉴스 등 모든 결과물의 '원본 데이터'다.
AI 편집이 없거나 실패하면 build_fallback()이 원문 헤드라인으로 채운다.
"""
import json
import logging
import re

from .collect import _bigrams, _is_korean, _similar
from .config import DATA_DIR, RAW_DIR, WEEKDAYS

log = logging.getLogger("haru.edition")


def volume_number(today) -> int:
    """호수 = 오늘 이전에 발행된 호의 수 + 1 (같은 날 다시 만들면 같은 호수)."""
    earlier = [p for p in DATA_DIR.glob("????-??-??.json") if p.stem < today.isoformat()]
    return len(earlier) + 1

SCHEMA_VERSION = 1


def sources_of(c: dict, related: list | None = None, limit: int = 6) -> list[dict]:
    """대표 기사 + 같은 사건을 다룬 다른 매체 기사 → [{name, title, link}] (매체 중복 없이)."""
    # related(같은 검색어의 다른 기사)는 제목이 실제로 비슷한 한글 기사만 — 다른 사건이 섞이지 않게
    base = _bigrams(c.get("title", ""))
    related = [r for r in (related or []) if _is_korean(r.get("title", "")) and base
               and len(base & _bigrams(r.get("title", ""))) / len(base) >= 0.3]
    out, seen = [], set()
    for x in [c] + list(c.get("also", [])) + related:
        name = x.get("source") or ""
        if name.startswith("http"):  # 매체명 대신 주소가 온 경우 → 도메인만
            name = re.sub(r"^https?://(www\.)?|/.*$", "", name)
        if not x.get("link") or name in seen:
            continue
        seen.add(name)
        out.append({"name": name, "title": x.get("title", ""), "link": x["link"]})
        if len(out) >= limit:
            break
    return out


def _item(c: dict) -> dict:
    return {"headline": c["title"], "summary": "", "source": c["source"], "link": c["link"],
            "original_title": c["title"], "coverage": c.get("coverage", 1), "sources": sources_of(c)}


def fit_reading_time(edited: dict, max_items: int) -> dict:
    """'3분 안에 읽기'를 위해 전체 기사 수를 제한한다.
    섹션마다 1개는 꼭 싣고, 두 번째 기사는 많이 보도된 것부터 남는 자리만큼."""
    sections = edited.get("sections", [])
    budget = max_items - len(sections)
    extras = sorted(
        ((s["id"], i, it.get("coverage", 1)) for s in sections for i, it in enumerate(s["items"]) if i > 0),
        key=lambda x: -x[2],
    )
    keep = {(sid, i) for sid, i, _ in extras[: max(0, budget)]}
    for s in sections:
        s["items"] = [it for i, it in enumerate(s["items"]) if i == 0 or (s["id"], i) in keep]
    return edited


def build_fallback(raw: dict, items_per_section: int = 2) -> dict:
    """AI 없이: 가장 많이 보도된 기사의 원문 제목을 그대로 싣는다."""
    used: list[set] = []

    def fresh(title: str) -> bool:
        g = _bigrams(title)
        if any(_similar(g, u) for u in used):
            return False
        used.append(g)
        return True

    covers = []
    # 한글 검색어(국내 이슈)를 먼저, 영어·외국어 검색어는 뒤로
    trends = sorted(raw.get("trends", []), key=lambda t: not _is_korean(t["keyword"]))
    for t in trends:
        if len(covers) >= 3:
            break
        # 한국 매체 2곳 이상이 한글로 보도한 검색어만 (해외 기계번역·광고성 기사 거르기)
        korean = [n for n in t["news"] if _is_korean(n["title"])]
        if len({n["source"] for n in korean}) < 2:
            continue
        n = korean[0]
        if fresh(n["title"]):
            covers.append({
                "keyword": t["keyword"],
                "headline": n["title"],
                "summary": "",
                "source": n["source"],
                "link": n["link"],
                "sources": sources_of(n, korean[1:]),
            })

    # 트렌드로 3개가 안 차면, 여러 매체가 많이 보도한 섹션 기사로 채운다
    tops = sorted((c for s in raw.get("sections", []) for c in s["candidates"]),
                  key=lambda c: -c.get("coverage", 1))
    for c in tops:
        if len(covers) >= 3:
            break
        if fresh(c["title"]):
            covers.append({"keyword": "", "headline": c["title"], "summary": "", "source": c["source"],
                           "link": c["link"], "sources": sources_of(c)})

    sections = []
    for sec in raw.get("sections", []):
        picked = [_item(c) for c in sec["candidates"] if fresh(c["title"])][:items_per_section]
        if picked:  # 비어 있는 섹션은 조용히 생략
            sections.append({"id": sec["id"], "name": sec["name"], "items": picked})

    return {"cover_stories": covers, "sections": sections}


def reading_minutes(edition: dict) -> int:
    """예상 읽기 시간. 성인 한국어 묵독 속도(분당 약 700자) 기준."""
    chars = 200  # 지표·제목 등
    for c in edition.get("cover_stories", []):
        chars += len(c["headline"]) + len(c.get("summary", ""))
    for s in edition.get("sections", []):
        for it in s["items"]:
            chars += len(it["headline"]) + len(it.get("summary", ""))
    sr = edition.get("series") or {}
    if sr:
        chars += len(sr.get("title", "")) + len(sr.get("description", "")) + sum(len(t) for t in sr.get("tips", []))
        chars += sum(len(i["name"]) for i in sr.get("items", []))
    if edition.get("quote"):
        chars += len(edition["quote"]["text"]) + 10
    for z in (edition.get("fortune") or {}).get("items", []):
        chars += len(z["text"]) + 3
    return max(1, round(chars / 700))


def assemble(today, generated_at, site_cfg: dict, raw: dict, edited: dict, mode: str) -> dict:
    edition = {
        "schema_version": SCHEMA_VERSION,
        "title": site_cfg.get("title", "하루 한 장"),
        "date": today.isoformat(),
        "weekday": WEEKDAYS[today.weekday()],
        "vol": volume_number(today),
        "generated_at": generated_at.isoformat(timespec="seconds"),
        "edit_mode": mode,  # "ai" 또는 "fallback"(원문 헤드라인)
        "indicators": raw.get("indicators", []),
        "weather": raw.get("weather"),
        "cover_stories": edited.get("cover_stories", []),
        "sections": edited.get("sections", []),
        "series": edited.get("series"),
        "quote": edited.get("quote"),
        "fortune": edited.get("fortune"),
    }
    edition["reading_minutes"] = reading_minutes(edition)
    return edition


def save_json(obj: dict, path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def raw_path(today):
    return RAW_DIR / f"{today.isoformat()}.json"


def edition_path(today):
    return DATA_DIR / f"{today.isoformat()}.json"
