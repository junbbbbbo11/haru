"""AI 편집: 섹션별 이슈 선택 + 헤드라인·요약 새로 쓰기 + 커버스토리 + 띠별 운세.

· AI는 후보의 '번호'만 고르고 글만 쓴다. 매체명·링크는 수집 데이터에서 그대로 가져온다
  (AI가 링크를 지어낼 수 없게).
· 응답은 JSON으로 받아 검증하고, 규칙 위반이면 1번 다시 시킨다.
  그래도 안 되면 그 섹션만 원문 헤드라인으로 대체한다.
"""
import logging
import random
import re
from concurrent.futures import ThreadPoolExecutor

from .ai_client import AICallError
from .collect import _bigrams, _similar
from .config import load_yaml

log = logging.getLogger("haru.editor")

SYSTEM = """너는 한국의 고급 매거진 '하루 한 장'의 뉴스 에디터다. 독자는 아침 출근길에 휴대폰으로 3분 안에 오늘의 이슈를 훑는다.

[문체]
- 잡지 에디터처럼 세련되고 간결하게. 담백한 평서문.
- 과장·낚시성 표현 금지: '충격', '경악', '대박', '결국', '드디어', 느낌표, 물음표 헤드라인, 말줄임표를 쓰지 않는다.
- 정치적으로 중립. 특정 정당·인물·진영을 평가하는 형용사를 넣지 않고, 사실과 각 측의 입장만 전한다.

[사실]
- 주어진 제목과 요약문에 있는 사실만 쓴다. 숫자·이름·날짜·국적·직함을 지어내거나 추측하지 않는다.
- 숫자는 원문에 적힌 그대로 쓴다(단위를 바꾸거나 계산하지 않는다). 원문에 없는 수치는 쓰지 않는다.
- 확실하지 않은 내용은 빼고, 짧더라도 정확하게 쓴다.
- 기사 문장을 그대로 베끼지 말고 반드시 너의 새 문장으로 다시 쓴다.
- 한국어 맞춤법과 띄어쓰기를 정확히 지킨다. 단어 사이를 붙여 쓰지 않는다.

[분량]
- headline: 25자 내외(최대 32자). 마침표를 찍지 않는다. 따옴표는 꼭 필요할 때만.
- summary: 1~2문장, 80자 내외(최대 110자). '~했다', '~이다'로 끝나는 문장.

[형식]
- 반드시 요청한 JSON 형식으로만 답한다. 다른 말은 쓰지 않는다."""

ZODIAC = ["쥐", "소", "호랑이", "토끼", "용", "뱀", "말", "양", "원숭이", "닭", "개", "돼지"]

HEADLINE_MAX = 40   # 검증 상한(프롬프트 32자보다 조금 여유)
SUMMARY_MAX = 140
COPY_WINDOW = 18    # 원문과 공백 제외 18자 이상 연속으로 같으면 '베낀 것'으로 본다


# ── 검증 도우미 ─────────────────────────────────────────────

