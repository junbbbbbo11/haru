"""뉴스 수집: RSS 읽기 → 최근 24시간만 → 같은 사건 기사 묶기.

소스 하나가 실패해도 로그만 남기고 계속 진행한다.
"""
import calendar
import html
import logging
import re
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from urllib.parse import quote

import feedparser
import requests

from .config import KST

log = logging.getLogger("haru.collect")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}
GOOGLE_NEWS_PARAMS = "hl=ko&gl=KR&ceid=KR:ko"


def google_news_search_url(query: str) -> str:
    return f"https://news.google.com/rss/search?q={quote(query + ' when:1d')}&{GOOGLE_NEWS_PARAMS}"


# ── 제목 정리 ────────────────────────────────────────────────

def _clean(text: str) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", "", text or ""))
    return re.sub(r"\s+", " ", text).strip()


def _split_google_title(title: str, source_title: str) -> tuple[str, str]:
    """구글 뉴스 제목 '헤드라인 - 매체명'에서 매체명을 떼어낸다."""
    source = source_title
    if source_title and title.endswith(" - " + source_title):
        title = title[: -len(" - " + source_title)]
    # '헤드라인 - 조선비즈 - Chosunbiz' 처럼 한글 매체명이 한 번 더 붙는 경우
    if " - " in title:
        head, tail = title.rsplit(" - ", 1)
        if len(tail) <= 15:
            title, source = head, tail
    return title.strip(), source or "구글 뉴스"


def _strip_source(title: str, source: str) -> str:
    """제목 끝에 붙은 ' - 매체명' / ' | 매체명' 을 떼어낸다."""
    for sep in (" - ", " | ", " : "):
        if source and title.endswith(sep + source):
            return title[: -len(sep + source)].strip()
    return title


_NOISE = re.compile(r"\[[^\]]*\]|\([^)]*\)|【[^】]*】|<[^>]*>")


def _bigrams(title: str) -> set[str]:
    core = _NOISE.sub(" ", title)
    core = re.sub(r"[^0-9A-Za-z가-힣]", "", core).lower()
    return {core[i : i + 2] for i in range(len(core) - 1)}


def _similar(a: set, b: set, threshold: float = 0.45) -> bool:
    """짧은 쪽 제목 글자쌍의 45% 이상이 겹치면 같은 사건으로 본다.
    (실측: 같은 사건 0.47~0.71, 다른 사건 0.11 이하)"""
    if len(a) < 6 or len(b) < 6:
        return a == b
    return len(a & b) / min(len(a), len(b)) >= threshold


# ── 피드 읽기 ────────────────────────────────────────────────

