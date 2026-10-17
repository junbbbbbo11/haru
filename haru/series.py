"""이번 호의 스타일 시리즈 — 패션 매거진 최신 기사에서 '한 시리즈'(예: 아메카지룩)를 골라 소개한다.

· 매거진 사진·기사 본문은 싣지 않는다 (저작권). 시리즈 소개 글은 AI가 새로 쓰고,
  핵심 아이템은 직접 그린 일러스트(templates/icons.html)로 보여 주며, 원문 기사 링크를 건다.
· 최근에 소개한 시리즈는 피한다 (data/ 의 지난 호를 읽어 중복 방지).
· AI가 안 되는 날은 지어내지 않고, 매거진의 최신 기사 한 건을 그대로(제목·출처·링크) 소개한다.
"""
import json
import logging
import re

from . import collect
from .config import DATA_DIR
from .wardrobe import CATEGORIES, HEX, name_problem, order_items

log = logging.getLogger("haru.series")

MAX_ITEMS_IN_PROMPT = 32


# ── 매거진 최신 기사 수집 ────────────────────────────────────

def collect_magazines(sources: dict, ccfg: dict) -> list[dict]:
    cfg = sources.get("style_series") or {}
    feeds = cfg.get("feeds") or []
    if not feeds:
        return []
    hours = int(cfg.get("max_age_days", 7)) * 24
    timeout = ccfg.get("timeout_seconds", 15)
    items, seen = [], set()
    for f in feeds:
        for it in collect.fetch_feed(f["name"], f["url"], hours, 30, timeout):
            if it["link"] in seen:
                continue
            seen.add(it["link"])
            items.append({"title": it["title"], "source": f["name"], "link": it["link"],
                          "snippet": it.get("snippet", ""), "published": it["published"]})
    items.sort(key=lambda x: x["published"], reverse=True)
    log.info("스타일 시리즈 후보: 매거진 기사 %d건 (%s)", len(items), ", ".join(sorted({i["source"] for i in items})))
    return items


def _recent_series(today, days: int = 14) -> tuple[list[str], set[str]]:
    """최근 호에서 소개한 시리즈 제목과 기사 링크."""
    titles, links = [], set()
    for p in sorted(DATA_DIR.glob("????-??-??.json"), reverse=True):
        if p.stem >= today.isoformat():
            continue
        if len(titles) >= days:
            break
        try:
            s = json.load(open(p, encoding="utf-8")).get("series") or {}
        except Exception:
            continue
        if s.get("title"):
            titles.append(s["title"])
        links.update(a["link"] for a in s.get("articles", []))
    return titles, links


# ── AI: 시리즈 고르고 쓰기 ──────────────────────────────────

def _check_prose(text: str, originals: list[str], lo: int, hi: int, label: str) -> str | None:
    from .editor import _copied

    t = (text or "").strip()
    if not (lo <= len(t) <= hi):
        return f"{label} 길이 {len(t)}자 ({lo}~{hi}자)"
    if len(t) >= 20 and t.count(" ") < 3:
        return f"{label}에 띄어쓰기가 거의 없음 — 맞춤법대로 띄어 써야 함"
    if _copied(t, originals):
        return f"{label}가 기사 문장을 그대로 베낌 — 새 문장으로 써야 함"
    return None