def _norm(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


def _copied(text: str, originals: list[str]) -> bool:
    t = _norm(text)
    src = "\n".join(_norm(o) for o in originals if o)
    if len(t) < COPY_WINDOW or not src:
        return False
    return any(t[i : i + COPY_WINDOW] in src for i in range(len(t) - COPY_WINDOW + 1))


_NUM = re.compile(r"\d[\d,.]*\d|\d")


def _numbers(text: str) -> set[str]:
    return {n.replace(",", "").rstrip(".") for n in _NUM.findall(text or "")}


def _check_text(headline, summary, originals: list[str]) -> str | None:
    """문제가 있으면 이유를, 없으면 None."""
    if not isinstance(headline, str) or not isinstance(summary, str):
        return "headline/summary가 문자열이 아님"
    h, s = headline.strip(), summary.strip()
    if not (6 <= len(h) <= HEADLINE_MAX):
        return f"headline 길이 {len(h)}자 (목표 25자 내외)"
    if not (15 <= len(s) <= SUMMARY_MAX):
        return f"summary 길이 {len(s)}자 (목표 80자 내외)"
    if len(h) >= 12 and " " not in h:
        return "headline에 띄어쓰기가 없음 — 단어 사이를 띄어 써야 함"
    if len(s) >= 20 and s.count(" ") < 3:
        return "summary에 띄어쓰기가 거의 없음 — 맞춤법대로 띄어 써야 함"
    src_nums = _numbers(" ".join(o for o in originals if o))
    bad = sorted(n for n in _numbers(h + " " + s) if n not in src_nums)
    if bad:
        return f"원문에 없는 숫자 {', '.join(bad)} — 숫자는 원문 그대로만 써야 함"
    if any(_norm(h) == _norm(o) for o in originals):
        return "headline이 원문 제목과 똑같음 — 새로 써야 함"
    if _copied(s, originals):
        return "summary가 원문 문장을 그대로 베낌 — 새 문장으로 써야 함"
    return None


def _ask(client, user: str, validate):
    """AI에게 묻고 검증. 실패하면 이유를 알려주고 한 번 더."""
    last_err = None
    for attempt in range(2):
        prompt = user if attempt == 0 else f"{user}\n\n[이전 응답의 문제] {last_err}\n규칙을 지켜 JSON으로 다시 답하라."
        try:
            data = client.complete_json(SYSTEM, prompt)
            return validate(data)
        except AICallError:
            raise  # 서버 호출 자체가 안 되면 다시 해도 소용없다
        except Exception as e:
            last_err = str(e)
            log.warning("    AI 응답 문제(%d회차): %s", attempt + 1, last_err)
    raise ValueError(last_err)


def _cand_line(i, c, snippet_chars: int = 200) -> str:
    line = f"[{i}] (보도 매체 {c.get('coverage', 1)}곳) {c['title']} — {c['source']}"
    if c.get("snippet"):
        line += f"\n    요약문: {c['snippet'][:snippet_chars]}"
    others = [a["title"] for a in c.get("also", [])[:2]]
    if others:
        line += "\n    다른 매체 제목: " + " / ".join(others)
    return line


def _originals(c) -> list[str]:
    return [c["title"], c.get("snippet", "")] + [a["title"] for a in c.get("also", [])]


# ── 커버스토리 ──────────────────────────────────────────────

def edit_covers(client, raw: dict) -> list[dict]:
    pool: dict[str, dict] = {}
    lines = ["[구글 트렌드 인기 검색어와 관련 기사]"]
    for i, t in enumerate(raw.get("trends", [])):
        lines.append(f"\n검색어 '{t['keyword']}' (검색량 {t['traffic']})")
        for j, n in enumerate(t["news"]):
            nid = f"T{i}-{j}"
            pool[nid] = {**n, "keyword": t["keyword"]}
            lines.append(f"  [{nid}] {n['title']} — {n['source']}")

    # 트렌드가 부족한 날을 대비해, 여러 매체가 많이 보도한 기사도 후보로
    tops = sorted(
        (c for s in raw.get("sections", []) for c in s["candidates"]),
        key=lambda c: -c.get("coverage", 1),
    )[:10]
    lines.append("\n[여러 매체가 많이 보도한 기사]")
    for k, c in enumerate(tops):
        nid = f"H{k}"
        pool[nid] = c
        lines.append(f"  [{nid}] (보도 매체 {c.get('coverage', 1)}곳) {c['title']} — {c['source']}")

    user = "\n".join(lines) + """

위 목록에서 오늘 한국 사람들이 가장 많이 이야기하는 이슈 3개를 골라 커버스토리를 써라.
- 같은 사건·같은 주제(예: 같은 야구 경기와 관련된 여러 검색어)는 하나로 합친다. 3개는 서로 다른 이슈여야 한다.
- 가능하면 서로 다른 분야(사회·경제·스포츠·문화 등)로 고른다.
- 이슈마다 대표 기사 하나의 번호를 news_id로 고른다.
- kicker: 헤드라인 위에 작게 붙는 2~8자 키워드 라벨(예: '가을야구', 'K뷰티').
- 화제성이 높은 순서로 정렬한다.

JSON 형식:
{"cover_stories":[{"news_id":"T0-1","kicker":"...","headline":"...","summary":"..."}]}"""

    def validate(data):
        out, seen = [], set()
        for c in data.get("cover_stories", []):
            nid = str(c.get("news_id", ""))
            if nid not in pool or nid in seen:
                continue
            src = pool[nid]
            err = _check_text(c.get("headline"), c.get("summary"), _originals(src) if "also" in src else [src["title"]])
            if err:
                raise ValueError(f"{nid}: {err}")
            seen.add(nid)
            out.append({
                "kicker": str(c.get("kicker") or src.get("keyword") or "")[:12],
                "headline": c["headline"].strip(),
                "summary": c["summary"].strip(),
                "source": src["source"],
                "link": src["link"],
                "original_title": src["title"],
            })
        if len(out) < 3:
            raise ValueError(f"커버스토리가 {len(out)}개뿐 (3개 필요, news_id는 목록의 번호만)")
        return out[:3]

    return _ask(client, user, validate)


# ── 섹션 ───────────────────────────────────────────────────

def edit_section(client, sec: dict, n: int, cover_titles: list[str]) -> list[dict]:
    covered = [_bigrams(t) for t in cover_titles]
    cands = [c for c in sec["candidates"] if not any(_similar(_bigrams(c["title"]), g) for g in covered)]
    cands = cands[: getattr(client, "prompt_candidates", 25)]
    if not cands:
        return []

    user = f"[섹션] {sec['name']}\n\n최근 24시간 '{sec['name']}' 기사 후보다. '보도 매체'는 이 사건을 다룬 매체 수(화제성)다.\n\n"
    user += "\n".join(_cand_line(i, c, getattr(client, "snippet_chars", 200)) for i, c in enumerate(cands))
    user += f"""

화제성과 중요도가 가장 높은 이슈를 최대 {n}개 골라 헤드라인과 요약을 새로 써라.
- 두 번째 이슈는 첫 번째와 다른 사건이어야 하며, 충분히 중요할 때만 넣는다(1개만 골라도 된다).
- '{sec['name']}' 섹션 성격에 맞는 기사를 고른다. 단순 광고성 보도자료, 지자체 행사 홍보, 연예 가십은 피한다.

JSON 형식:
{{"items":[{{"id":0,"headline":"...","summary":"..."}}]}}"""

    def validate(data):
        out, seen = [], set()
        for it in data.get("items", [])[:n]:
            try:
                idx = int(it.get("id"))
            except (TypeError, ValueError):
                continue
            if not (0 <= idx < len(cands)) or idx in seen:
                continue
            c = cands[idx]
            err = _check_text(it.get("headline"), it.get("summary"), _originals(c))
            if err:
                raise ValueError(f"[{idx}] {err}")
            seen.add(idx)
            out.append({
                "headline": it["headline"].strip(),
                "summary": it["summary"].strip(),
                "source": c["source"],
                "link": c["link"],
                "original_title": c["title"],
                "coverage": c.get("coverage", 1),
            })
        if not out:
            raise ValueError("고른 기사가 없음 (id는 후보 번호만)")
        return out

    return _ask(client, user, validate)


# ── 운세 · 명언 ─────────────────────────────────────────────

FORTUNE_BITS = [
    "작은 친절이 큰 웃음으로 돌아오는 날", "미뤄둔 연락 하나가 반가운 소식이 돼요",
    "점심 메뉴 선택 운 최고", "산책길에서 좋은 아이디어가 떠올라요",
    "오늘의 칭찬 한마디가 행운을 불러요", "가벼운 정리정돈이 기분을 바꿔줘요",
    "새로 시작한 일에 순풍이 부는 하루", "오랜 친구와의 대화가 힘이 돼요",
    "좋아하는 노래가 하루의 BGM이 됩니다", "생각보다 일이 술술 풀리는 날",
    "따뜻한 차 한 잔이 행운의 열쇠", "웃는 얼굴에 좋은 사람이 모여요",
    "작은 목표 하나를 이루기 좋은 날", "저녁에 기분 좋은 소식이 있어요",
    "평소보다 감이 좋은 하루, 직감을 믿어요", "가까운 사람에게 고마움을 전해 보세요",
]


def fallback_fortune(date_str: str) -> dict:
    rng = random.Random(date_str)
    bits = rng.sample(FORTUNE_BITS, len(ZODIAC))
    return {"type": "zodiac", "items": [{"animal": a, "text": b} for a, b in zip(ZODIAC, bits)]}


def edit_fortune(client, date_str: str, weekday: str) -> dict:
    user = f"""오늘({date_str} {weekday})의 띠별 운세를 써라.
- 가볍고 긍정적이고 재치 있게, 띠마다 한 줄(25자 이내).
- 불안감을 주는 내용, 건강·사고·금전 손실 경고, 미신적 단정은 쓰지 않는다.
- 12띠 순서: {' '.join(ZODIAC)}

JSON 형식:
{{"zodiac":[{{"animal":"쥐","text":"..."}}]}}"""

    def validate(data):
        items = data.get("zodiac", [])
        by_animal = {str(i.get("animal", "")).replace("띠", ""): str(i.get("text", "")).strip() for i in items}
        out = []
        for a in ZODIAC:
            text = by_animal.get(a, "")
            if not (4 <= len(text) <= 40):
                raise ValueError(f"'{a}' 띠 운세가 없거나 길이가 맞지 않음")
            out.append({"animal": a, "text": text})
        return {"type": "zodiac", "items": out}

    return _ask(client, user, validate)


def pick_quote(today) -> dict | None:
    """quotes.yaml에서 날짜에 따라 하나 (AI가 명언·출처를 지어내지 않도록 직접 고른 목록)."""
    try:
        quotes = load_yaml("quotes.yaml").get("quotes", [])
    except Exception:
        log.exception("quotes.yaml 읽기 실패")
        return None
    if not quotes:
        return None
    q = quotes[today.toordinal() % len(quotes)]
    return {"text": q["text"], "author": q["author"], "work": q.get("work", "")}


# ── 전체 ───────────────────────────────────────────────────

def edit_all(client, raw: dict, fallback: dict, n: int, today, weekday: str) -> tuple[dict, str]:
    """AI로 편집. 실패한 부분은 fallback(원문 헤드라인)으로 채운다.
    돌려주는 mode: 'ai' / 'partial'(일부만 AI) / 'fallback'."""
    ai_parts, total_parts = 0, 0

    total_parts += 1
    try:
        log.info("  커버스토리 편집…")
        covers = edit_covers(client, raw)
        ai_parts += 1
    except AICallError as e:
        log.warning("  AI 서버 호출 불가 → 오늘은 전부 원문 헤드라인으로: %s", e)
        return fallback, "fallback"
    except Exception as e:
        log.warning("  커버스토리 AI 실패 → 원문 헤드라인: %s", e)
        covers = fallback["cover_stories"]

    cover_titles = [c.get("original_title", c["headline"]) for c in covers]
    fb_sections = {s["id"]: s for s in fallback["sections"]}

    def do_section(sec):
        try:
            items = edit_section(client, sec, n, cover_titles)
            log.info("  ✓ [%s] %d개", sec["name"], len(items))
            return sec, items, True
        except Exception as e:
            log.warning("  ✗ [%s] AI 실패 → 원문 헤드라인: %s", sec["name"], e)
            return sec, fb_sections.get(sec["id"], {}).get("items", []), False

    with ThreadPoolExecutor(max_workers=getattr(client, "max_workers", 5)) as pool:
        fortune_future = pool.submit(edit_fortune, client, today.isoformat(), weekday)
        results = list(pool.map(do_section, [s for s in raw.get("sections", []) if s["candidates"]]))

    # 섹션끼리, 그리고 커버와 겹치는 이슈 정리
    used = [_bigrams(t) for t in cover_titles] + [_bigrams(c["headline"]) for c in covers]
    sections = []
    for sec, items, ok in results:
        total_parts += 1
        ai_parts += ok
        kept = []
        for it in items:
            grams = [_bigrams(it.get("original_title", it["headline"])), _bigrams(it["headline"])]
            if any(_similar(g, u) for g in grams for u in used):
                continue
            used.extend(grams)
            kept.append(it)
        if kept:
            sections.append({"id": sec["id"], "name": sec["name"], "items": kept})

    total_parts += 1
    try:
        fortune = fortune_future.result()
        ai_parts += 1
    except Exception as e:
        log.warning("  운세 AI 실패 → 기본 문구: %s", e)
        fortune = fallback_fortune(today.isoformat())

    mode = "ai" if ai_parts == total_parts else "partial" if ai_parts else "fallback"
    return {"cover_stories": covers, "sections": sections, "fortune": fortune}, mode
