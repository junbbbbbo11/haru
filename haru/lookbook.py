"""오늘의 OOTD 착샷 — 추천 코디를 입은 '목 아래' 실사 이미지를 여성·남성 한 장씩 AI로 생성한다.

1) 이미지 AI에게 목 아래만 나오는 구도로 주문한다.
2) 그래도 얼굴이 그려질 수 있으므로, 얼굴 검출(OpenCV YuNet)로 얼굴을 찾아 턱 아래로 잘라낸다.
3) 잘라낸 사진을 한 번 더 검사해서 얼굴이 남아 있으면 버리고 다시 생성한다.
   → 끝까지 안 되면 그 성별은 일러스트(플랫레이)로 표시.

기본: Cloudflare Workers AI 무료 등급의 FLUX.1 [schnell] (하루 무료 한도 안에서 0원).
필요한 환경변수(GitHub Secrets):
  CLOUDFLARE_ACCOUNT_ID   Cloudflare 계정 ID
  CLOUDFLARE_API_TOKEN    Workers AI 권한이 있는 API 토큰

다른 이미지 AI로 바꾸려면 _cloudflare() 와 같은 모양의 함수를 하나 더 만들어 PROVIDERS에 넣으면 된다.
"""
import base64
import logging
import os
from datetime import timedelta
from pathlib import Path

import requests

from .config import DATA_DIR

log = logging.getLogger("haru.lookbook")
LOOKS_DIR = DATA_DIR / "looks"
FACE_MODEL = Path(__file__).parent / "models" / "face_detection_yunet_2023mar.onnx"

# 날씨 → 배경 분위기
_SCENES = {
    "맑음": "bright clear morning sunlight", "대체로 맑음": "soft sunny morning light",
    "구름 조금": "soft diffused daylight", "흐림": "overcast soft grey daylight", "안개": "misty hazy morning",
    "이슬비": "light drizzle, wet pavement reflections", "비": "rainy day, wet pavement reflections",
    "소나기": "after a rain shower, wet pavement", "눈": "light snowfall", "뇌우": "moody stormy sky",
}


class NoKey(RuntimeError):
    """키가 없음 — 다시 해도 소용없다."""


def build_prompt(look: dict, weather: dict | None, person: str, framing: str) -> str:
    items = look["items"]
    outfit = ", ".join(i["en"] for i in items if i.get("en") and i["category"] != "umbrella")
    umbrella = next((i["en"] for i in items if i["category"] == "umbrella"), None)
    holding = f", and holding a {umbrella} lowered at the side" if umbrella else ""
    light = _SCENES.get((weather or {}).get("sky", ""), "soft natural morning light")
    crop = ("Fashion photo cropped at the neck: the frame starts at the base of the neck, "
            "the head and face are completely outside the top of the frame. Visible from the collarbones down to the shoes.")
    if framing == "studio":
        scene = f"Standing against a plain warm grey seamless studio backdrop, {light} from a large window. Clean lookbook photography."
    else:
        scene = f"Standing on a quiet Seoul city sidewalk, {light}. Street style snap shot on 35mm film."
    return (
        f"{crop} {person.capitalize()} wearing {outfit}{holding}. {scene} "
        f"Fashion magazine editorial, realistic fabric texture and natural wrinkles, natural colors. "
        f"No face, no head, no text, no logos, no watermark."
    )


# ── 이미지 AI ──────────────────────────────────────────────

def _cloudflare(prompt: str, cfg: dict, seed: int) -> bytes:
    account = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    if not account or not token:
        raise NoKey("CLOUDFLARE_ACCOUNT_ID / CLOUDFLARE_API_TOKEN 이 없음")
    model = cfg.get("model", "@cf/black-forest-labs/flux-1-schnell")
    r = requests.post(
        f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/{model}",
        headers={"Authorization": f"Bearer {token}"},
        json={"prompt": prompt, "steps": int(cfg.get("steps", 8)), "seed": seed},
        timeout=int(cfg.get("timeout_seconds", 90)),
    )
    if r.status_code in (401, 403):
        raise NoKey(f"Cloudflare 인증 실패({r.status_code}) — 토큰을 확인하세요")
    if r.status_code != 200:
        raise RuntimeError(f"Cloudflare 응답 {r.status_code}: {r.text[:200]}")
    data = r.json()
    img = (data.get("result") or {}).get("image")
    if not img:
        raise RuntimeError(f"이미지가 없는 응답: {str(data)[:200]}")
    return base64.b64decode(img)


PROVIDERS = {"cloudflare": _cloudflare}


# ── 얼굴 잘라내기 ──────────────────────────────────────────

def _faces(img, threshold: float):
    import cv2

    h, w = img.shape[:2]
    det = cv2.FaceDetectorYN.create(str(FACE_MODEL), "", (w, h), threshold)
    _, faces = det.detect(img)
    return [] if faces is None else [tuple(float(v) for v in f[:4]) for f in faces]


