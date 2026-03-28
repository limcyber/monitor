function setText(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value ?? "-";
}

function scoreColor(score) {
  if (score >= 70) return "#0f7b6c";
  if (score >= 40) return "#b47f00";
  return "#b94343";
}

function scoreTone(score) {
  if (score >= 70) return "success";
  if (score >= 40) return "warning";
  return "danger";
}

function marketTone(score) {
  return `tone-${scoreTone(score)}`;
}

function formatScore(score) {
  return `${score}/100`;
}

function formatPercent(value) {
  if (typeof value !== "number" || Number.isNaN(value)) return "-";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

function formatClose(value, changePct) {
  if (typeof value !== "number" || Number.isNaN(value)) return "-";
  return `${value.toFixed(2)} (${formatPercent(changePct)})`;
}

function quoteTone(changePct, invert = false) {
  if (typeof changePct !== "number" || Number.isNaN(changePct)) return "warning";
  if (changePct === 0) return "warning";
  const positive = invert ? changePct < 0 : changePct > 0;
  return positive ? "success" : "danger";
}

function renderQuote(id, value, changePct, invert = false) {
  const el = document.getElementById(id);
  if (!el) return;
  const tone = quoteTone(changePct, invert);
  el.className = `quote-value ${tone}`;
  el.textContent = formatClose(Number(value), changePct);
}

function renderList(el, items, fallback) {
  if (!el) return;
  el.innerHTML = "";
  const rows = items && items.length ? items : [fallback];
  rows.forEach((item) => {
    const li = document.createElement("li");
    li.textContent = item;
    el.appendChild(li);
  });
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function tagTone(text) {
  const value = String(text || "");
  if (value.includes("경고") || value.includes("주의") || value.includes("데드") || value.includes("약함") || value.includes("자제") || value.includes("보수")) {
    return "danger";
  }
  if (value.includes("강함") || value.includes("골든") || value.includes("좋음")) {
    return "success";
  }
  return "warning";
}

function renderTagList(el, items, fallback) {
  if (!el) return;
  const rows = items && items.length ? items : [fallback];
  el.innerHTML = rows.map((item) => `<span class="mini-tag ${tagTone(item)}">${escapeHtml(item)}</span>`).join("");
}

const appState = {
  data: null,
  charts: [],
  stockRendered: false,
};

function applyTheme(theme) {
  const normalized = theme === "bw" ? "bw" : "finviz";
  document.body.dataset.theme = normalized === "bw" ? "bw" : "";
  const isBw = normalized === "bw";
  const bwButton = document.getElementById("themeBw");
  const colorButton = document.getElementById("themeColor");
  if (bwButton) bwButton.setAttribute("aria-pressed", String(isBw));
  if (colorButton) colorButton.setAttribute("aria-pressed", String(!isBw));
  if (bwButton) bwButton.textContent = "어둡게";
  if (colorButton) colorButton.textContent = "밝게";
  try {
    localStorage.setItem("monitorTheme", normalized);
  } catch {}
  if (appState.data) {
    renderMarketCharts(appState.data.charts.market);
    renderStressTable(appState.data.charts.market);
  }
}

function initThemeToggle() {
  let saved = "bw";
  try {
    saved = localStorage.getItem("monitorTheme");
  } catch {
    saved = null;
  }
  if (saved !== "bw" && saved !== "finviz") saved = "bw";
  applyTheme(saved || "bw");
  document.getElementById("themeBw")?.addEventListener("click", () => applyTheme("bw"));
  document.getElementById("themeColor")?.addEventListener("click", () => applyTheme("finviz"));
}

function syncFactorBoxPair(grid) {
  const boxes = Array.from(grid.querySelectorAll(".factor-box"));
  if (boxes.length !== 2 || grid.dataset.synced === "true") return;
  grid.dataset.synced = "true";
  boxes.forEach((box, index) => {
    box.addEventListener("toggle", () => {
      if (box.dataset.syncing === "true") return;
      const peer = boxes[index === 0 ? 1 : 0];
      if (!peer) return;
      peer.dataset.syncing = "true";
      peer.open = box.open;
      requestAnimationFrame(() => {
        delete peer.dataset.syncing;
      });
    });
  });
}

function bindFactorBoxes(root = document) {
  root.querySelectorAll(".factor-grid").forEach(syncFactorBoxPair);
}

function bindStockExtraInfo(root = document) {
  root.querySelectorAll(".stock-extra-info").forEach((details) => {
    if (details.dataset.synced === "true") return;
    details.dataset.synced = "true";
    details.addEventListener("toggle", () => {
      details.querySelectorAll(".factor-box").forEach((box) => {
        box.open = details.open;
      });
    });
  });
}

function chartTheme() {
  const dark = document.body.dataset.theme === "bw";
  return {
    dark,
    bg: dark ? "#0b0e0c" : "#ffffff",
    grid: dark ? "rgba(121,160,122,0.18)" : "rgba(106,118,131,0.12)",
    ticks: dark ? "#96c49c" : "#51606f",
  };
}

function formatChartLabel(raw) {
  if (!raw) return "";
  const str = String(raw);
  if (/^\d{4}-\d{2}-\d{2}/.test(str)) {
    return `${str.slice(5, 7)}/${str.slice(8, 10)}`;
  }
  return str;
}

function formatAxisValue(value) {
  if (typeof value !== "number" || Number.isNaN(value)) return "";
  if (Math.abs(value) >= 1000) return value.toLocaleString("en-US", { maximumFractionDigits: 0 });
  if (Math.abs(value) >= 100) return value.toFixed(0);
  if (Math.abs(value) >= 10) return value.toFixed(1);
  return value.toFixed(2);
}

function formatManAxisValue(value) {
  if (typeof value !== "number" || Number.isNaN(value)) return "";
  const abs = Math.abs(value);
  if (abs >= 10000) {
    const scaled = value / 10000;
    const digits = Math.abs(scaled) >= 100 ? 0 : Math.abs(scaled) >= 10 ? 1 : 2;
    return `${scaled.toFixed(digits)}만`;
  }
  if (abs >= 1000) return value.toLocaleString("en-US", { maximumFractionDigits: 0 });
  if (abs >= 100) return value.toFixed(0);
  if (abs >= 10) return value.toFixed(1);
  return value.toFixed(2);
}

function createBackgroundPlugin(theme) {
  return {
    id: "chartBackground",
    beforeDraw(chart) {
      const { ctx } = chart;
      const area = chart.chartArea;
      if (!area) return;
      ctx.save();
      ctx.fillStyle = theme.bg;
      ctx.fillRect(area.left, area.top, area.right - area.left, area.bottom - area.top);
      ctx.restore();
    },
  };
}

function lineChart(ctx, labels, datasets, options = {}) {
  if (!ctx || !window.Chart) return null;
  const theme = chartTheme();
  return new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: datasets.map((dataset) => ({
        fill: false,
        tension: 0.18,
        pointRadius: 0,
        borderWidth: dataset.borderWidth || 2,
        borderDash: dataset.borderDash || [],
        ...dataset,
      })),
    },
    plugins: [createBackgroundPlugin(theme)],
    options: {
      responsive: true,
      maintainAspectRatio: true,
      layout: { padding: { left: 2, right: 2, top: 4, bottom: 0 } },
      interaction: { mode: "index", intersect: false },
      scales: {
        x: {
          grid: { color: theme.grid },
          ticks: {
            color: theme.ticks,
            autoSkip: true,
            maxTicksLimit: 6,
            maxRotation: 0,
            font: { size: 10 },
            callback(value, index) {
              return formatChartLabel(labels[index]);
            },
          },
        },
        y: {
          position: "left",
          grid: { color: theme.grid },
          ticks: {
            color: theme.ticks,
            maxTicksLimit: 5,
            callback(value) {
              return formatAxisValue(value);
            },
          },
        },
        y2: options.rightAxis
          ? {
              position: "right",
              grid: { drawOnChartArea: false },
              ticks: {
                color: theme.ticks,
                maxTicksLimit: 5,
                callback(value) {
                  return formatAxisValue(value);
                },
              },
            }
          : undefined,
      },
      plugins: {
        legend: { display: false },
      },
    },
  });
}

