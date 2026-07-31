/* XAU/USD Analyzer — client-side rendering of data/analysis.json */
(async function () {
  const $ = (id) => document.getElementById(id);
  let DATA = null;
  let chart = null;
  let currentTf = "1day";

  function fmt(n, d = 2) {
    if (n === null || n === undefined) return "—";
    return Number(n).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
  }

  function tagClass(dir) {
    if (dir === "bullish" || dir === "up") return "tag-bull";
    if (dir === "bearish" || dir === "down") return "tag-bear";
    return "tag-neutral";
  }

  function renderSpot(spot) {
    const el = $("spot");
    if (!spot || !spot.price) { el.innerHTML = '<span class="muted">Tidak tersedia</span>'; return; }
    const cls = spot.change >= 0 ? "up" : "down";
    const arrow = spot.change >= 0 ? "▲" : "▼";
    el.innerHTML = `
      <div class="price-big ${cls}">$${fmt(spot.price)}</div>
      <div class="${cls}">${arrow} ${fmt(Math.abs(spot.change))} (${fmt(Math.abs(spot.change_pct), 2)}%)</div>
      <div class="muted" style="font-size:.8rem;margin-top:4px">Prev close: $${fmt(spot.prev_close)}</div>`;
  }

  function renderIndicators(a) {
    const el = $("indicators");
    if (!a) { el.innerHTML = '<span class="muted">—</span>'; return; }
    const t = a.trend_d1;
    const ttag = t === "bullish" ? '<span class="tag tag-bull">BULLISH</span>'
      : t === "bearish" ? '<span class="tag tag-bear">BEARISH</span>'
      : '<span class="tag tag-neutral">RANGING</span>';
    const m = a.macd_d1 || {};
    el.innerHTML = `
      <div style="margin-bottom:6px">Trend D1: ${ttag}</div>
      <table>
        <tr><th>RSI(14)</th><td>${fmt(a.rsi14_d1, 1)}</td></tr>
        <tr><th>MACD / Signal / Hist</th><td>${fmt(m.macd)} / ${fmt(m.signal)} / ${fmt(m.hist)}</td></tr>
        <tr><th>EMA20</th><td>$${fmt(a.ema20)}</td></tr>
        <tr><th>EMA50</th><td>$${fmt(a.ema50)}</td></tr>
        <tr><th>EMA200</th><td>${a.ema200 ? "$" + fmt(a.ema200) : "—"}</td></tr>
        <tr><th>Harga</th><td>$${fmt(a.price)}</td></tr>
      </table>`;
  }

  function renderPatterns(pats) {
    const el = $("patterns");
    if (!pats || !pats.length) { el.innerHTML = '<span class="muted">Tidak ada pola terdeteksi</span>'; return; }
    el.innerHTML = '<div class="pat-list">' + pats.map(p => `
      <div class="pat">
        <span class="tag ${tagClass(p.direction)}">${p.direction.toUpperCase()}</span>
        <b>${p.name}</b>
        <span class="muted">· ${p.candle} · $${fmt(p.price)}</span>
      </div>`).join("") + "</div>";
  }

  function renderLevels(lv) {
    const el = $("levels");
    if (!lv) { el.innerHTML = '<span class="muted">—</span>'; return; }
    const row = (title, arr, cls) => arr && arr.length
      ? `<tr><th>${title}</th><td>${arr.map(l => `<span class="tag ${cls}">$${fmt(l.price)} ×${l.touches}</span>`).join(" ")}</td></tr>`
      : "";
    el.innerHTML = `<table>${row("Resistance", lv.resistance, "tag-bear")}${row("Support", lv.support, "tag-bull")}</table>`;
  }

  function renderOpportunities(opps) {
    const el = $("opportunities");
    if (!opps || !opps.length) {
      el.innerHTML = '<span class="muted">Tidak ada peluang limit order layak saat ini (R:R &lt; 1:2 atau tanpa konfirmasi).</span>';
      return;
    }
    el.innerHTML = `<table>
      <tr><th>Side</th><th>Entry</th><th>SL</th><th>TP1</th><th>TP2</th><th>R:R</th><th>Confidence</th></tr>
      ${opps.map(o => `
        <tr>
          <td><span class="tag ${tagClass(o.side === "BUY_LIMIT" ? "bullish" : "bearish")}">${o.side}</span></td>
          <td>$${fmt(o.entry)}</td>
          <td class="down">$${fmt(o.sl)}</td>
          <td class="up">$${fmt(o.tp)}</td>
          <td>$${fmt(o.tp2)}</td>
          <td>1:${fmt(o.rr)}</td>
          <td><b>${o.confidence}%</b></td>
        </tr>
        <tr><td colspan="7" class="muted" style="font-size:.78rem">${o.reason}</td></tr>`).join("")}
    </table>`;
  }

  function renderAI(ai, model) {
    const el = $("ai-summary");
    $("ai-model").textContent = model || "";
    if (!ai) { el.innerHTML = '<span class="muted">AI summary tidak tersedia (token GitHub Models belum di-set atau limit tercapai).</span>'; return; }
    el.innerHTML = `<div class="ai-box">${ai.replace(/\n/g, "<br>")}</div>`;
  }

  function renderChart() {
    const container = $("chart-container");
    container.innerHTML = "";
    if (!DATA || !DATA.chart || !DATA.chart[currentTf]) return;
    const candles = DATA.chart[currentTf];
    if (!window.LightweightCharts) { container.innerHTML = '<span class="muted">Library chart gagal dimuat.</span>'; return; }

    chart = LightweightCharts.createChart(container, {
      autoSize: true,
      height: window.innerWidth <= 480 ? 300 : 420,
      layout: { background: { color: "#161b22" }, textColor: "#8b949e" },
      grid: { vertLines: { color: "#21262d" }, horzLines: { color: "#21262d" } },
      rightPriceScale: { borderColor: "#30363d" },
      timeScale: { borderColor: "#30363d" },
      crosshair: { mode: 0 },
    });
    const series = chart.addCandlestickSeries({
      upColor: "#3fb950", downColor: "#f85149",
      borderUpColor: "#3fb950", borderDownColor: "#f85149",
      wickUpColor: "#3fb950", wickDownColor: "#f85149",
    });
    series.setData(candles.map(c => ({
      time: c.datetime.length > 10 ? c.datetime.replace(" ", "T") : c.datetime,
      open: c.open, high: c.high, low: c.low, close: c.close,
    })));
    chart.timeScale().fitContent();
  }

  async function load() {
    try {
      const res = await fetch("data/analysis.json?t=" + Date.now());
      DATA = await res.json();
    } catch (e) {
      $("last-updated").textContent = "❌ Gagal memuat data. Coba refresh.";
      return;
    }
    $("last-updated").textContent = "Diperbarui: " + (DATA.generated_at || "?") + " (UTC) · Sumber: " + (DATA.source || "");
    renderSpot(DATA.spot);
    renderIndicators(DATA.analysis);
    renderPatterns(DATA.analysis && DATA.analysis.patterns);
    renderLevels(DATA.analysis && DATA.analysis.levels);
    renderOpportunities(DATA.analysis && DATA.analysis.opportunities);
    renderAI(DATA.ai_summary, DATA.ai_model);
    renderChart();
  }

  document.querySelectorAll(".tf-btns button").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tf-btns button").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      currentTf = btn.dataset.tf;
      renderChart();
    });
  });

  load();
  setInterval(load, 5 * 60 * 1000); // auto refresh tiap 5 menit
})();
