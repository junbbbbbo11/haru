"""(선택) 발행 후 이메일로 오늘 호 링크 보내기 — Gmail SMTP + 앱 비밀번호.

필요한 환경변수(GitHub Secrets):
  GMAIL_ADDRESS       보내는 Gmail 주소
  GMAIL_APP_PASSWORD  Gmail 앱 비밀번호(16자리)
  MAIL_TO             받는 주소 (여러 명이면 쉼표로 구분, 없으면 보내는 주소로)
"""
import logging
import os
import smtplib
from datetime import date
from email.message import EmailMessage
from html import escape

log = logging.getLogger("haru.mailer")


def send_edition_email(edition: dict, site_url: str) -> bool:
    sender = os.environ.get("GMAIL_ADDRESS", "").strip()
    password = os.environ.get("GMAIL_APP_PASSWORD", "").replace(" ", "").strip()
    to = [a.strip() for a in os.environ.get("MAIL_TO", sender).split(",") if a.strip()]
    if not sender or not password or not to:
        log.warning("이메일: GMAIL_ADDRESS / GMAIL_APP_PASSWORD 가 없어 보내지 않음")
        return False

    d = date.fromisoformat(edition["date"])
    title = edition.get("title", "하루 한 장")
    link = site_url or ""
    covers = edition.get("cover_stories", [])[:3]

    text_lines = [f"{d.month}월 {d.day}일 {edition['weekday']} · Vol. {edition['vol']}", ""]
    text_lines += [f"{i}. {c['headline']}" for i, c in enumerate(covers, 1)]
    text_lines += ["", f"오늘 호 읽기 → {link}" if link else ""]

    items_html = "".join(
        f'<li style="margin:0 0 14px;font-size:17px;line-height:1.45;font-weight:700">{escape(c["headline"])}'
        + (f'<div style="font-weight:400;font-size:14px;color:#555;margin-top:4px">{escape(c["summary"])}</div>' if c.get("summary") else "")
        + "</li>"
        for c in covers
    )
    button = (
        f'<a href="{escape(link)}" style="display:inline-block;background:#141311;color:#f6f3ec;'
        f'padding:12px 22px;border-radius:999px;text-decoration:none;font-weight:700">오늘 호 읽기 →</a>'
        if link else ""
    )
    html = f"""<div style="background:#f6f3ec;padding:28px 20px;font-family:-apple-system,'Apple SD Gothic Neo','Malgun Gothic',sans-serif;color:#141311">
  <div style="max-width:560px;margin:0 auto">
    <div style="font-size:12px;letter-spacing:.15em;color:#77716a">DAILY EDITION · VOL. {edition['vol']}</div>
    <div style="font-family:Georgia,serif;font-size:40px;font-weight:900;letter-spacing:-.04em;margin:8px 0 4px">{escape(title)}</div>
    <div style="font-size:13px;color:#3b3833;border-top:1px solid #141311;border-bottom:1px solid #141311;padding:7px 0;margin-bottom:22px">{d.year}년 {d.month}월 {d.day}일 {edition['weekday']} · {edition.get('reading_minutes', 3)}분 읽기</div>
    <div style="font-size:12px;letter-spacing:.15em;color:#77716a;margin-bottom:12px">COVER STORY</div>
    <ol style="padding-left:20px;margin:0 0 24px">{items_html}</ol>
    {button}
  </div>
</div>"""

    msg = EmailMessage()
    msg["Subject"] = f"오늘의 {title} · {d.month}월 {d.day}일 {edition['weekday']}"
    msg["From"] = f"{title} <{sender}>"
    msg["To"] = ", ".join(to)
    msg.set_content("\n".join(text_lines))
    msg.add_alternative(html, subtype="html")

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
            smtp.login(sender, password)
            smtp.send_message(msg)
    except Exception as e:
        log.warning("이메일 발송 실패: %s", e)
        return False
    log.info("이메일 발송 완료 → %d명", len(to))
    return True
