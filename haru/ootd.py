"""오늘의 OOTD: 날씨 + 오늘의 패션 뉴스를 보고 여성·남성 한 벌씩 추천한다.

페이지에서는 여성 | 남성 탭으로 골라 보고, 착샷(haru/lookbook.py)이 있으면 사진으로,
없으면 직접 그린 SVG 실루엣에 추천 색을 입힌 '플랫레이'로 보여준다.
AI가 없거나 실패하면 기온대별 기본 코디로 대체한다.
"""
import logging
import re

log = logging.getLogger("haru.ootd")

# 페이지에 그릴 수 있는 아이템 종류 (templates/icons.html 의 garment 모양과 짝)
CATEGORIES = ["outer", "top", "dress", "bottom", "shoes", "bag", "hat", "scarf", "glasses", "umbrella"]
_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")

DEFAULT_LOOKS = [
    {"id": "women", "label": "여성", "style": "여성 데일리룩", "person": "a woman in her 30s with a slim build"},
    {"id": "men", "label": "남성", "style": "남성 데일리룩", "person": "a man in his 30s with an average build"},
]


def _order(items: list[dict]) -> list[dict]:
    return sorted(items, key=lambda i: CATEGORIES.index(i["category"]))


def look_settings(cfg: dict) -> list[dict]:
    looks = cfg.get("looks") or DEFAULT_LOOKS
    return [{**d, **l} for l in looks for d in [next((x for x in DEFAULT_LOOKS if x["id"] == l.get("id")), {})]]


# ── AI 추천 ────────────────────────────────────────────────

def _weather_line(w: dict | None, month: int) -> str:
    if not w:
        return f"날씨 정보 없음 → {month}월 서울의 평년 날씨를 기준으로 할 것"
    return f"{w['city']} 최저 {w['t_min']}°C, 최고 {w['t_max']}°C, {w['sky']}, 강수확률 {w['rain_pct']}%"


def _validate_look(d: dict, label: str) -> dict:
    title, keyword, tip = (str(d.get(k, "")).strip() for k in ("title", "keyword", "tip"))
    if not (4 <= len(title) <= 24):
        raise ValueError(f"[{label}] title 길이 {len(title)}자 (15자 내외)")
    if not (2 <= len(keyword) <= 12):
        raise ValueError(f"[{label}] keyword 길이가 맞지 않음 (2~8자)")
    if not (15 <= len(tip) <= 120):
        raise ValueError(f"[{label}] tip 길이 {len(tip)}자 (70자 내외)")
    items, seen = [], set()
    for it in d.get("items", []):
        cat = str(it.get("category", "")).strip().lower()
        name, color, hx, en = (str(it.get(k, "")).strip() for k in ("name", "color", "hex", "en"))
        if cat not in CATEGORIES or cat in seen:
            continue
        if not (2 <= len(name) <= 16) or not _HEX.match(hx):
            raise ValueError(f"[{label}] 아이템 '{name}': name 길이 또는 hex 형식(#RRGGBB) 오류")
        if not re.fullmatch(r"[A-Za-z0-9 ,.'/-]{4,60}", en):
            raise ValueError(f"[{label}] 아이템 '{name}': en(영어 설명)이 없거나 영어가 아님")
        seen.add(cat)
        items.append({"category": cat, "name": name, "color": color[:8], "hex": hx.upper(), "en": en})
    if not (seen & {"top", "dress"}) or "shoes" not in seen:
        raise ValueError(f"[{label}] top(또는 dress)과 shoes는 꼭 넣어야 함")
    if not (4 <= len(items) <= 6):
        raise ValueError(f"[{label}] 아이템이 {len(items)}개 (4~6개)")
    return {"title": title, "keyword": keyword, "items": _order(items), "tip": tip}


