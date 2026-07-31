#!/usr/bin/env python3
"""
XAU/USD Analyzer — candlestick patterns + chart patterns + indicator confirmation + limit order opportunities.
Fetches data from Twelve Data (OHLCV) + GoldAPI (spot), computes everything locally, optionally asks
GitHub Models (free AI) for a summary. Output: data/analysis.json (committed to repo, served by Pages).
No external pip deps — stdlib only.
"""

import json
import math
import os
import time
import urllib.request
import urllib.parse

TD_KEY = os.environ.get("TWELVE_DATA_API_KEY", "")
GOLD_KEY = os.environ.get("GOLDAPI_API_KEY", "")
GROQ_KEY = os.environ.get("GROQ_API_KEY", "")
GH_TOKEN = os.environ.get("GH_MODELS_TOKEN", "")

OUT = os.path.join(os.path.dirname(__file__), "..", "data", "analysis.json")
HISTORY = os.path.join(os.path.dirname(__file__), "..", "data", "history.json")


# ---------------------------------------------------------------- helpers
def http_json(url, headers=None, timeout=25):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def td(path, **params):
    params["apikey"] = TD_KEY
    qs = urllib.parse.urlencode(params)
    return http_json(f"https://api.twelvedata.com/{path}?{qs}")


def ema(values, period):
    if not values:
        return []
    k = 2 / (period + 1)
    out = [values[0]]
    for v in values[1:]:
        out.append(v * k + out[-1] * (1 - k))
    return out


def rsi(closes, period=14):
    if len(closes) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0))
        losses.append(max(-d, 0))
    avg_g = sum(gains[:period]) / period
    avg_l = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_g = (avg_g * (period - 1) + gains[i]) / period
        avg_l = (avg_l * (period - 1) + losses[i]) / period
    if avg_l == 0:
        return 100.0
    rs = avg_g / avg_l
    return 100 - 100 / (1 + rs)


def macd(closes, fast=12, slow=26, signal=9):
    if len(closes) < slow + signal:
        return None
    ef = ema(closes, fast)
    es = ema(closes, slow)
    line = [a - b for a, b in zip(ef, es)]
    sig = ema(line, signal)
    hist = [a - b for a, b in zip(line, sig)]
    return {"macd": round(line[-1], 3), "signal": round(sig[-1], 3), "hist": round(hist[-1], 3)}


def atr(candles, period=14):
    if len(candles) < period + 1:
        return None
    trs = []
    for i in range(1, len(candles)):
        h, l, pc = candles[i]["high"], candles[i]["low"], candles[i - 1]["close"]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    return sum(trs[-period:]) / period


# ---------------------------------------------------------------- patterns
def body(c): return abs(c["close"] - c["open"])
def rng(c): return c["high"] - c["low"]
def upper_wick(c): return c["high"] - max(c["open"], c["close"])
def lower_wick(c): return min(c["open"], c["close"]) - c["low"]


