# 🥇 XAU/USD Analyzer — GitHub Pages

Website analisa **XAU/USD** otomatis: candlestick patterns, pola grafik (support/resistance), konfirmasi indikator (RSI, MACD, EMA), peluang **limit order**, dan ringkasan **AI gratis dari GitHub Models**.

## ✨ Fitur

- 🕯️ **Candlestick patterns** — Doji, Hammer, Engulfing, Morning/Evening Star, Three Soldiers/Crows, dll (10 candle terakhir D1)
- 📐 **Pola grafik** — swing highs/lows → level support & resistance (clustering multi-touch)
- 📊 **Konfirmasi indikator** — RSI(14), MACD, EMA20/50/200, ATR, trend filter
- 🎯 **Peluang limit order** — BUY_LIMIT di support + konfirmasi bullish, SELL_LIMIT di resistance + konfirmasi bearish; filter R:R ≥ 1:2, skor confidence
- 🤖 **AI summary** — ringkasan Bahasa Indonesia dari GitHub Models (gratis)
- ⏱️ **Auto-update** — GitHub Actions tiap 30 menit

## 🚀 Cara Kerja

1. **GitHub Actions** (`/workflows/analyze.yml`) menjalankan `scripts/analyze.py` tiap 30 menit
2. Script menarik data dari **Twelve Data** (OHLCV D1/4H/1H) + **GoldAPI** (spot XAU)
3. Semua analisa dihitung lokal (pola, indikator, level, limit order)
4. Ringkasan AI diminta ke **GitHub Models** (gpt-4o-mini → fallback llama-3.3-70b)
5. Hasil disimpan ke `data/analysis.json` dan di-commit
6. Website statis membaca JSON dan menampilkan semuanya

## 🔑 Secrets yang Dibutuhkan

| Secret | Sumber |
|---|---|
| `TWELVE_DATA_API_KEY` | twelvedata.com (free 800 req/hari) |
| `GOLDAPI_API_KEY` | gold-api.com (free unlimited) |
| `GH_MODELS_TOKEN` | GitHub token untuk GitHub Models (opsional — kalau kosong, AI summary dilewati) |

```bash
gh secret set TWELVE_DATA_API_KEY -R pmuhammadagus-byte/xau-analytics
gh secret set GOLDAPI_API_KEY -R pmuhammadagus-byte/xau-analytics
gh secret set GH_MODELS_TOKEN -R pmuhammadagus-byte/xau-analytics
```

## 🧪 Jalankan Lokal

```bash
TWELVE_DATA_API_KEY=... GOLDAPI_API_KEY=... python3 scripts/analyze.py
```

## ⚠️ Disclaimer

Analisa teknis otomatis — **bukan saran finansial**. Trading emas berisiko tinggi.
