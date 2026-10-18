"""기사 미리보기 사진 — 링크 미리보기(카톡·네이버가 보여 주는 것)처럼 대표 사진 '주소'만 연결한다.

· 사진 파일을 내려받아 저장하거나 서버에 올리지 않는다. 브라우저가 언론사 서버의 사진을 그대로 불러온다(핫링크).
· 출처 매체명과 원문 링크를 항상 함께 보여 준다.
· 사진은 1) RSS 피드가 준 대표 사진 → 2) 기사 페이지의 공유용 이미지(og:image) 순서로 찾는다.
· 구글 뉴스 링크는 실제 언론사 주소로 풀어서(해독) og:image 를 찾는다. 실패하면 사진 없이 요약만 보여 준다.
· 끄려면 config.yaml 의 preview.images: false
"""
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote, urlparse

import requests

log = logging.getLogger("haru.preview")

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept-Language": "ko-KR,ko;q=0.9",
}
_BAD_IMAGE = re.compile(r"(logo|default|noimage|no_image|blank|placeholder|favicon|sprite|common/|/ico_)", re.I)


# ── 구글 뉴스 링크 → 실제 기사 주소 ──────────────────────────

def decode_google_news(url: str, timeout: int = 12) -> str | None:
    m = re.search(r"/articles/([^/?#]+)", url)
    if not m:
        return None
    gid = m.group(1)
    try:
        page = requests.get(f"https://news.google.com/articles/{gid}", headers=HEADERS, timeout=timeout)
        sg = re.search(r'data-n-a-sg="([^"]+)"', page.text)
        ts = re.search(r'data-n-a-ts="([^"]+)"', page.text)
        if not (sg and ts):
            page = requests.get(f"https://news.google.com/rss/articles/{gid}", headers=HEADERS, timeout=timeout)
            sg = re.search(r'data-n-a-sg="([^"]+)"', page.text)
            ts = re.search(r'data-n-a-ts="([^"]+)"', page.text)
        if not (sg and ts):
            return None
        payload = [
            "Fbv4je",
            f'["garturlreq",[["X","X",["X","X"],null,null,1,1,"US:en",null,1,null,null,null,null,null,0,1],"X","X",1,[1,1,1],1,1,null,0,0,null,0],"{gid}",{ts.group(1)},"{sg.group(1)}"]',
        ]
        body = "f.req=" + quote(json.dumps([[payload]]))
        r = requests.post(
            "https://news.google.com/_/DotsSplashUi/data/batchexecute?rpcids=Fbv4je",
            headers={**HEADERS, "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"},
            data=body, timeout=timeout)
        parts = r.text.split("\n\n")
        data = json.loads(parts[1])[:-2]
        decoded = json.loads(data[0][2])[1]
        return decoded if decoded.startswith("http") else None
    except Exception:
        return None


# ── 기사 페이지에서 대표 사진 찾기 ───────────────────────────

def _meta_image(html: str) -> str | None:
    for pat in (r'<meta[^>]+property=["\']og:image(?::secure_url)?["\'][^>]+content=["\']([^"\']+)',
                r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image',
                r'<meta[^>]+name=["\']twitter:image(?::src)?["\'][^>]+content=["\']([^"\']+)'):
        m = re.search(pat, html, re.I)
        if m:
            return m.group(1).replace("&amp;", "&")
    return None


def _good(img: str | None, base: str = "") -> str | None:
    if not img:
        return None
    if img.startswith("//"):
        img = "https:" + img
    elif img.startswith("/") and base:
        p = urlparse(base)
        img = f"{p.scheme}://{p.netloc}{img}"
    if not img.startswith("http") or _BAD_IMAGE.search(img):
        return None
    return img.replace("http://", "https://", 1)  # https 페이지에서 http 사진은 막힘


def _loads(img: str, timeout: int) -> bool:
    """사진이 실제로 열리는지(Referer 없이 — 방문자 브라우저와 같은 조건) 확인."""
    try:
        r = requests.get(img, headers={"User-Agent": HEADERS["User-Agent"]}, timeout=timeout, stream=True)
        ok = r.status_code == 200 and r.headers.get("content-type", "").lower().startswith("image/")
        r.close()
        return ok
    except Exception:
        return False


def find_image(link: str, timeout: int = 12) -> tuple[str | None, str | None]:
    """(대표 사진 주소, 실제 기사 주소). 못 찾으면 사진은 None. 구글 뉴스 링크는 실제 주소를 돌려준다."""
    url = link
    if "news.google.com" in link:
        url = decode_google_news(link, timeout)
        if not url:
            return None, None
    real = url if url != link else None
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        real = real or (r.url if r.url != link else None)
        img = _good(_meta_image(r.text[:300_000]), r.url)
        return (img if img and _loads(img, timeout) else None), real
    except Exception:
        return None, real


def attach_images(articles: list[dict], workers: int = 6) -> int:
    """articles: [{'link', ...}] 각각에 'image'(대표 사진 주소)와 'url'(실제 기사 주소)을 채운다. 사진을 찾은 개수를 돌려준다.
    같은 링크는 한 번만 조사하고, 이미 'image' 가 있으면 건너뛴다."""
    todo = {}
    for a in articles:
        if a.get("link") and not a.get("image"):
            todo.setdefault(a["link"], []).append(a)
    links = list(todo)
    if links:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(find_image, links))
        for link, (img, real) in zip(links, results):
            for a in todo[link]:
                if img:
                    a["image"] = img
                if real:
                    a["url"] = real
    total = sum(1 for a in articles if a.get("link"))
    found = sum(1 for a in articles if a.get("image"))
    log.info("미리보기 사진: %d/%d건 (조사 %d건)", found, total, len(links))
    return found
