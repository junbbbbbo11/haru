"""오늘의 지표: 코스피, 원/달러 환율, 비트코인(원화).

하나가 실패해도 나머지는 그대로 싣고, 실패한 것은 ok=False(→ '데이터 준비 중')로 둔다.
"""
import logging

import requests

log = logging.getLogger("haru.indicators")


def _result(key, name, unit, value, prev, digits):
    change = value - prev
    pct = change / prev * 100 if prev else 0.0
    direction = "up" if change > 0 else "down" if change < 0 else "flat"
    if unit == "만원":  # 1억이 넘는 비트코인 가격은 만 원 단위로 짧게
        display = f"{value / 10_000:,.0f}만원"
    else:
        display = f"{value:,.{digits}f}{unit}"
    return {
        "id": key,
        "name": name,
        "ok": True,
        "value": round(value, digits),
        "change": round(change, digits),
        "change_pct": round(pct, 2),
        "direction": direction,
        "display": display,
        "change_display": f"{'▲' if change > 0 else '▼' if change < 0 else '–'} {abs(pct):.2f}%",
    }


def _failed(key, name):
    return {"id": key, "name": name, "ok": False, "display": "데이터 준비 중"}


def _yahoo(symbol: str) -> tuple[float, float]:
    """마지막 종가(또는 현재가)와 그 전날 종가."""
    import yfinance as yf

    hist = yf.Ticker(symbol).history(period="10d", interval="1d", auto_adjust=False)
    closes = [float(c) for c in hist["Close"].dropna().tolist()]
    if len(closes) < 2:
        raise ValueError(f"{symbol} 데이터 부족 ({len(closes)}일치)")
    return closes[-1], closes[-2]


def _upbit_btc(timeout: int) -> tuple[float, float]:
    r = requests.get("https://api.upbit.com/v1/ticker", params={"markets": "KRW-BTC"}, timeout=timeout)
    r.raise_for_status()
    d = r.json()[0]
    return float(d["trade_price"]), float(d["prev_closing_price"])


def collect_indicators(timeout: int = 15) -> list[dict]:
    jobs = [
        ("kospi", "코스피", "", lambda: _yahoo("^KS11"), 2),
        ("usdkrw", "원/달러", "원", lambda: _yahoo("KRW=X"), 1),
        ("btc", "비트코인", "만원", lambda: _upbit_btc(timeout), 0),
    ]
    out = []
    for key, name, unit, fetch, digits in jobs:
        try:
            value, prev = fetch()
            out.append(_result(key, name, unit, value, prev, digits))
            log.info("  ✓ %s %s (%s)", name, out[-1]["display"], out[-1]["change_display"])
        except Exception as e:
            log.warning("  ✗ %s 실패 → '데이터 준비 중' 표시: %s", name, e)
            out.append(_failed(key, name))
    return out