def crop_below_face(data: bytes) -> bytes:
    """얼굴(있다면) 턱 아래부터 4:5 세로 사진으로 잘라낸다. 안전하게 못 자르면 예외."""
    import cv2
    import numpy as np

    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise RuntimeError("이미지를 읽을 수 없음")
    H, W = img.shape[:2]
    faces = _faces(img, 0.5)
    if faces:
        bottom = max(y + fh for x, y, fw, fh in faces)
        tallest = max(fh for *_, fh in faces)
        cut = int(bottom + tallest * 0.35)          # 턱 아래 + 목 일부까지 넉넉히
        cx = sum(x + fw / 2 for x, y, fw, fh in faces) / len(faces)
    else:
        cut = int(H * 0.08)                          # 얼굴이 없어도 위쪽은 살짝 정리
        cx = W / 2
    if cut > H * 0.45:
        raise RuntimeError("얼굴이 너무 아래에 있어 자를 수 없음")

    ch = H - cut
    cw = min(W, int(ch * 0.8))                       # 4:5 세로
    if cw < int(ch * 0.8):                           # 폭이 모자라면 아래쪽 여백을 줄임
        ch = int(cw / 0.8)
    x0 = int(min(max(cx - cw / 2, 0), W - cw))
    out = img[cut:cut + ch, x0:x0 + cw]

    if _faces(out, 0.6):                             # 잘라낸 사진에 얼굴이 또 있으면 실패
        raise RuntimeError("잘라낸 사진에 얼굴이 남아 있음")
    ok, buf = cv2.imencode(".jpg", out, [cv2.IMWRITE_JPEG_QUALITY, 88])
    if not ok:
        raise RuntimeError("JPEG 저장 실패")
    return buf.tobytes()


# ── 저장 ───────────────────────────────────────────────────

def cleanup(today, keep_days: int) -> None:
    """오래된 착샷은 지운다 (저장소 용량 관리). 지워진 날의 지난 호는 일러스트로 보인다."""
    if keep_days <= 0 or not LOOKS_DIR.exists():
        return
    cutoff = (today - timedelta(days=keep_days)).isoformat()
    for p in LOOKS_DIR.iterdir():
        if p.name[:10] < cutoff:
            p.unlink()
            log.info("  오래된 착샷 삭제: %s", p.name)


def _one(look: dict, weather, person: str, today, cfg: dict, provider) -> dict | None:
    prompt = build_prompt(look, weather, person, cfg.get("framing", "street"))
    base_seed = int(today.strftime("%Y%m%d")) * 10 + (0 if look["id"] == "women" else 5)
    tries = int(cfg.get("max_tries", 3))
    for attempt in range(tries):
        try:
            img = crop_below_face(provider(prompt, cfg, base_seed + attempt))
            break
        except NoKey:
            raise
        except Exception as e:
            log.warning("  ✗ [%s] 착샷 %d회차 실패: %s", look["label"], attempt + 1, e)
    else:
        log.warning("  → [%s] 착샷 대신 일러스트로 표시", look["label"])
        return None
    LOOKS_DIR.mkdir(parents=True, exist_ok=True)
    name = f"{today.isoformat()}-{look['id']}.jpg"
    (LOOKS_DIR / name).write_bytes(img)
    log.info("  ✓ [%s] 착샷 생성: data/looks/%s (%d KB)", look["label"], name, len(img) // 1024)
    return {"photo": f"looks/{name}", "photo_prompt": prompt}


def generate_all(ootd: dict, today, cfg: dict, look_cfgs: list[dict]) -> None:
    """ootd['looks'] 각각에 photo/photo_prompt 를 채운다 (실패한 성별은 그대로 둠)."""
    if not cfg.get("enabled", True) or not ootd.get("looks"):
        return
    provider = PROVIDERS.get(cfg.get("provider", "cloudflare"))
    if not provider:
        log.warning("  ✗ 알 수 없는 착샷 provider '%s'", cfg.get("provider"))
        return
    try:
        import cv2  # noqa: F401  얼굴 검사를 못 하면 사진을 싣지 않는다
    except ImportError:
        log.warning("  ✗ opencv 가 설치되지 않아 착샷을 만들지 않음 (pip install -r requirements.txt)")
        return

    persons = {l["id"]: l.get("person", "a person") for l in look_cfgs}
    persons.setdefault("daily", "a person with a slim build")  # 기본 코디(성별 구분 없음)
    for old in LOOKS_DIR.glob(f"{today.isoformat()}*") if LOOKS_DIR.exists() else []:
        old.unlink()
    for look in ootd["looks"]:
        try:
            shot = _one(look, ootd.get("weather"), persons.get(look["id"], "a person"), today, cfg, provider)
        except NoKey as e:
            log.warning("  ✗ 착샷 생성 안 함: %s", e)
            return
        if shot:
            look.update(shot)
    cleanup(today, int(cfg.get("keep_days", 90)))