def detect_candlestick(candles):
    """Return list of patterns on last candles (daily)."""
    found = []
    n = len(candles)
    for i in range(max(1, n - 10), n):
        c = candles[i]
        p = candles[i - 1]
        r = rng(c)
        if r <= 0:
            continue
        b = body(c)
        uw, lw = upper_wick(c), lower_wick(c)
        bull = c["close"] > c["open"]
        bear = c["close"] < c["open"]
        ctx_up = p["close"] > p["open"]
        ctx_dn = p["close"] < p["open"]

        def add(name, direction, strength=1):
            found.append({"name": name, "direction": direction, "candle": c["datetime"],
                          "strength": strength, "price": round(c["close"], 2)})

        if b <= 0.1 * r:
            add("Doji", "neutral", 1)
        if lw >= 2 * b and uw <= 0.6 * b and b > 0:
            add("Hammer" if not ctx_up else "Hanging Man", "bullish" if not ctx_up else "bearish", 2)
        if uw >= 2 * b and lw <= 0.6 * b and b > 0:
            add("Inverted Hammer" if not ctx_dn else "Shooting Star", "bullish" if not ctx_dn else "bearish", 2)
        if b >= 0.9 * r:
            add("Marubozu", "bullish" if bull else "bearish", 1)
        if p and b > 0:
            pb = body(p)
            if pb > 0 and not bull and p["close"] < p["open"] and c["close"] > c["open"] \
               and c["close"] >= p["open"] and c["open"] <= p["close"]:
                add("Bullish Engulfing", "bullish", 3)
            if pb > 0 and bull and p["close"] > p["open"] and c["close"] < c["open"] \
               and c["close"] <= p["open"] and c["open"] >= p["close"]:
                add("Bearish Engulfing", "bearish", 3)
        # 3-bar patterns
        if i >= 2:
            p2 = candles[i - 2]
            mid_small = body(candles[i - 1]) <= 0.3 * rng(candles[i - 1]) if rng(candles[i - 1]) > 0 else True
            if p2["close"] < p2["open"] and p["close"] < p["open"] and mid_small \
               and bull and c["close"] > (p2["open"] + p2["close"]) / 2:
                add("Morning Star", "bullish", 3)
            if p2["close"] > p2["open"] and p["close"] > p["open"] and mid_small \
               and bear and c["close"] < (p2["open"] + p2["close"]) / 2:
                add("Evening Star", "bearish", 3)
        # 3 consecutive
        if i >= 3 and all(candles[j]["close"] > candles[j]["open"] and
                          candles[j]["close"] > candles[j - 1]["close"] for j in (i - 1, i)):
            if candles[i - 3]["close"] < candles[i - 3]["open"]:
                add("Three White Soldiers", "bullish", 2)
        if i >= 3 and all(candles[j]["close"] < candles[j]["open"] and
                          candles[j]["close"] < candles[j - 1]["close"] for j in (i - 1, i)):
            if candles[i - 3]["close"] > candles[i - 3]["open"]:
                add("Three Black Crows", "bearish", 2)
    # dedupe (keep strongest per candle)
    dedup = {}
    for f in found:
        key = (f["candle"], f["name"])
        if key not in dedup or f["strength"] > dedup[key]["strength"]:
            dedup[key] = f
    return sorted(dedup.values(), key=lambda x: x["candle"], reverse=True)


# ---------------------------------------------------------------- chart patterns / S/R
def find_swings(candles, window=2):
    highs, lows = [], []
    for i in range(window, len(candles) - window):
        if all(candles[i]["high"] > candles[j]["high"] for j in range(i - window, i + window + 1) if j != i):
            highs.append({"price": candles[i]["high"], "i": i, "datetime": candles[i]["datetime"]})
        if all(candles[i]["low"] < candles[j]["low"] for j in range(i - window, i + window + 1) if j != i):
            lows.append({"price": candles[i]["low"], "i": i, "datetime": candles[i]["datetime"]})
    return highs, lows


def cluster_levels(swings, tolerance=0.004):
    """Group swing prices into support/resistance clusters."""
    levels = []
    for s in swings:
        placed = False
        for lv in levels:
            if abs(lv["price"] - s["price"]) / s["price"] <= tolerance:
                lv["touches"] += 1
                lv["prices"].append(s["price"])
                lv["price"] = round(sum(lv["prices"]) / len(lv["prices"]), 2)
                placed = True
                break
        if not placed:
            levels.append({"price": round(s["price"], 2), "touches": 1, "prices": [s["price"]]})
    return [l for l in levels if l["touches"] >= 2]


def trend_from_ema(closes):
    if len(closes) < 200:
        return None
    e20, e50, e200 = ema(closes, 20)[-1], ema(closes, 50)[-1], ema(closes, 200)[-1]
    px = closes[-1]
    if e20 > e50 > e200 and px > e20:
        return "bullish"
    if e20 < e50 < e200 and px < e20:
        return "bearish"
    return "ranging"


def rsi_divergence(closes, rsi_vals, lookback=10):
    """Simple divergence: compare last two swing lows in price vs RSI."""
    if not rsi_vals or len(closes) < lookback + 2:
        return None
    seg = closes[-lookback:]
    rseg = rsi_vals[-lookback:]
    try:
        i1 = seg.index(min(seg))
        i2 = seg.index(min(seg[i1 + 1:])) if i1 + 1 < len(seg) else None
        if i2 is None:
            return None
    except ValueError:
        return None
    if seg[i2] < seg[i1] and rseg[i2] > rseg[i1]:
        return "bullish"
    if seg[i2] > seg[i1] and rseg[i2] < rseg[i1]:
        return "bearish"
    return None