def fetch_feed(name: str, url: str, hours: int, limit: int, timeout: int) -> list[dict]:
    """피드 하나를 읽어 최근 기사 목록을 돌려준다. 실패하면 빈 목록."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
        parsed = feedparser.parse(resp.content)
    except Exception as e:
        log.warning("  ✗ %s 실패: %s", name, e)
        return []

    is_google = "news.google.com" in url
    cutoff = time.time() - hours * 3600
    items = []
    for entry in parsed.entries[:limit]:
        t = entry.get("published_parsed") or entry.get("updated_parsed")
        if not t:
            continue  # 날짜를 모르면 '최근 24시간'인지 알 수 없으므로 버린다
        ts = calendar.timegm(t)
        if ts < cutoff:
            continue

        title = _clean(entry.get("title", ""))
        source = name
        related = 1
        if is_google:
            src = entry.get("source") or {}
            title, source = _split_google_title(title, src.get("title", ""))
            # 구글 뉴스는 같은 사건의 관련 기사를 <li>로 묶어 준다 → 화제성 지표
            related = max(1, entry.get("summary", "").count("<li>"))
        else:
            title = _strip_source(title, name)
        if not title or not entry.get("link"):
            continue

        # 기사 요약문: AI가 맥락을 이해하는 데만 쓰고, 페이지에는 싣지 않는다
        snippet = "" if is_google else _clean(entry.get("summary", ""))[:200]
        items.append({
            "title": title,
            "source": source,
            "snippet": snippet,
            "link": entry.link,
            "published": datetime.fromtimestamp(ts, KST).isoformat(timespec="minutes"),
            "feed": name,
            "_ts": ts,
            "_related": related,
            "_direct": not is_google,
        })
    log.info("  ✓ %s: %d건", name, len(items))
    return items


def cluster(items: list[dict]) -> list[dict]:
    """같은 사건을 다룬 기사들을 하나로 묶고, 많이 보도된 순으로 정렬."""
    items = sorted(items, key=lambda x: -x["_ts"])
    groups: list[dict] = []
    seen_links = set()
    for it in items:
        if it["link"] in seen_links:
            continue
        seen_links.add(it["link"])
        grams = _bigrams(it["title"])
        for g in groups:
            if any(_similar(grams, other) for other in g["_grams"]):
                g["_members"].append(it)
                g["_grams"].append(grams)
                break
        else:
            groups.append({"_grams": [grams], "_members": [it]})

    result = []
    for g in groups:
        members = g["_members"]
        # 대표 기사: 한글 제목 + 언론사 직접 링크를 우선, 그다음 최신
        rep = sorted(members, key=lambda m: (not _is_korean(m["title"]), not m["_direct"], -m["_ts"]))[0]
        outlets = list(dict.fromkeys(m["source"] for m in members))
        related = max(m["_related"] for m in members)
        coverage = max(len(outlets), related)
        # 화제성 점수: 여러 매체가 실제로 보도한 것을 가장 크게 친다
        score = len(outlets) + 0.5 * (min(related, 5) - 1)
        result.append({
            "title": rep["title"],
            "source": rep["source"],
            "link": rep["link"],
            "snippet": next((m["snippet"] for m in members if m["snippet"]), ""),
            "published": rep["published"],
            "coverage": coverage,          # 몇 군데서 보도했는지 (화제성)
            "outlets": outlets[:6],
            "also": [
                {"title": m["title"], "source": m["source"], "link": m["link"]}
                for m in members if m is not rep
            ][:4],
            "_ts": rep["_ts"],
            "_score": score,
            "_feeds": {m["feed"] for m in members},
        })
    result.sort(key=lambda x: (-x["_score"], -x["_ts"]))
    return result


def _is_korean(text: str) -> bool:
    return bool(re.search(r"[가-힣]", text))


def pick_diverse(clusters: list[dict], n_feeds: int, limit: int) -> list[dict]:
    """점수순으로 고르되, 피드 하나가 후보 자리를 독차지하지 않게 한다."""
    cap = max(3, -(-limit // max(1, n_feeds)) + 1)  # 피드당 대략 공평한 몫
    used: dict[str, int] = {}
    picked, rest = [], []
    for c in clusters:
        if len(c["_feeds"]) > 1 or all(used.get(f, 0) < cap for f in c["_feeds"]):
            picked.append(c)
            for f in c["_feeds"]:
                used[f] = used.get(f, 0) + 1
        else:
            rest.append(c)
        if len(picked) >= limit:
            break
    picked += rest[: limit - len(picked)]
    picked.sort(key=lambda x: (-x["_score"], -x["_ts"]))
    return [{k: v for k, v in c.items() if not k.startswith("_")} for c in picked]


def collect_sections(sources: dict, cfg: dict) -> list[dict]:
    hours = cfg.get("hours", 24)
    limit = cfg.get("max_items_per_feed", 40)
    timeout = cfg.get("timeout_seconds", 15)
    max_cand = cfg.get("max_candidates_per_section", 25)

    sections = []
    for sec in sources.get("sections", []):
        feeds = [(f["name"], f["url"]) for f in sec.get("feeds") or []]
        feeds += [(f"구글 뉴스 검색 '{q}'", google_news_search_url(q)) for q in sec.get("search") or []]
        log.info("[%s] 피드 %d개 수집", sec["name"], len(feeds))
        items = []
        try:
            with ThreadPoolExecutor(max_workers=8) as pool:
                results = pool.map(lambda f: fetch_feed(f[0], f[1], hours, limit, timeout), feeds)
                items = [it for r in results for it in r]
            candidates = pick_diverse(cluster(items), len(feeds), max_cand)
        except Exception:
            log.exception("[%s] 섹션 수집 중 오류 → 이 섹션은 생략", sec["name"])
            candidates = []
        log.info("[%s] 기사 %d건 → 묶은 뒤 후보 %d건", sec["name"], len(items), len(candidates))
        sections.append({"id": sec["id"], "name": sec["name"], "candidates": candidates})
    return sections


# ── 구글 트렌드 ──────────────────────────────────────────────

# 매일 검색량은 많지만 뉴스는 아닌 것들 — 커버스토리 후보에서 뺀다
_ROUTINE = re.compile(r"운세|로또|복권|정답|퀴즈|캐시워크|토스\s*행운|날씨|\[포토\]|xsmb|xsmn|kqxs", re.I)


def _is_routine(keyword: str, news: list[dict]) -> bool:
    if _ROUTINE.search(keyword):
        return True
    head = news[0]["title"] if news else ""
    return bool(_ROUTINE.search(head))


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def collect_trends(sources: dict, cfg: dict) -> list[dict]:
    """구글 트렌드 인기 검색어 + 검색어별 관련 기사."""
    tcfg = sources.get("trends") or {}
    url = tcfg.get("url")
    if not url:
        return []
    timeout = cfg.get("timeout_seconds", 15)
    hours = cfg.get("hours", 24)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
    except Exception as e:
        log.warning("구글 트렌드 실패: %s", e)
        return []

    trends = []
    for item in root.iter("item"):
        kw, traffic, news = "", "", []
        for child in item:
            tag = _local(child.tag)
            if tag == "title":
                kw = (child.text or "").strip()
            elif tag == "approx_traffic":
                traffic = (child.text or "").strip()
            elif tag == "news_item":
                fields = {_local(c.tag): _clean(c.text or "") for c in child}
                if fields.get("news_item_title") and fields.get("news_item_url"):
                    news.append({
                        "title": _strip_source(fields["news_item_title"], fields.get("news_item_source", "")),
                        "source": fields.get("news_item_source", ""),
                        "link": fields["news_item_url"],
                    })
        if kw and _is_routine(kw, news):
            log.info("  · 트렌드 '%s' 제외 (운세·로또·퀴즈 정답 같은 반복성 검색어)", kw)
        elif kw:
            trends.append({"keyword": kw, "traffic": traffic, "news": news})
        if len(trends) >= tcfg.get("max_keywords", 10):
            break

    # 검색어마다 구글 뉴스에서 관련 기사를 더 붙인다
    per_kw = tcfg.get("news_per_keyword", 6)

    def enrich(t):
        found = fetch_feed(f"트렌드 '{t['keyword']}'", google_news_search_url(t["keyword"]), hours, 30, timeout)
        news = t["news"] + [
            {"title": f["title"], "source": f["source"], "link": f["link"]} for f in cluster(found)
        ]
        kw = t["keyword"].replace(" ", "").lower()
        # 한글 기사 > 제목에 검색어가 들어간 기사 > 나머지 순으로
        news.sort(key=lambda n: (not _is_korean(n["title"]), kw not in n["title"].replace(" ", "").lower()))
        seen, t["news"] = set(), []
        for n in news:
            if n["link"] not in seen and len(t["news"]) < per_kw:
                seen.add(n["link"])
                t["news"].append(n)
        t["traffic_num"] = _traffic_to_int(t["traffic"])
        return t

    with ThreadPoolExecutor(max_workers=6) as pool:
        trends = list(pool.map(enrich, trends))
    trends.sort(key=lambda t: -t["traffic_num"])
    log.info("구글 트렌드: 검색어 %d개 (%s)", len(trends), ", ".join(t["keyword"] for t in trends))
    return trends


def _traffic_to_int(s: str) -> int:
    """'2만+' / '1000+' / '20K+' 같은 표기를 숫자로."""
    s = (s or "").replace(",", "").replace("+", "").strip()
    mult = 1
    for suffix, m in (("만", 10_000), ("천", 1_000), ("K", 1_000), ("M", 1_000_000)):
        if s.endswith(suffix):
            s, mult = s[: -len(suffix)], m
    try:
        return int(float(s) * mult)
    except ValueError:
        return 0