def edit_series(client, ask, magazines: list[dict], weather: dict | None, today, weekday: str,
                recent_titles: list[str]) -> dict:
    pool = magazines[:MAX_ITEMS_IN_PROMPT]
    lines = []
    for i, m in enumerate(pool):
        line = f"[{i}] {m['title']} — {m['source']}"
        if m.get("snippet"):
            line += f"\n    요약문: {m['snippet'][:110]}"
        lines.append(line)
    wline = weather["display"] if weather else "날씨 정보 없음"
    avoid = ", ".join(recent_titles[:10]) or "(없음)"

    user = f"""오늘({today.isoformat()} {weekday}) 소개할 '스타일 시리즈'를 하나 골라 써라.

[패션 매거진 최신 기사]
{chr(10).join(lines)}

- 목록에는 연예·여행·건강·음식 기사도 섞여 있다. 그런 기사는 무시하고, '옷·신발·가방·컬러 등 패션 스타일'을 다룬 기사만 근거로 쓴다.
- 위 기사들이 다루는 스타일·트렌드 중 하나를 '한 시리즈'로 골라 소개한다. 예: '아메카지룩', '고프코어', '발레코어', '올드머니룩', '쿼이어트 럭셔리', '모카 무스 컬러'.
- 반드시 위 기사에 근거가 있어야 한다(기사에서 직접 다루거나 기사 내용과 맞닿은 스타일). 기사에 없는 유행을 지어내지 않는다.
- 최근에 소개한 시리즈는 피한다: {avoid}
- title: 시리즈 이름, 한국어 2~12자 (예: 아메카지룩). 마침표 없이.
  이름은 '기사에 실제로 나온 표현' 또는 '이미 널리 쓰이는 스타일 용어'(아메카지, 고프코어, 발레코어, 올드머니룩 등)만 쓴다.
  '○○코어', '○○룩'처럼 새로 만들어 붙인 이름은 쓰지 않는다. 마땅한 용어가 없으면 기사 표현 그대로(예: '슬림 핏 부츠') 쓴다.
- tagline: 한 줄 부제, 25자 내외.
- description: 2~3문장, 100자 내외. 이 스타일이 무엇이고 요즘 왜 눈에 띄는지. 일반적으로 널리 알려진 정의와 기사에서 확인되는 내용만 쓴다. 브랜드 신제품·가격·인물 발언은 쓰지 않는다.
- items: 이 스타일의 핵심 아이템 4~6개. category는 {', '.join(CATEGORIES)} 중 하나, 같은 category는 한 번만.
  name: 한국어, '첫 단어는 색 또는 소재 + 옷 이름' (예: '네이비 데님 재킷', '카키 치노 팬츠', '브라운 레더 부츠'). 띄어쓰기를 지키고 영어를 섞지 않는다.
  color: 색 이름, hex: '#RRGGBB' 형식의 실제 색.
- tips: 입는 법 3가지. 각 30~60자, '~한다/~좋다' 체.
- weather_tip: 오늘 날씨({wline})에 맞춰 이 스타일을 응용하는 한 줄, 40자 내외.
- article_ids: 근거가 된 기사 번호 1~3개 (위 목록의 번호).

JSON 형식:
{{"title":"...","tagline":"...","description":"...","items":[{{"category":"outer","name":"...","color":"...","hex":"#2F4A6D"}}],"tips":["...","...","..."],"weather_tip":"...","article_ids":[0]}}"""

    def validate(d):
        title = str(d.get("title", "")).strip()
        tagline = str(d.get("tagline", "")).strip()
        if not (2 <= len(title) <= 14):
            raise ValueError(f"title 길이 {len(title)}자 (2~12자)")
        if title in recent_titles:
            raise ValueError(f"'{title}'는 최근에 소개한 시리즈 — 다른 스타일을 골라야 함")
        if not (4 <= len(tagline) <= 50):
            raise ValueError(f"tagline 길이 {len(tagline)}자 (25자 내외)")

        ids = []
        for x in d.get("article_ids", []):
            try:
                k = int(x)
            except (TypeError, ValueError):
                continue
            if 0 <= k < len(pool) and k not in ids:
                ids.append(k)
        if not ids:
            raise ValueError("article_ids에 유효한 기사 번호가 없음 (목록의 번호만)")
        arts = [pool[k] for k in ids[:3]]
        originals = [a["title"] for a in arts] + [a.get("snippet", "") for a in arts]

        # 기사에 근거 없는 '지어낸 유행' 거르기: 시리즈 이름이 기사 글에 나오거나, 소개 글이 고른 기사와 내용이 겹쳐야 한다
        corpus = " ".join(m["title"] + " " + m.get("snippet", "") for m in pool).replace(" ", "")
        key = title.replace(" ", "")
        key = key[:-1] if key.endswith("룩") and len(key) > 2 else key
        d_grams = collect._bigrams(str(d.get("description", "")))
        a_grams = collect._bigrams(" ".join(originals))
        overlap = len(d_grams & a_grams) / len(d_grams) if d_grams else 0
        if key not in corpus and overlap < 0.12:
            raise ValueError(f"'{title}'은(는) 위 기사들에서 다루지 않는 스타일 — 기사에 나오는 스타일을 골라야 함")

        problem = (_check_prose(d.get("description"), originals, 40, 280, "description")
                   or _check_prose(d.get("weather_tip"), originals, 10, 90, "weather_tip"))
        if problem:
            raise ValueError(problem)

        tips = [str(t).strip() for t in d.get("tips", []) if str(t).strip()]
        if len(tips) < 3:
            raise ValueError(f"tips가 {len(tips)}개 (3개 필요)")
        for t in tips[:3]:
            p = _check_prose(t, originals, 12, 100, "tips")
            if p:
                raise ValueError(p)

        items, seen = [], set()
        for it in d.get("items", []):
            cat = str(it.get("category", "")).strip().lower()
            name, color, hx = (str(it.get(k, "")).strip() for k in ("name", "color", "hex"))
            if cat not in CATEGORIES or cat in seen:
                continue
            if not (2 <= len(name) <= 16) or not HEX.match(hx):
                raise ValueError(f"아이템 '{name}': name 길이 또는 hex 형식(#RRGGBB) 오류")
            if len(name) >= 6 and " " not in name:
                raise ValueError(f"아이템 이름 '{name}'에 띄어쓰기가 없음 — 예: '카멜 울 코트'")
            if re.search(r"[A-Za-z]{3,}", name):
                raise ValueError(f"아이템 이름 '{name}'에 영어가 섞임 — 이름은 한국어로만")
            problem = name_problem(cat, name)
            if problem:
                raise ValueError(problem)
            seen.add(cat)
            items.append({"category": cat, "name": name, "color": color[:8], "hex": hx.upper()})
        if not (4 <= len(items) <= 6):
            raise ValueError(f"아이템이 {len(items)}개 (4~6개)")

        return {
            "by": "ai", "title": title, "tagline": tagline,
            "description": d["description"].strip(),
            "items": order_items(items), "tips": [t[:100] for t in tips[:3]],
            "weather_tip": d["weather_tip"].strip(),
            "weather": weather,
            "articles": [{"title": a["title"], "source": a["source"], "link": a["link"]} for a in arts],
        }

    return ask(client, user, validate)