# ---------------------------------------------------------------- opportunities
def make_opportunities(candles, patterns, levels, trend, rsi_val, macd_v, atr_v):
    if not levels or not atr_v:
        return []
    price = candles[-1]["close"]
    supports = sorted([l for l in levels if l["price"] < price], key=lambda x: -x["price"])[:2]
    resistances = sorted([l for l in levels if l["price"] > price], key=lambda x: x["price"])[:2]
    bullish_pats = [p for p in patterns if p["direction"] == "bullish" and p["strength"] >= 2]
    bearish_pats = [p for p in patterns if p["direction"] == "bearish" and p["strength"] >= 2]
    rsi_low = rsi_val is not None and rsi_val < 32
    rsi_high = rsi_val is not None and rsi_val > 68
    opps = []

    # BUY LIMIT candidates
    for s in supports:
        entry = s["price"]
        sl = round(entry - 1.2 * atr_v, 2)
        tp1 = round(entry + 1.8 * atr_v, 2)
        tp2 = round(entry + 3.0 * atr_v, 2)
        rr = round((tp1 - entry) / (entry - sl), 2)
        if rr < 1.5:
            continue
        conf = 35
        reasons = [f"Support {s['price']} ({s['touches']}x) + harga di zona permintaan"]
        if bullish_pats:
            conf += 25
            reasons.append("Pola bullish: " + ", ".join(p["name"] for p in bullish_pats[:2]))
        if rsi_low:
            conf += 15
            reasons.append(f"RSI oversold ({rsi_val:.1f})")
        if trend in ("ranging", None) or trend == "bullish":
            conf += 10
            reasons.append(f"Trend D1: {trend}")
        if macd_v and macd_v["hist"] > 0:
            conf += 10
            reasons.append("MACD histogram positif")
        conf = min(conf, 92)
        opps.append({"side": "BUY_LIMIT", "entry": entry, "sl": sl, "tp": tp1, "tp2": tp2,
                     "rr": rr, "confidence": conf, "reason": "; ".join(reasons[:4])})

    # SELL LIMIT candidates
    for r_ in resistances:
        entry = r_["price"]
        sl = round(entry + 1.2 * atr_v, 2)
        tp1 = round(entry - 1.8 * atr_v, 2)
        tp2 = round(entry - 3.0 * atr_v, 2)
        rr = round((entry - tp1) / (sl - entry), 2)
        if rr < 1.5:
            continue
        conf = 35
        reasons = [f"Resistance {r_['price']} ({r_['touches']}x) + harga di zona supply"]
        if bearish_pats:
            conf += 25
            reasons.append("Pola bearish: " + ", ".join(p["name"] for p in bearish_pats[:2]))
        if rsi_high:
            conf += 15
            reasons.append(f"RSI overbought ({rsi_val:.1f})")
        if trend in ("ranging", None) or trend == "bearish":
            conf += 10
            reasons.append(f"Trend D1: {trend}")
        if macd_v and macd_v["hist"] < 0:
            conf += 10
            reasons.append("MACD histogram negatif")
        conf = min(conf, 92)
        opps.append({"side": "SELL_LIMIT", "entry": entry, "sl": sl, "tp": tp1, "tp2": tp2,
                     "rr": rr, "confidence": conf, "reason": "; ".join(reasons[:4])})

    opps.sort(key=lambda x: -x["confidence"])
    return opps[:3]