function supportMetricChart(ctx, labels, series, color) {
  if (!ctx || !window.Chart) return null;
  const theme = chartTheme();
  return new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          data: series,
          fill: false,
          tension: 0.18,
          pointRadius: 0,
          borderWidth: 2,
          borderColor: color,
        },
      ],
    },
    plugins: [createBackgroundPlugin(theme)],
    options: {
      responsive: true,
      maintainAspectRatio: false,
      layout: { padding: { left: 0, right: 0, top: 0, bottom: 0 } },
      interaction: { mode: "index", intersect: false },
      scales: {
        x: {
          grid: { color: theme.grid },
          ticks: {
            color: theme.ticks,
            maxTicksLimit: 4,
            maxRotation: 0,
            font: { size: 8 },
            callback(value, index) {
              return formatChartLabel(labels[index]);
            },
          },
        },
        y: {
          grid: { color: theme.grid },
          ticks: {
            color: theme.ticks,
            maxTicksLimit: 4,
            font: { size: 8 },
            callback(value) {
              return formatAxisValue(value);
            },
          },
        },
      },
      plugins: {
        legend: { display: false },
        tooltip: { enabled: false },
      },
    },
  });
}

function renderChartLegend(targetId, items) {
  const holder = document.getElementById(targetId);
  if (!holder) return;
  holder.innerHTML = items
    .map(
      (item) => `
        <span class="chart-legend-item">
          <span class="chart-legend-swatch" style="background:${item.color}"></span>
          <span>${escapeHtml(item.label)}</span>
        </span>`
    )
    .join("");
}

