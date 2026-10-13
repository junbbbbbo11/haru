"""홈 화면 아이콘(PNG) 만들기 — 디자인을 바꿀 때만 한 번 실행하면 된다.

    pip install playwright && python -m playwright install chromium
    python tools/make_icons.py

결과: templates/static/icon-192.png, icon-512.png, apple-touch-icon.png
"""
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent.parent / "templates" / "static"

HTML = """<!doctype html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Serif+KR:wght@900&display=block">
<style>
  html,body{margin:0}
  .i{width:512px;height:512px;background:#141311;display:grid;place-items:center;position:relative}
  .g{font-family:'Noto Serif KR',serif;font-weight:900;font-size:270px;line-height:1;color:#f6f3ec;transform:translateY(-34px)}
  .r{position:absolute;left:156px;right:156px;bottom:96px;border-top:6px solid #f6f3ec}
  .r2{position:absolute;left:156px;right:156px;bottom:82px;border-top:2px solid #f6f3ec}
</style></head><body><div class="i"><span class="g">한</span><i class="r"></i><i class="r2"></i></div></body></html>"""


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch()
        for size, name in ((512, "icon-512.png"), (192, "icon-192.png"), (180, "apple-touch-icon.png")):
            page = b.new_page(viewport={"width": 512, "height": 512}, device_scale_factor=size / 512)
            page.set_content(HTML, wait_until="networkidle")
            page.evaluate("document.fonts.ready")
            page.locator(".i").screenshot(path=str(OUT / name))
            page.close()
        b.close()
    print("아이콘 저장:", OUT)


if __name__ == "__main__":
    main()
