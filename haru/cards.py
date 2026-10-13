"""인스타그램 카드뉴스(1080×1350) 만들기 — 오늘 호 JSON → site/cards/

웹페이지와 같은 글꼴·디자인을 쓰려고 HTML로 카드를 그린 뒤 헤드리스 브라우저(Playwright)로 찍는다.
Playwright가 없거나 실패해도 발행은 멈추지 않는다 (카드뉴스 페이지에 '만들지 못했어요' 표시).

카드 구성: 표지 → 커버스토리 3장 → 섹션 브리핑 → OOTD(여성·남성) → 지표·명언 마무리
"""
import base64
import logging
from pathlib import Path

from .config import DATA_DIR
from .render import _env

log = logging.getLogger("haru.cards")


def _plan(e: dict) -> list[dict]:
    cards = [{"kind": "cover"}]
    for i, s in enumerate(e.get("cover_stories", []), 1):
        cards.append({"kind": "story", "story": s, "n": i})
    if e.get("sections"):
        cards.append({"kind": "brief"})
    for look in (e.get("ootd") or {}).get("looks", []):
        photo = None
        p = DATA_DIR / look["photo"] if look.get("photo") else None
        if p and p.exists():
            photo = "data:image/jpeg;base64," + base64.b64encode(p.read_bytes()).decode()
        cards.append({"kind": "ootd", "look": look, "photo": photo})
        if not photo:
            break  # 착샷이 없으면 일러스트 카드는 한 장만 (두 룩이 같은 기본 코디일 수 있음)
    cards.append({"kind": "end"})
    return cards


def caption(e: dict, site_url: str) -> str:
    lines = [f"📰 {e['title']} · {e['date'][5:7].lstrip('0')}월 {e['date'][8:10].lstrip('0')}일 {e['weekday']}", ""]
    for i, s in enumerate(e.get("cover_stories", []), 1):
        lines.append(f"{i}. {s['headline']}")
    looks = (e.get("ootd") or {}).get("looks", [])
    if looks:
        lines += ["", "👗 오늘의 OOTD: " + " / ".join(f"{l['label']} '{l['title']}'" for l in looks)]
    if site_url:
        lines += ["", f"전체 내용은 → {site_url}"]
    sources = sorted({s["source"] for s in e.get("cover_stories", [])})
    if sources:
        lines += ["", "출처: " + ", ".join(sources)]
    lines += ["", "#하루한장 #오늘의뉴스 #뉴스요약 #아침뉴스 #OOTD #데일리룩"]
    return "\n".join(lines)


def build_cards(e: dict, site_dir: Path, site_url: str = "") -> list[str]:
    out = site_dir / "cards"
    out.mkdir(parents=True, exist_ok=True)
    env = _env()
    files: list[str] = []
    try:
        from playwright.sync_api import sync_playwright

        html = env.get_template("cards.html").render(e=e, cards=_plan(e), site_url=site_url)
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1080, "height": 1350}, device_scale_factor=1)
            page.set_content(html, wait_until="networkidle", timeout=60_000)
            page.evaluate("document.fonts.ready")
            for i, card in enumerate(page.locator(".card").all(), 1):
                name = f"{e['date']}-{i:02d}.jpg"
                card.screenshot(path=str(out / name), type="jpeg", quality=90)
                files.append(name)
            browser.close()
        log.info("카드뉴스 %d장 생성 → site/cards/", len(files))
    except ImportError:
        log.warning("카드뉴스: playwright 가 설치되지 않아 건너뜀")
    except Exception:
        log.exception("카드뉴스 생성 실패 → 건너뜀")
        for f in files:
            (out / f).unlink(missing_ok=True)
        files = []

    (out / "index.html").write_text(
        env.get_template("cards_index.html").render(e=e, files=files, caption=caption(e, site_url)),
        encoding="utf-8")
    if files:
        (out / "caption.txt").write_text(caption(e, site_url), encoding="utf-8")
    return files