# ---------------------------------------------------------------- AI
def ai_summary(payload):
    system = ("Kamu analis pasar emas. Jawab dalam Bahasa Indonesia, ringkas (maks 100 kata), "
              "pakai poin singkat: bias, level penting, dan apakah ada peluang limit order layak. "
              "Bukan saran finansial.")
    user = "Data XAU/USD:\n" + json.dumps(payload, ensure_ascii=False)[:4000]

    # 1) Groq (Llama) — primary
    if GROQ_KEY:
        for model in ("llama-3.3-70b-versatile", "llama-3.1-8b-instant"):
            try:
                body = json.dumps({"model": model, "temperature": 0.3, "max_tokens": 400,
                                   "messages": [{"role": "system", "content": system},
                                                {"role": "user", "content": user}]}).encode()
                req = urllib.request.Request(
                    "https://api.groq.com/openai/v1/chat/completions", data=body,
                    headers={"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json",
                             "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) xau-analytics/1.0"})
                with urllib.request.urlopen(req, timeout=60) as r:
                    resp = json.load(r)
                return resp["choices"][0]["message"]["content"].strip(), f"Groq {model}"
            except Exception:
                continue

    # 2) GitHub Models — fallback
    if GH_TOKEN:
        for model in ("gpt-4o-mini", "meta-llama-3.3-70b-instruct", "gpt-4.1-mini"):
            try:
                body = json.dumps({"model": model, "temperature": 0.3, "max_tokens": 400,
                                   "messages": [{"role": "system", "content": system},
                                                {"role": "user", "content": user}]}).encode()
                req = urllib.request.Request(
                    "https://models.github.ai/inference/chat/completions", data=body,
                    headers={"Authorization": f"Bearer {GH_TOKEN}", "Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=60) as r:
                    resp = json.load(r)
                return resp["choices"][0]["message"]["content"].strip(), model
            except Exception:
                continue
    return None, None


# ---------------------------------------------------------------- main
def main():
    if not TD_KEY:
        raise SystemExit("TWELVE_DATA_API_KEY missing")
    candles = {}
    for iv, size in (("1day", 230), ("4h", 80), ("1h", 60)):
        d = td("time_series", symbol="XAU/USD", interval=iv, outputsize=str(size))
        if d.get("status") != "ok" or not d.get("values"):
            raise RuntimeError(f"Twelve Data {iv} failed: {d}")
        vals = [{"datetime": v["datetime"], "open": float(v["open"]), "high": float(v["high"]),
                 "low": float(v["low"]), "close": float(v["close"])} for v in d["values"]]
        vals.reverse()  # oldest -> newest
        candles[iv] = vals

    spot = None
    if GOLD_KEY:
        try:
            g = http_json("https://www.goldapi.io/api/XAU", {"x-access-token": GOLD_KEY})
            spot = {"price": g.get("price"), "prev_close": g.get("prev_close_price"),
                    "change": g.get("ch"), "change_pct": g.get("chp")}
        except Exception:
            spot = None

    d1 = candles["1day"]
    closes = [c["close"] for c in d1]
    rsi_val = rsi(closes, 14)
    macd_v = macd(closes)
    atr_v = atr(d1)
    trend = trend_from_ema(closes)
    patterns = detect_candlestick(d1)
    highs, lows = find_swings(d1)
    levels = cluster_levels(highs + lows)
    opps = make_opportunities(d1, patterns, levels, trend, rsi_val, macd_v, atr_v)

    # nearest S/R for display
    price = closes[-1]
    supports = sorted([l for l in levels if l["price"] < price], key=lambda x: -x["price"])[:3]
    resistances = sorted([l for l in levels if l["price"] > price], key=lambda x: x["price"])[:3]

    payload = {
        "price": round(price, 2), "trend_d1": trend, "rsi14_d1": round(rsi_val, 1) if rsi_val else None,
        "macd_d1": macd_v, "ema20": round(ema(closes, 20)[-1], 2),
        "ema50": round(ema(closes, 50)[-1], 2), "ema200": round(ema(closes, 200)[-1], 2) if len(closes) >= 200 else None,
        "patterns": patterns[:5], "levels": {"support": supports, "resistance": resistances},
        "opportunities": opps,
    }
    ai_text, ai_model = ai_summary(payload)

    analysis = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": "Twelve Data + GoldAPI (GitHub Actions)",
        "spot": spot,
        "analysis": payload,
        "ai_summary": ai_text,
        "ai_model": ai_model,
        "disclaimer": "Analisa teknis otomatis, bukan saran finansial.",
        "chart": {"1day": d1[-40:], "4h": candles["4h"][-60:]},    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(analysis, f, ensure_ascii=False, indent=1)

    # ---------- HISTORY LOG (memori belajar AI) ----------
    # Simpan rekor ringkas tiap siklus: harga, trend, indikator, pola, level, peluang.
    # Data ini dipakai retrain mingguan → AI makin pinter dari data nyata.
    try:
        history = []
        if os.path.exists(HISTORY):
            with open(HISTORY) as f:
                history = json.load(f)
        record = {
            "ts": analysis["generated_at"],
            "price": round(price, 2),
            "trend": trend,
            "rsi": round(rsi_val, 1) if rsi_val else None,
            "ema20": round(ema(closes, 20)[-1], 2),
            "ema50": round(ema(closes, 50)[-1], 2),
            "patterns": [p["name"] for p in patterns[:3]],
            "support": [l["price"] for l in supports],
            "resistance": [l["price"] for l in resistances],
            "opportunities": [{"side": o["side"], "entry": o["entry"],
                                "conf": o["confidence"]} for o in opps],
        }
        history.append(record)
        history = history[-2000:]  # simpan maks 2000 rekor
        with open(HISTORY, "w") as f:
            json.dump(history, f, ensure_ascii=False, indent=1)
    except Exception as e:
        print(f"  ⚠ history log gagal: {e}")

    print(f"OK — price {price}, trend {trend}, RSI {rsi_val:.1f}, patterns {len(patterns)}, opps {len(opps)}, AI {ai_model or 'none'}")


if __name__ == "__main__":
    main()