# ── AI가 안 되는 날: 매거진 최신 기사 한 건을 그대로 소개 ───────

# 연예·여행·건강 기사가 섞여 있으므로, AI 없이 고를 때는 제목에 패션 단어가 있는 기사만 후보로
_FASHION_WORDS = ("룩", "패션", "스타일", "코디", "입", "신발", "부츠", "니트", "가방", "재킷", "코트", "팬츠", "데님", "셔츠",
                  "스커트", "원피스", "슈즈", "컬렉션", "트렌드", "맨투맨", "어그", "스웨터", "아우터", "컬러", "착장", "백")


def fallback_series(magazines: list[dict], weather: dict | None, recent_links: set[str]) -> dict | None:
    if not magazines:
        return None
    fashion = [m for m in magazines if any(w in m["title"] for w in _FASHION_WORDS)] or magazines
    pick = next((m for m in fashion if m["link"] not in recent_links), fashion[0])
    return {"by": "rule", "title": pick["title"], "tagline": f"{pick['source']} 최신 기사", "description": "",
            "items": [], "tips": [], "weather_tip": "", "weather": weather,
            "articles": [{"title": pick["title"], "source": pick["source"], "link": pick["link"]}]}


def make_series(client, ask, magazines: list[dict], weather: dict | None, today, weekday: str) -> dict | None:
    if not magazines:
        log.warning("  ✗ 스타일 시리즈: 매거진 기사를 못 가져와 이번 호는 생략")
        return None
    recent_titles, recent_links = _recent_series(today)
    if client:
        try:
            log.info("  스타일 시리즈 선정…")
            s = edit_series(client, ask, magazines, weather, today, weekday, recent_titles)
            log.info("  ✓ 스타일 시리즈: %s (%s)", s["title"], ", ".join(a["source"] for a in s["articles"]))
            return s
        except Exception as e:
            log.warning("  ✗ 스타일 시리즈 AI 실패 → 매거진 최신 기사 소개로 대체: %s", str(e)[:150])
    return fallback_series(magazines, weather, recent_links)
