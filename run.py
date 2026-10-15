"""하루 한 장 — 오늘 호를 만든다.

    python run.py                 전체 실행 (수집 → 지표 → AI 편집 → 저장 → 웹페이지 → 이메일)
    python run.py --no-ai         AI 없이 원문 헤드라인으로
    python run.py --no-email      이메일 보내지 않기
    python run.py --render-only   수집 없이 data/ 의 JSON으로 웹페이지만 다시 만들기

어느 한 단계가 실패해도 가능한 만큼 발행한다.
"""
import argparse
import logging
import os
import sys
import time

from haru import cards, collect, edition, editor, indicators, lookbook, ootd, render, weather
from haru.ai_client import make_client
from haru.config import load_config, load_sources, now_kst
from haru.log import setup_logging


def site_url(cfg: dict) -> str:
    """config의 site.url, 없으면 GitHub 저장소 이름으로 Pages 주소를 만든다."""
    url = (cfg.get("site", {}).get("url") or "").strip()
    if url:
        return url if url.endswith("/") else url + "/"
    repo = os.environ.get("GITHUB_REPOSITORY", "")  # 예: myname/haru-hanjang
    if "/" in repo:
        owner, name = repo.split("/", 1)
        owner = owner.lower()
        if name.lower() == f"{owner}.github.io":
            return f"https://{owner}.github.io/"
        return f"https://{owner}.github.io/{name}/"
    return ""


def make_edition(cfg: dict, log: logging.Logger, use_ai: bool) -> dict:
    now = now_kst()
    today = now.date()
    sources = load_sources()
    ccfg = cfg.get("collect", {})
    n_items = ccfg.get("items_per_section", 2)

    # 1) 뉴스 수집
    log.info("── 1. 뉴스 수집")
    raw = {"date": today.isoformat(), "collected_at": now.isoformat(timespec="seconds")}
    raw["trends"] = collect.collect_trends(sources, ccfg)
    raw["sections"] = collect.collect_sections(sources, ccfg)

    # 2) 지표
    log.info("── 2. 오늘의 지표")
    try:
        raw["indicators"] = indicators.collect_indicators(ccfg.get("timeout_seconds", 15))
    except Exception:
        log.exception("지표 수집 전체 실패 → '데이터 준비 중'")
        raw["indicators"] = []
    raw["weather"] = weather.fetch_weather(cfg.get("weather", {}), ccfg.get("timeout_seconds", 15))
    edition.save_json(raw, edition.raw_path(today))

    # 3) 편집
    log.info("── 3. 편집")
    fallback = edition.build_fallback(raw, n_items)
    fallback["fortune"] = editor.fallback_fortune(today.isoformat())
    edited, mode = fallback, "fallback"
    client = make_client(cfg.get("ai", {})) if use_ai else None
    if client:
        # 무료 AI는 느리고 가끔 응답이 없어서, 정해진 시간이 지나면 남은 부분은 원문 헤드라인으로 마무리
        budget = float(cfg.get("ai", {}).get("time_budget_minutes", 30)) * 60
        client.deadline = time.monotonic() + budget
    if client:
        try:
            edited, mode = editor.edit_all(client, raw, fallback, n_items, today,
                                           edition.WEEKDAYS[today.weekday()])
        except Exception:
            log.exception("AI 편집 전체 실패 → 원문 헤드라인으로 발행")
            edited, mode = fallback, "fallback"
    ocfg = cfg.get("ootd", {})
    if ocfg.get("enabled", True):
        # AI 서버 자체가 안 되는 날(mode=fallback)은 다시 부르지 않는다
        edited["ootd"] = ootd.make_ootd(client if mode != "fallback" else None, editor._ask, raw, today,
                                        edition.WEEKDAYS[today.weekday()], ocfg)
        edited["ootd"]["default"] = ocfg.get("default", "men")
        # 여성·남성 착샷 (실패한 쪽은 페이지에 일러스트로 표시)
        lookbook.generate_all(edited["ootd"], today, cfg.get("lookbook", {}), ootd.look_settings(ocfg))
    edition.fit_reading_time(edited, ccfg.get("max_total_items", 13))
    if client:
        u = client.usage
        log.info("AI 사용량: 호출 %d회, 입력 %s토큰, 출력 %s토큰",
                 u["calls"], f"{u['input_tokens']:,}", f"{u['output_tokens']:,}")
    edited["quote"] = editor.pick_quote(today)

    result = edition.assemble(today, now, cfg.get("site", {}), raw, edited, mode)
    edition.save_json(result, edition.edition_path(today))
    log.info("오늘 호 저장: data/%s.json (커버 %d개, 섹션 %d개, 편집=%s, %d분 읽기)",
             today, len(result["cover_stories"]), len(result["sections"]), mode, result["reading_minutes"])
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description="하루 한 장 발행")
    ap.add_argument("--no-ai", action="store_true", help="AI 편집 없이 원문 헤드라인으로")
    ap.add_argument("--no-email", action="store_true", help="이메일 보내지 않기")
    ap.add_argument("--render-only", action="store_true", help="수집 없이 웹페이지만 다시 만들기")
    args = ap.parse_args()

    log = setup_logging()
    started = time.time()
    cfg = load_config()
    url = site_url(cfg)
    log.info("===== 하루 한 장 %s 발행 시작 =====", now_kst().date())

    result = None
    if not args.render_only:
        result = make_edition(cfg, log, use_ai=not args.no_ai)

    # 4) 웹페이지
    log.info("── 4. 웹페이지 렌더링")
    want_cards = cfg.get("cards", {}).get("enabled", True)
    try:
        render.build_site(url, cards=want_cards)
    except Exception:
        log.exception("웹페이지 렌더링 실패")
        return 1

    # 4-1) 인스타그램 카드뉴스 (실패해도 발행은 계속)
    if want_cards:
        log.info("── 4-1. 카드뉴스")
        try:
            cards.build_cards(render.load_editions()[-1], render.SITE_DIR, url)
        except Exception:
            log.exception("카드뉴스 실패 → 건너뜀")

    # 5) 이메일 (선택)
    if result and not args.no_email and cfg.get("email", {}).get("enabled"):
        log.info("── 5. 이메일 발송")
        from haru.mailer import send_edition_email
        send_edition_email(result, url)

    log.info("===== 완료 (%.1f초)%s =====", time.time() - started, f" → {url}" if url else "")
    return 0


if __name__ == "__main__":
    sys.exit(main())