function destroyCharts() {
  appState.charts.forEach((chart) => chart?.destroy?.());
  appState.charts = [];
}

function renderMiniSparkline(series, color) {
  if (!series || !series.length) return '<div class="sparkline-empty">-</div>';
  const width = 84;
  const height = 18;
  const values = series.filter((value) => typeof value === "number" && !Number.isNaN(value));
  if (!values.length) return '<div class="sparkline-empty">-</div>';
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const points = values
    .map((value, index) => {
      const x = (index / Math.max(values.length - 1, 1)) * width;
      const y = height - ((value - min) / range) * height;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return `<svg class="sparkline" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none"><polyline fill="none" stroke="${color}" stroke-width="1.6" points="${points}"></polyline></svg>`;
}

function lastNumeric(series) {
  if (!series?.length) return null;
  for (let index = series.length - 1; index >= 0; index -= 1) {
    const value = series[index];
    if (typeof value === "number" && !Number.isNaN(value)) return value;
  }
  return null;
}

function changePctFromSeries(series) {
  if (!series?.length || series.length < 2) return null;
  const current = lastNumeric(series);
  const prev = [...series].reverse().find((value) => typeof value === "number" && !Number.isNaN(value) && value !== current);
  if (!current || !prev) return null;
  return ((current / prev) - 1) * 100;
}

function renderStressColumn(targetId, rows) {
  const el = document.getElementById(targetId);
  if (!el) return;
  el.innerHTML = `
    <div class="stress-column-grid">
      ${rows
        .map(
          (row) => `
          <article class="stress-cell">
            <div class="stress-main">
              <strong class="stress-label">${row.label}</strong>
              <span class="stress-quote ${quoteTone(row.change, row.label === "USD/KRW" || row.label === "VIX" || row.label === "Brent")}">
                <span class="stress-value">${row.value == null ? "-" : formatAxisValue(row.value)}</span>
                ${row.change == null ? "" : `<span class="stress-change">(${formatPercent(row.change)})</span>`}
              </span>
            </div>
            <div class="stress-chart-wrap">
              <canvas id="stress-chart-${row.label.replace(/[^a-z0-9]+/gi, "-").toLowerCase()}" class="stress-chart-canvas"></canvas>
            </div>
          </article>
        `
        )
        .join("")}
    </div>
  `;
  rows.forEach((row) => {
    const canvas = document.getElementById(`stress-chart-${row.label.replace(/[^a-z0-9]+/gi, "-").toLowerCase()}`);
    if (!canvas) return;
    const chart = supportMetricChart(canvas, row.dates || [], row.series || [], row.color);
    if (chart) appState.charts.push(chart);
  });
}

function renderStressTable(charts) {
  const rows = [
    {
      label: "KOSPI200",
      value: lastNumeric(charts?.kospi200_close),
      change: changePctFromSeries(charts?.kospi200_close),
      note: "대형 대표주 체감",
      color: "#2563eb",
      series: charts?.kospi200_close,
      dates: charts?.dates,
    },
    {
      label: "USD/KRW",
      value: lastNumeric(charts?.usdkrw_close),
      change: changePctFromSeries(charts?.usdkrw_close),
      note: "원달러 부담",
      color: "#ef4444",
      series: charts?.usdkrw_close,
      dates: charts?.dates,
    },
    {
      label: "VIX",
      value: lastNumeric(charts?.vix_close),
      change: changePctFromSeries(charts?.vix_close),
      note: "해외 변동성",
      color: "#6b7280",
      series: charts?.vix_close,
      dates: charts?.dates,
    },
    {
      label: "Brent",
      value: lastNumeric(charts?.brent_close),
      change: changePctFromSeries(charts?.brent_close),
      note: "국제유가",
      color: "#fb923c",
      series: charts?.brent_close,
      dates: charts?.dates,
    },
    {
      label: "KOSDAQ/KOSPI",
      value: lastNumeric(charts?.kosdaq_kospi_ratio),
      change: changePctFromSeries(charts?.kosdaq_kospi_ratio),
      note: "중소형 참여도",
      color: "#f59e0b",
      series: charts?.kosdaq_kospi_ratio,
      dates: charts?.dates,
    },
  ];
  renderStressColumn("krStressPrimary", rows.slice(0, 2));
  renderStressColumn("krStressSecondary", rows.slice(2, 5));
}

function renderMarket(data) {
  setText("generatedAt", `생성 시각: ${data.generated_at_et}`);
  setText("asOf", `데이터 기준 시각: ${data.market_data_as_of}`);
  const marketPanel = document.querySelector(".market-panel");
  if (marketPanel) {
    marketPanel.classList.remove("tone-success", "tone-warning", "tone-danger");
    marketPanel.classList.add(marketTone(data.market.score));
  }
  const marketState = document.getElementById("marketState");
  marketState.textContent = data.market.state;
  marketState.className = `pill ${scoreTone(data.market.score)}`;
  ["marketScore", "marketExecution", "marketAction"].forEach((id) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.className = `market-value ${marketTone(data.market.score)}`;
  });
  setText("marketScore", formatScore(data.market.score));
  setText("marketExecution", data.market.execution_strength);
  setText("marketAction", data.market.action);
  renderQuote("marketKospiQuote", data.market.metrics.kospi_close, data.market.metrics.kospi_change_pct);
  renderQuote("marketKosdaqQuote", data.market.metrics.kosdaq_close, data.market.metrics.kosdaq_change_pct);
  renderQuote("marketKospi200Quote", data.market.metrics.kospi200_close, data.market.metrics.kospi200_change_pct);
  renderQuote("marketSemiconQuote", data.market.metrics.semicon_close, data.market.metrics.semicon_change_pct);
  renderQuote("marketUsdkrwQuote", data.market.metrics.usdkrw_close, data.market.metrics.usdkrw_change_pct, true);

  renderList(document.getElementById("marketCrossHighlights"), data.market.cross_highlights, "최근 눈에 띄는 골든크로스나 데드크로스는 없습니다.");
  setText("marketEasy", data.market.easy_explanation);
  setText("marketInvalidation", data.market.invalidation);
  renderList(document.getElementById("marketReasons"), data.market.top_reasons, "오늘은 시장을 좋게 볼 만한 신호가 많지 않습니다.");
  renderList(document.getElementById("marketPositiveFactors"), data.market.positive_factors, "점수를 올려준 신호가 많지 않습니다.");
  renderList(document.getElementById("marketNegativeFactors"), data.market.negative_factors, "크게 나쁜 신호는 없습니다.");
  renderTagList(document.getElementById("marketChangeTags"), data.market.change_tags, "오늘 변화 없음");
  renderTagList(document.getElementById("marketPositionTags"), data.market.position_tags, "기본 운용");
  renderTagList(document.getElementById("marketAlertTags"), data.market.alerts, "오늘 별도 알림 없음");
  renderTagList(document.getElementById("marketWarningTags"), data.market.confidence_warnings, "데이터 경고 없음");
  renderTagList(document.getElementById("marketHistoryTags"), data.market.history_tags, "히스토리 없음");
  bindFactorBoxes(document);
}

function renderTable(rows) {
  const body = document.getElementById("watchlistTable");
  if (!body) return;
  body.innerHTML = "";
  rows.forEach((row) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td data-label="종목"><strong>${escapeHtml(row.name || row.ticker)}</strong></td>
      <td data-label="현재가"><span class="quote-value ${quoteTone(row.close_change_pct)}">${escapeHtml(formatClose(row.close, row.close_change_pct))}</span></td>
      <td data-label="점수"><span class="pill ${scoreTone(row.stock_score)}">${formatScore(row.stock_score)}</span></td>
      <td data-label="상태"><span class="pill ${scoreTone(row.stock_score)}">${escapeHtml(row.stock_state)}</span></td>
      <td data-label="추천 행동"><span class="pill ${scoreTone(row.stock_score)}">${escapeHtml(row.final_action)}</span></td>
      <td data-label="메모">${escapeHtml(row.note)}</td>
    `;
    body.appendChild(tr);
  });
}

function stockSeriesPalette() {
  return {
    close: "#2563eb",
    dma5: "#ef4444",
    dma20: "#0ea5e9",
    dma50: "#f59e0b",
    volume: "#6b7280",
  };
}

function renderMarketCharts(charts) {
  destroyCharts();
  const palette = {
    kospi: "#2563eb",
    kospi200: "#f59e0b",
    kosdaq: "#0f766e",
    kosdaq200: "#ef4444",
  };
  const labels = charts.dates;
  const monthStart = Math.max(0, labels.length - 21);
  const monthLabels = labels.slice(monthStart);
  appState.charts.push(
    lineChart(
      document.getElementById("krIndexChart"),
      monthLabels,
      [
        { label: "KOSPI", data: charts.kospi_close.slice(monthStart), borderColor: palette.kospi, yAxisID: "y" },
        { label: "KOSPI 200일선", data: charts.kospi_dma200.slice(monthStart), borderColor: palette.kospi200, yAxisID: "y", borderDash: [5, 4] },
        { label: "KOSDAQ", data: charts.kosdaq_close.slice(monthStart), borderColor: palette.kosdaq, yAxisID: "y2" },
        { label: "KOSDAQ 200일선", data: charts.kosdaq_dma200.slice(monthStart), borderColor: palette.kosdaq200, yAxisID: "y2", borderDash: [5, 4] },
      ],
      { rightAxis: true }
    )
  );
  renderChartLegend("krIndexLegend", [
    { label: "KOSPI", color: palette.kospi },
    { label: "KOSPI 200일선", color: palette.kospi200 },
    { label: "KOSDAQ", color: palette.kosdaq },
    { label: "KOSDAQ 200일선", color: palette.kosdaq200 },
  ]);
}

function renderStocks(stocks) {
  const holder = document.getElementById("stockCards");
  if (!holder) return;
  holder.innerHTML = "";
  stocks.forEach((s) => {
    const stockPalette = stockSeriesPalette();
    const changeAndHistory = (s.change_tags?.length ? s.change_tags : ["오늘 변화 없음"]).concat(s.history_tags?.length ? s.history_tags : []).slice(0, 2);
    const positionAndAlerts = (s.position_tags?.length ? s.position_tags : ["기본 운용"]).concat(s.alerts?.length ? s.alerts : []).slice(0, 2);
    const warningTags = (s.confidence_warnings?.length ? s.confidence_warnings : ["데이터 경고 없음"]).slice(0, 2);
    const card = document.createElement("article");
    card.className = "stock-card";
    card.innerHTML = `
      <div class="stock-top">
        <h3>${escapeHtml(s.name || s.ticker)} <span class="stock-subcode">${escapeHtml(s.ticker)}</span></h3>
        <span class="pill ${scoreTone(s.stock_score)}">${escapeHtml(s.stock_state)}</span>
      </div>
      <p style="margin:6px 0;color:${scoreColor(s.stock_score)};"><strong>점수:</strong> ${formatScore(s.stock_score)} | <strong>추천 행동:</strong> ${escapeHtml(s.final_action)}</p>
      <div class="mini-meta">
        <span>시장구분: ${escapeHtml(s.market_label || "-")}</span>
        <span>현재가: ${formatClose(s.metrics.close, s.metrics.close_change_pct)}</span>
      </div>
      <div class="cross-highlight-block stock-cross-highlight">
        <h4>크로스 신호</h4>
        <ul>${(s.cross_highlights?.length ? s.cross_highlights : ["최근 눈에 띄는 골든크로스나 데드크로스는 없습니다."]).map((r) => `<li>${escapeHtml(r)}</li>`).join("")}</ul>
      </div>
      <details class="extra-info-box stock-extra-info">
        <summary>설명과 세부 정보</summary>
        <div class="stock-summary-copy">
          <p>${escapeHtml(s.easy_explanation)}</p>
          <ul>${(s.top_reasons || []).map((r) => `<li>${escapeHtml(r)}</li>`).join("")}</ul>
        </div>
        <div class="factor-grid stock-factor-grid">
          <details class="factor-box factor-box-positive">
            <summary>점수를 올린 항목</summary>
            <ul>${(s.positive_factors?.length ? s.positive_factors : ["점수를 올려준 신호가 많지 않습니다."]).map((r) => `<li>${escapeHtml(r)}</li>`).join("")}</ul>
          </details>
          <details class="factor-box factor-box-negative">
            <summary>점수를 깎았거나 불리한 항목</summary>
            <ul>${(s.negative_factors?.length ? s.negative_factors : ["크게 나쁜 신호는 없습니다."]).map((r) => `<li>${escapeHtml(r)}</li>`).join("")}</ul>
          </details>
        </div>
        <div class="tag-row compact-tag-row">
          <h4>변화/히스토리</h4>
          <div class="tag-list">${changeAndHistory.map((r) => `<span class="mini-tag ${tagTone(r)}">${escapeHtml(r)}</span>`).join("")}</div>
        </div>
        <div class="tag-row compact-tag-row">
          <h4>운용/알림</h4>
          <div class="tag-list">${positionAndAlerts.map((r) => `<span class="mini-tag ${tagTone(r)}">${escapeHtml(r)}</span>`).join("")}</div>
        </div>
        <div class="tag-row compact-tag-row">
          <h4>주의</h4>
          <div class="tag-list">${warningTags.map((r) => `<span class="mini-tag ${tagTone(r)}">${escapeHtml(r)}</span>`).join("")}</div>
        </div>
      </details>
      <canvas id="chart-${s.ticker}" class="stock-chart"></canvas>
      <div id="stockLegend-${s.ticker}" class="chart-legend stock-chart-legend"></div>
    `;
    holder.appendChild(card);
    const ctx = document.getElementById(`chart-${s.ticker}`);
    if (!window.Chart || !ctx) return;
    const theme = chartTheme();
    appState.charts.push(
      new Chart(ctx, {
        type: "line",
        data: {
          labels: s.series.dates,
          datasets: [
            { type: "line", label: "현재가", data: s.series.close, borderColor: stockPalette.close, yAxisID: "price" },
            { type: "line", label: "5일선", data: s.series.dma5, borderColor: stockPalette.dma5, yAxisID: "price" },
            { type: "line", label: "20일선", data: s.series.dma20, borderColor: stockPalette.dma20, yAxisID: "price" },
            { type: "line", label: "50일선", data: s.series.dma50, borderColor: stockPalette.dma50, yAxisID: "price" },
            { type: "bar", label: "거래량", data: s.series.volume, backgroundColor: "rgba(249, 115, 22, 0.16)", borderColor: "rgba(249, 115, 22, 0.22)", yAxisID: "volume", order: 2 },
            { type: "line", label: "20일 평균", data: s.series.volume_dma20, borderColor: stockPalette.volume, yAxisID: "volume", borderWidth: 1.2, pointRadius: 0, borderDash: [4, 4], order: 1 },
          ],
        },
        plugins: [createBackgroundPlugin(theme)],
        options: {
          responsive: true,
          maintainAspectRatio: true,
          layout: { padding: { left: 0, right: 0, top: 4, bottom: 0 } },
          scales: {
            x: {
              display: true,
              grid: { color: theme.grid },
              title: { display: false },
              ticks: {
                color: theme.ticks,
                autoSkip: true,
                maxTicksLimit: 6,
                maxRotation: 0,
                font: { size: 10 },
                callback(value, index) {
                  return formatChartLabel(s.series.dates[index]);
                },
              },
            },
            price: {
              type: "linear",
              position: "left",
              grid: { color: theme.grid },
              ticks: {
                color: theme.ticks,
                padding: 0,
                maxTicksLimit: 6,
                callback(value) {
                  return formatManAxisValue(value);
                },
              },
            },
            volume: {
              type: "linear",
              position: "right",
              grid: { drawOnChartArea: false },
              ticks: {
                color: theme.ticks,
                padding: 0,
                maxTicksLimit: 6,
                callback(value) {
                  return formatManAxisValue(value);
                },
              },
            },
          },
          elements: { line: { borderWidth: 1.8 }, point: { radius: 0 }, bar: { borderWidth: 0 } },
          plugins: { legend: { display: false } },
        },
      })
    );
    renderChartLegend(`stockLegend-${s.ticker}`, [
      { label: "현재가", color: stockPalette.close },
      { label: "5일선", color: stockPalette.dma5 },
      { label: "20일선", color: stockPalette.dma20 },
      { label: "50일선", color: stockPalette.dma50 },
      { label: "거래량", color: "rgba(249, 115, 22, 0.55)" },
      { label: "20일 평균", color: stockPalette.volume },
    ]);
  });
  bindFactorBoxes(holder);
}

function initStockPanel(stocks) {
  const panel = document.getElementById("stockPanel");
  if (!panel) return;
  const stateEl = panel.querySelector(".stock-panel-state");
  const syncState = () => {
    if (stateEl) stateEl.textContent = panel.open ? "닫힘" : "펼침";
  };
  const renderIfNeeded = () => {
    if (appState.stockRendered) return;
    renderStocks(stocks);
    appState.stockRendered = true;
    bindStockExtraInfo(document);
  };
  syncState();
  if (panel.open) renderIfNeeded();
  panel.addEventListener("toggle", () => {
    syncState();
    if (panel.open) renderIfNeeded();
  });
}

async function boot() {
  initThemeToggle();
  const response = await fetch("./data/latest_kr.json", { cache: "no-store" });
  if (!response.ok) throw new Error("Failed to load latest_kr.json");
  const data = await response.json();
  appState.data = data;
  renderMarket(data);
  renderTable(data.watchlist_summary);
  renderMarketCharts(data.charts.market);
  renderStressTable(data.charts.market);
  initStockPanel(data.stocks);
}

boot().catch((error) => {
  document.body.innerHTML = `<main class="container"><section class="panel"><h2>한국 시장 데이터를 아직 불러오지 못했습니다</h2><p>${escapeHtml(error.message)}</p></section></main>`;
});