def edit_ootd(client, ask, raw: dict, today, weekday: str, looks: list[dict]) -> dict:
    """ask 는 editor._ask (검증 실패 시 한 번 더 시키는 도우미)."""
    w = raw.get("weather")
    fashion = next((s["candidates"] for s in raw.get("sections", []) if s["id"] == "fashion"), [])[:12]
    news = "\n".join(f"[{i}] {c['title']} — {c['source']}" for i, c in enumerate(fashion)) or "(없음)"
    targets = "\n".join(f"- {l['id']}: {l['style']}" for l in looks)
    example = ", ".join(f'"{l["id"]}": {{"title":"...","keyword":"...","items":[...],"tip":"..."}}' for l in looks)

    user = f"""오늘({today.isoformat()} {weekday})의 OOTD를 아래 대상별로 한 벌씩 제안하라.

[대상]
{targets}
[날씨] {_weather_line(w, today.month)}
[최근 24시간 패션 기사]
{news}

- 지금의 트렌드를 참고하되, 실제로 출근·외출할 때 바로 입을 수 있는 현실적인 룩으로.
- 대상마다 서로 다른 룩으로 쓰되, 같은 날씨·같은 트렌드를 공유한다.
- 일교차가 크면 겹쳐 입기를, 강수확률 60% 이상이면 우산이나 비에 강한 신발을 고려한다.
- title: 룩 이름, 15자 내외 (예: '트렌치 위에 니트 한 겹'). 마침표 없이.
- keyword: 무드 키워드 2~8자 (예: '젠틀 캐주얼').
- items: 4~6개. category는 {', '.join(CATEGORIES)} 중 하나.
  top 또는 dress 중 1개, shoes 1개는 꼭 넣는다. 같은 category는 한 번만.
  name: '카멜 울 코트'처럼 색·소재·형태가 드러나게, 12자 이내. 브랜드명은 쓰지 않는다.
  color: 색 이름(예: '카멜'), hex: '#RRGGBB' 형식의 실제 색.
  en: 착샷 이미지 생성용 영어 설명, 색·소재·형태 포함 (예: 'camel wool single-breasted coat').
- tip: 스타일링 팁 1~2문장, 70자 내외, '~해요'체가 아닌 '~하다/~좋다'체.
- trend_id: 참고한 기사 번호(없으면 null).

JSON 형식 (items 원소: {{"category":"outer","name":"...","color":"...","hex":"#B5835A","en":"camel wool coat"}}):
{{"looks": {{{example}}}, "trend_id": null}}"""

    def validate(d):
        got = d.get("looks") or {}
        out = []
        for l in looks:
            if l["id"] not in got:
                raise ValueError(f"looks에 '{l['id']}'가 없음")
            out.append({"id": l["id"], "label": l["label"], **_validate_look(got[l["id"]], l["label"])})
        trend = None
        tid = d.get("trend_id")
        if isinstance(tid, int) and 0 <= tid < len(fashion):
            c = fashion[tid]
            trend = {"title": c["title"], "source": c["source"], "link": c["link"]}
        return {"looks": out, "trend": trend, "weather": w, "by": "ai"}

    return ask(client, user, validate)


# ── AI 없을 때: 기온대별 기본 코디 ─────────────────────────

