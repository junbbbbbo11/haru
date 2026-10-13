"""오늘 날씨 (OOTD 추천용) — Open-Meteo 무료 API, 키 필요 없음.

실패하면 None을 돌려주고, OOTD는 날씨 없이 계절 기준으로 추천한다.
"""
import logging

import requests

log = logging.getLogger("haru.weather")

# WMO 날씨 코드 → 한국어
_CODES = [
    ((0,), "맑음"), ((1,), "대체로 맑음"), ((2,), "구름 조금"), ((3,), "흐림"),
    ((45, 48), "안개"), ((51, 53, 55, 56, 57), "이슬비"), ((61, 63, 65, 66, 67), "비"),
    ((71, 73, 75, 77, 85, 86), "눈"), ((80, 81, 82), "소나기"), ((95, 96, 99), "뇌우"),
]


def _describe(code: int) -> str:
    for codes, name in _CODES:
        if code in codes:
            return name
    return "흐림"


def fetch_weather(cfg: dict, timeout: int = 15) -> dict | None:
    city = cfg.get("city", "서울")
    try:
        r = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": cfg.get("latitude", 37.5665),
                "longitude": cfg.get("longitude", 126.978),
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code",
                "timezone": "Asia/Seoul",
                "forecast_days": 1,
            },
            timeout=timeout,
        )
        r.raise_for_status()
        d = r.json()["daily"]
        w = {
            "city": city,
            "t_max": round(d["temperature_2m_max"][0]),
            "t_min": round(d["temperature_2m_min"][0]),
            "rain_pct": int(d["precipitation_probability_max"][0] or 0),
            "sky": _describe(int(d["weather_code"][0])),
        }
    except Exception as e:
        log.warning("  ✗ 날씨 실패 → 계절 기준으로 OOTD 추천: %s", e)
        return None
    w["display"] = f"{city} {w['t_min']}~{w['t_max']}°C · {w['sky']} · 강수 {w['rain_pct']}%"
    log.info("  ✓ 날씨 %s", w["display"])
    return w