# (하루 평균기온 이상, 제목, 키워드, 아이템들, 팁) — 흔히 쓰는 '기온별 옷차림표' 기준
_BANDS = [
    (28, "린넨 한 장의 여유", "서머 이지", [
        ("top", "화이트 린넨 셔츠", "화이트", "#F4F1EA", "white linen shirt"), ("bottom", "베이지 와이드 쇼츠", "베이지", "#D8C3A0", "beige wide-leg shorts"),
        ("shoes", "블랙 레더 샌들", "블랙", "#1E1E1E", "black leather sandals"), ("hat", "내추럴 버킷햇", "내추럴", "#E2D3B5", "natural straw bucket hat")],
     "통기성 좋은 린넨에 품이 넉넉한 하의를 맞추면 한낮 더위에도 단정하다."),
    (23, "티셔츠의 정석", "클린 캐주얼", [
        ("top", "네이비 코튼 티셔츠", "네이비", "#24304A", "navy cotton crew-neck t-shirt"), ("bottom", "아이보리 치노 팬츠", "아이보리", "#EDE6D6", "ivory chino pants"),
        ("shoes", "화이트 스니커즈", "화이트", "#F7F7F5", "white leather sneakers"), ("bag", "캔버스 토트백", "에크루", "#E6DCC8", "ecru canvas tote bag")],
     "기본 티셔츠는 핏이 전부다. 어깨선이 맞는 한 장에 밝은 하의로 산뜻하게."),
    (20, "셔츠로 시작하는 아침", "오피스 데일리", [
        ("top", "스카이블루 옥스퍼드 셔츠", "스카이블루", "#AFC6DE", "sky blue oxford shirt"), ("bottom", "그레이 슬랙스", "그레이", "#8A8D91", "grey tailored slacks"),
        ("shoes", "브라운 페니 로퍼", "브라운", "#6B4430", "brown penny loafers"), ("bag", "블랙 레더 백", "블랙", "#1E1E1E", "black leather shoulder bag")],
     "소매를 두 번 접어 올리면 긴팔 셔츠도 한결 가볍다. 로퍼로 단정함을 더하자."),
    (17, "가디건 한 겹의 온도", "소프트 레이어드", [
        ("outer", "오트밀 니트 가디건", "오트밀", "#D9CBB3", "oatmeal knit cardigan"), ("top", "화이트 크루넥 티", "화이트", "#F4F2EC", "white crew-neck t-shirt"),
        ("bottom", "인디고 스트레이트 데님", "인디고", "#2F4A6D", "indigo straight-leg jeans"), ("shoes", "그레이 스웨이드 스니커즈", "그레이", "#9A9690", "grey suede sneakers")],
     "아침저녁 쌀쌀할 땐 벗기 쉬운 가디건이 정답이다. 단추를 반쯤 풀어 여유 있게."),
    (12, "트렌치 위에 니트 한 겹", "클래식 가을", [
        ("outer", "베이지 트렌치코트", "베이지", "#C8AE85", "beige trench coat"), ("top", "브라운 크루넥 니트", "브라운", "#7A5638", "brown crew-neck knit sweater"),
        ("bottom", "블랙 와이드 슬랙스", "블랙", "#1F1F1F", "black wide-leg slacks"), ("shoes", "버건디 레더 로퍼", "버건디", "#5E1F2B", "burgundy leather loafers"),
        ("bag", "탄 숄더백", "탄", "#A97E55", "tan leather shoulder bag")],
     "트렌치는 벨트를 뒤로 묶고 앞을 열어 두면 한층 가볍다. 니트 색으로 온기를 더하자."),
    (9, "울 재킷의 계절", "모던 어반", [
        ("outer", "차콜 울 블레이저", "차콜", "#3A3B3E", "charcoal wool blazer"), ("top", "아이보리 터틀넥", "아이보리", "#EEE7DA", "ivory turtleneck"),
        ("bottom", "라이트 블루 데님", "라이트블루", "#8FA8C4", "light blue jeans"), ("shoes", "블랙 첼시 부츠", "블랙", "#1C1C1C", "black chelsea boots")],
     "터틀넥 위 블레이저는 셔츠보다 편하고 단정하다. 부츠로 무게 중심을 아래에."),
    (5, "코트와 머플러의 계절", "윈터 클래식", [
        ("outer", "카멜 울 코트", "카멜", "#B5835A", "camel wool coat"), ("top", "그레이 울 니트", "그레이", "#9C9C9A", "grey wool sweater"),
        ("bottom", "차콜 울 팬츠", "차콜", "#353638", "charcoal wool trousers"), ("shoes", "블랙 레더 부츠", "블랙", "#1C1C1C", "black leather ankle boots"),
        ("scarf", "버건디 캐시미어 머플러", "버건디", "#6A2433", "burgundy cashmere scarf")],
     "톤을 맞춘 코트와 니트에 머플러로 색 하나만 더하면 겨울 룩이 완성된다."),
    (-99, "따뜻함이 최고의 스타일", "코지 윈터", [
        ("outer", "블랙 롱 패딩", "블랙", "#1D1D1F", "black long puffer coat"), ("top", "크림 케이블 니트", "크림", "#EFE6D2", "cream cable-knit sweater"),
        ("bottom", "그레이 기모 팬츠", "그레이", "#7F8186", "grey fleece-lined trousers"), ("shoes", "브라운 방한 부츠", "브라운", "#5A3E2B", "brown winter boots"),
        ("hat", "아이보리 비니", "아이보리", "#ECE6DA", "ivory knit beanie"), ("scarf", "그레이 울 머플러", "그레이", "#8E8E8E", "grey wool scarf")],
     "한파엔 목·머리·발을 먼저 지키자. 밝은 니트와 비니로 패딩의 무게감을 덜어낸다."),
]
# 날씨를 모를 때 쓰는 월별 평년 평균기온(서울)
_MONTH_AVG = {1: -2, 2: 1, 3: 6, 4: 13, 5: 18, 6: 23, 7: 26, 8: 26, 9: 22, 10: 15, 11: 7, 12: 0}


def fallback_ootd(raw: dict, today, looks: list[dict]) -> dict:
    w = raw.get("weather")
    avg = (w["t_max"] + w["t_min"]) / 2 if w else _MONTH_AVG[today.month]
    floor, title, keyword, items, tip = next(b for b in _BANDS if avg >= b[0])
    items = [{"category": c, "name": n, "color": cn, "hex": h, "en": en} for c, n, cn, h, en in items]
    if w and w["t_max"] - w["t_min"] >= 9 and "outer" not in {i["category"] for i in items}:
        tip += " 일교차가 크니 가볍게 걸칠 겉옷 하나를 챙기자."
    if w and w["rain_pct"] >= 60 and len(items) < 6:
        items.append({"category": "umbrella", "name": "블랙 장우산", "color": "블랙", "hex": "#222222",
                      "en": "black long umbrella"})
        tip += " 비 소식이 있으니 우산도 함께."
    # 기본 코디는 성별 구분 없이 입는 구성이라 탭 없이 한 벌만 싣는다
    out = [{"id": "daily", "label": "데일리", "title": title, "keyword": keyword,
            "items": _order(items), "tip": tip}]
    return {"looks": out, "trend": None, "weather": w, "by": "rule"}


def make_ootd(client, ask, raw: dict, today, weekday: str, cfg: dict) -> dict:
    looks = look_settings(cfg)
    if client:
        try:
            log.info("  OOTD 추천…")
            o = edit_ootd(client, ask, raw, today, weekday, looks)
            log.info("  ✓ OOTD: %s", " / ".join(f"{l['label']} '{l['title']}'" for l in o["looks"]))
            return o
        except Exception as e:
            log.warning("  ✗ OOTD AI 실패 → 기온대별 기본 코디: %s", e)
    return fallback_ootd(raw, today, looks)
