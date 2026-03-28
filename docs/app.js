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
  const pct = formatPercent(changePct);
  return `${value.toFixed(2)} (${pct})`;
}

function quoteTone(changePct, invert = false) {
  if (typeof changePct !== "number" || Number.isNaN(changePct)) return "warning";
  if (changePct === 0) return "warning";
  const positive = invert ? changePct < 0 : changePct > 0;
  return positive ? "success" : "danger";
}

function renderQuote(id, labelValue, changePct, invert = false) {
  const el = document.getElementById(id);
  if (!el) return;
  const tone = quoteTone(changePct, invert);
  el.className = `quote-value ${tone}`;
  el.textContent = formatClose(Number(labelValue), changePct);
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
  if (value.includes("경고") || value.includes("주의") || value.includes("데드") || value.includes("약함") || value.includes("자제") || value.includes("보수") || value.includes("고스트레스") || value.includes("실적")) {
    return "danger";
  }
  if (value.includes("강함") || value.includes("골든") || value.includes("상위") || value.includes("좋음")) {
    return "success";
  }
  return "warning";
}

function renderTagList(el, items, fallback) {
  if (!el) return;
  const rows = items && items.length ? items : [fallback];
  el.innerHTML = rows
    .map((item) => `<span class="mini-tag ${tagTone(item)}">${escapeHtml(item)}</span>`)
    .join("");
}

function renderSectorTagList(el, items, fallback) {
  if (!el) return;
  const rows = items && items.length ? items : [];
  if (!rows.length) {
    renderTagList(el, [fallback], fallback);
    return;
  }
  el.innerHTML = rows
    .map((item) => {
      const tone = item.status === "강함" ? "success" : item.status === "약함" ? "danger" : "warning";
      return `<span class="mini-tag ${tone}">${escapeHtml(item.name)} ${escapeHtml(item.status)} ${escapeHtml(formatPercent(item.change_pct))}</span>`;
    })
    .join("");
}

const appState = {
  data: null,
  charts: [],
};

function applyTheme(theme) {
  const normalized = theme === "bw" ? "bw" : "finviz";
  document.body.dataset.theme = normalized === "bw" ? "bw" : "";
  const isBw = normalized === "bw";
  const bwButton = document.getElementById("themeBw");
  const colorButton = document.getElementById("themeColor");
  if (bwButton) {
    bwButton.textContent = "어둡게";
    bwButton.setAttribute("aria-label", "어두운 화면으로 바꾸기");
  }
  if (colorButton) {
    colorButton.textContent = "밝게";
    colorButton.setAttribute("aria-label", "밝은 화면으로 바꾸기");
  }
  if (bwButton) bwButton.setAttribute("aria-pressed", String(isBw));
  if (colorButton) colorButton.setAttribute("aria-pressed", String(!isBw));
  try {
    localStorage.setItem("monitorTheme", normalized);
  } catch {
    // Ignore storage failures in restrictive browser modes.
  }
  if (appState.data) {
    renderMarketCharts(appState.data.charts.market);
  }
}

function initThemeToggle() {
  let saved = "bw";
  try {
    saved = localStorage.getItem("monitorTheme");
  } catch {
    saved = null;
  }
  if (saved !== "bw" && saved !== "finviz") {
    saved = "bw";
  }
  applyTheme(saved || "bw");
  document.getElementById("themeBw")?.addEventListener("click", () => applyTheme("bw"));
  document.getElementById("themeColor")?.addEventListener("click", () => applyTheme("finviz"));
}

function syncFactorBoxPair(grid) {
  const boxes = Array.from(grid.querySelectorAll(".factor-box"));
  if (boxes.length !== 2) return;
  if (grid.dataset.synced === "true") return;
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

function limitTags(items, max = 2) {
  if (!items || !items.length) return [];
  return items.slice(0, max);
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
  const scoreEl = document.getElementById("marketScore");
  if (scoreEl) {
    scoreEl.textContent = formatScore(data.market.score);
    scoreEl.className = `market-value ${marketTone(data.market.score)}`;
  }
  const confidenceEl = document.getElementById("marketConfidence");
  if (confidenceEl) {
    confidenceEl.textContent = data.market.confidence;
    confidenceEl.className = `market-value ${marketTone(data.market.score)}`;
  }
  const executionEl = document.getElementById("marketExecution");
  if (executionEl) {
    executionEl.textContent = data.market.execution_strength;
    executionEl.className = `market-value ${marketTone(data.market.score)}`;
  }
  const actionEl = document.getElementById("marketAction");
  if (actionEl) {
    actionEl.textContent = data.market.action;
    actionEl.className = `market-value ${marketTone(data.market.score)}`;
  }
  renderQuote("marketSpyQuote", data.market.metrics.spx_close.toFixed(2), data.market.metrics.spx_change_pct);
  renderQuote("marketQqqQuote", data.market.metrics.ndx_close.toFixed(2), data.market.metrics.ndx_change_pct);
  renderQuote("marketRutQuote", data.market.metrics.rut_close.toFixed(2), data.market.metrics.rut_change_pct);
  renderQuote("marketVixQuote", data.market.metrics.vix_close.toFixed(2), data.market.metrics.vix_change_pct, true);
  renderQuote("marketTnxQuote", data.market.metrics.tnx_close.toFixed(2), data.market.metrics.tnx_change_pct, true);
  renderTagList(document.getElementById("marketChangeTags"), data.market.change_tags, "오늘 변화 없음");
  renderTagList(document.getElementById("marketPositionTags"), data.market.position_tags, "기본 운용");
  renderTagList(document.getElementById("marketAlertTags"), data.market.alerts, "오늘 별도 알림 없음");
  renderTagList(document.getElementById("marketWarningTags"), data.market.confidence_warnings, "데이터 경고 없음");
  renderSectorTagList(document.getElementById("marketSectorTags"), data.market.sector_tags, "섹터 데이터 없음");
  renderTagList(document.getElementById("marketHistoryTags"), data.market.history_tags, "히스토리 없음");
  renderList(document.getElementById("marketCrossHighlights"), data.market.cross_highlights, "최근 눈에 띄는 골든크로스나 데드크로스는 없습니다.");
  setText("marketEasy", data.market.easy_explanation);
  setText("marketInvalidation", data.market.invalidation);

  const reasonsEl = document.getElementById("marketReasons");
  renderList(reasonsEl, data.market.top_reasons, "뚜렷하게 좋은 신호가 많지 않습니다.");
  renderList(document.getElementById("marketPositiveFactors"), data.market.positive_factors, "점수를 올려준 신호가 많지 않습니다.");
  renderList(document.getElementById("marketNegativeFactors"), data.market.negative_factors, "크게 나쁜 신호는 없습니다.");

  const topbarMeta = document.querySelector(".site-topbar-time");
  if (topbarMeta) {
    topbarMeta.classList.remove("tone-success", "tone-warning", "tone-danger");
    topbarMeta.classList.add(marketTone(data.market.score));
  }
  bindFactorBoxes(document);
}

function renderTable(rows) {
  const body = document.getElementById("watchlistTable");
  body.innerHTML = "";
  rows.forEach((row) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td data-label="종목">${row.ticker}</td>
      <td data-label="점수"><span class="pill ${scoreTone(row.stock_score)}">${formatScore(row.stock_score)}</span></td>
      <td data-label="상태"><span class="pill ${scoreTone(row.stock_score)}">${row.stock_state}</span></td>
      <td data-label="추천 행동"><span class="pill ${scoreTone(row.stock_score)}">${row.final_action}</span></td>
    `;
    body.appendChild(tr);
  });
}

function chartTheme() {
  const isBw = document.body.dataset.theme === "bw";
  return isBw
    ? { bg: "#090b0c", grid: "#233027", ticks: "#8fb08d", legend: "#c8f0c2" }
    : { bg: "#ffffff", grid: "#d5dde5", ticks: "#526171", legend: "#22324a" };
}

function seriesPalette() {
  if (document.body.dataset.theme === "bw") {
    return {
      primary: "#76f08d",
      secondary: "#9fe9a7",
      warning: "#d7c46a",
      danger: "#ff7b7b",
      neutral: "#bfd0be",
    };
  }
  return {
    primary: "#2563eb",
    secondary: "#0f766e",
    warning: "#d97706",
    danger: "#dc2626",
    neutral: "#6b7280",
  };
}

function stockSeriesPalette() {
  if (document.body.dataset.theme === "bw") {
    return {
      close: "#76f08d",
      dma5: "#ff7b7b",
      dma20: "#7dd3fc",
      dma50: "#d7c46a",
      volume: "#f4a261",
    };
  }
  return {
    close: "#2563eb",
    dma5: "#ef4444",
    dma20: "#0f766e",
    dma50: "#f59e0b",
    volume: "#f97316",
  };
}

function formatChartLabel(label) {
  if (typeof label !== "string") return label;
  const parts = label.split("-");
  if (parts.length === 3) {
    return `${parts[1]}/${parts[2]}`;
  }
  return label;
}

function formatAxisValue(value) {
  const num = typeof value === "number" ? value : Number(value);
  if (Number.isNaN(num)) return value;
  const abs = Math.abs(num);
  if (abs >= 1_000_000) {
    return `${(num / 1_000_000).toFixed(1)}M`;
  }
  if (abs >= 1_000) {
    return `${(num / 1_000).toFixed(1)}K`;
  }
  if (abs >= 100) {
    return `${Math.round(num)}`;
  }
  return `${num.toFixed(1)}`;
}

function lineChart(ctx, labels, datasets, config = {}) {
  if (!window.Chart || !ctx) return null;
  const theme = chartTheme();
  const backgroundPlugin = {
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
  return new Chart(ctx, {
    type: "line",
    data: { labels, datasets },
    plugins: [backgroundPlugin],
    options: {
      responsive: true,
      maintainAspectRatio: true,
      layout: {
        padding: { left: 8, right: 8, top: 4, bottom: 0 },
      },
      scales: {
        x: {
          display: true,
          grid: { color: theme.grid },
          title: {
            display: false,
          },
          ticks: {
            color: theme.ticks,
            autoSkip: true,
            maxTicksLimit: 6,
            maxRotation: 0,
            callback(value, index, ticks) {
              const raw = labels[index] ?? ticks?.[value]?.label;
              return formatChartLabel(raw);
            },
          },
        },
        y: {
          grid: { color: theme.grid },
          ticks: {
            color: theme.ticks,
            maxTicksLimit: 6,
            callback(value) {
              return formatAxisValue(value);
            },
          },
        },
      },
      elements: { line: { borderWidth: 1.8 }, point: { radius: 0 } },
      plugins: {
        legend: {
          display: config.showLegend !== false,
          position: "bottom",
          labels: { color: theme.legend, boxWidth: 10 },
        },
      },
    },
  });
}

function barChart(ctx, labels, datasets) {
  if (!window.Chart || !ctx) return null;
  const theme = chartTheme();
  const backgroundPlugin = {
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
  return new Chart(ctx, {
    type: "bar",
    data: { labels, datasets },
    plugins: [backgroundPlugin],
    options: {
      responsive: true,
      maintainAspectRatio: true,
      layout: {
        padding: { left: 8, right: 8, top: 4, bottom: 0 },
      },
      scales: {
        x: {
          display: true,
          grid: { color: theme.grid },
          title: {
            display: false,
          },
          ticks: {
            color: theme.ticks,
            autoSkip: true,
            maxTicksLimit: 6,
            maxRotation: 0,
            callback(value, index, ticks) {
              const raw = labels[index] ?? ticks?.[value]?.label;
              return formatChartLabel(raw);
            },
          },
        },
        y: {
          grid: { color: theme.grid },
          ticks: {
            color: theme.ticks,
            maxTicksLimit: 6,
            callback(value) {
              return formatAxisValue(value);
            },
          },
        },
      },
      elements: { bar: { borderWidth: 0 }, line: { borderWidth: 1.8 }, point: { radius: 0 } },
      plugins: {
        legend: {
          display: true,
          position: "bottom",
          labels: { color: theme.legend, boxWidth: 10 },
        },
      },
    },
  });
}

function renderChartLegend(targetId, items) {
  const el = document.getElementById(targetId);
  if (!el) return;
  el.innerHTML = items
    .map(
      (item) => `
        <span class="chart-legend-item">
          <span class="chart-legend-swatch" style="background:${item.color}"></span>
          <span>${escapeHtml(item.label)}</span>
        </span>
      `
    )
    .join("");
}

function destroyCharts() {
  appState.charts.forEach((chart) => chart?.destroy?.());
  appState.charts = [];
}

function renderMarketCharts(charts) {
  destroyCharts();
  const palette = {
    primary: "#2563eb",
    secondary: "#0f766e",
    warning: "#f59e0b",
    danger: "#ef4444",
    neutral: "#6b7280",
  };
  const labels = charts.dates;
  appState.charts.push(
    lineChart(
      document.getElementById("spyChart"),
      labels,
      [
      { label: "S&P500", data: charts.spx_close, borderColor: palette.primary },
      { label: "S&P500 200일선", data: charts.spx_dma200, borderColor: palette.warning },
      { label: "NASDAQ", data: charts.ndx_close, borderColor: palette.secondary },
      { label: "NASDAQ 200일선", data: charts.ndx_dma200, borderColor: palette.danger },
      ],
      { showLegend: false }
    )
  );
  renderChartLegend("spyLegend", [
    { label: "S&P500", color: palette.primary },
    { label: "S&P500 200일선", color: palette.warning },
    { label: "NASDAQ", color: palette.secondary },
    { label: "NASDAQ 200일선", color: palette.danger },
  ]);
  appState.charts.push(
    lineChart(
      document.getElementById("breadthChart"),
      labels,
      [
      { label: "20일선 위 종목 비율", data: charts.breadth_20, borderColor: palette.secondary },
      { label: "50일선 위 종목 비율", data: charts.breadth_50, borderColor: palette.primary },
      ],
      { showLegend: false }
    )
  );
  renderChartLegend("breadthLegend", [
    { label: "20일선 위 종목 비율", color: palette.secondary },
    { label: "50일선 위 종목 비율", color: palette.primary },
  ]);
  appState.charts.push(
    lineChart(
      document.getElementById("stressChart"),
      labels,
      [
      { label: "VIX", data: charts.vix_close, borderColor: palette.danger },
      { label: "HYG", data: charts.hyg_close, borderColor: palette.secondary },
      { label: "10Y", data: charts.tnx_close, borderColor: palette.neutral },
      { label: "달러지수", data: charts.dxy_close, borderColor: palette.warning },
      ],
      { showLegend: false }
    )
  );
  renderChartLegend("stressLegend", [
    { label: "VIX", color: palette.danger },
    { label: "HYG", color: palette.secondary },
    { label: "10Y", color: palette.neutral },
    { label: "달러지수", color: palette.warning },
  ]);
}

function renderStocks(stocks) {
  const holder = document.getElementById("stockCards");
  holder.innerHTML = "";
  stocks.forEach((s) => {
    const stockPalette = stockSeriesPalette();
    const changeAndHistory = limitTags((s.change_tags?.length ? s.change_tags : ["오늘 변화 없음"]).concat(s.history_tags?.length ? s.history_tags : []));
    const positionAndAlerts = limitTags((s.position_tags?.length ? s.position_tags : ["기본 운용"]).concat(s.alerts?.length ? s.alerts : []));
    const warningTags = limitTags(s.confidence_warnings?.length ? s.confidence_warnings : ["데이터 경고 없음"]);
    const card = document.createElement("article");
    card.className = "stock-card";
    card.innerHTML = `
      <div class="stock-top">
        <h3>${s.ticker}</h3>
        <span class="pill ${scoreTone(s.stock_score)}">${s.stock_state}</span>
      </div>
      <p style="margin:6px 0;color:${scoreColor(s.stock_score)};"><strong>점수:</strong> ${formatScore(s.stock_score)} | <strong>추천 행동:</strong> ${s.final_action}</p>
      <div class="mini-meta">
        <span>실적발표일: ${s.earnings_date_label || "미확인"}</span>
        <span>현재가: ${formatClose(s.metrics.close, s.metrics.close_change_pct)}</span>
      </div>
      <div class="cross-highlight-block stock-cross-highlight">
        <h4>크로스 신호</h4>
        <ul>${(s.cross_highlights?.length ? s.cross_highlights : ["최근 눈에 띄는 골든크로스나 데드크로스는 없습니다."]).map((r) => `<li>${r}</li>`).join("")}</ul>
      </div>
      <details class="extra-info-box stock-extra-info">
        <summary>설명과 세부 정보</summary>
        <div class="stock-summary-copy">
          <p>${s.easy_explanation}</p>
          <ul>${(s.top_reasons || []).map((r) => `<li>${r}</li>`).join("")}</ul>
        </div>
        <div class="factor-grid stock-factor-grid">
          <details class="factor-box factor-box-positive">
            <summary>점수를 올린 항목</summary>
            <ul>${(s.positive_factors?.length ? s.positive_factors : ["점수를 올려준 신호가 많지 않습니다."]).map((r) => `<li>${r}</li>`).join("")}</ul>
          </details>
          <details class="factor-box factor-box-negative">
            <summary>점수를 깎았거나 불리한 항목</summary>
            <ul>${(s.negative_factors?.length ? s.negative_factors : ["크게 나쁜 신호는 없습니다."]).map((r) => `<li>${r}</li>`).join("")}</ul>
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
    if (window.Chart && ctx) {
      const theme = chartTheme();
      const backgroundPlugin = {
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
        plugins: [backgroundPlugin],
        options: {
          responsive: true,
          maintainAspectRatio: true,
          layout: { padding: { left: 8, right: 8, top: 4, bottom: 0 } },
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
                callback(value, index, ticks) {
                  const raw = s.series.dates[index] ?? ticks?.[value]?.label;
                  return formatChartLabel(raw);
                },
              },
            },
            price: {
              type: "linear",
              position: "left",
              grid: { color: theme.grid },
              ticks: {
                color: theme.ticks,
                maxTicksLimit: 6,
                callback(value) {
                  return formatAxisValue(value);
                },
              },
            },
            volume: {
              type: "linear",
              position: "right",
              grid: { drawOnChartArea: false },
              ticks: {
                color: theme.ticks,
                maxTicksLimit: 6,
                callback(value) {
                  return formatAxisValue(value);
                },
              },
            },
          },
          elements: { line: { borderWidth: 1.8 }, point: { radius: 0 }, bar: { borderWidth: 0 } },
          plugins: {
            legend: {
              display: false,
            },
          },
        },
      });
      renderChartLegend(`stockLegend-${s.ticker}`, [
        { label: "현재가", color: stockPalette.close },
        { label: "5일선", color: stockPalette.dma5 },
        { label: "20일선", color: stockPalette.dma20 },
        { label: "50일선", color: stockPalette.dma50 },
        { label: "거래량", color: "rgba(249, 115, 22, 0.55)" },
        { label: "20일 평균", color: stockPalette.volume },
      ]);
    }
  });
  bindFactorBoxes(holder);
}

async function boot() {
  initThemeToggle();
  const response = await fetch("./data/latest.json", { cache: "no-store" });
  if (!response.ok) throw new Error("Failed to load latest.json");
  const data = await response.json();
  appState.data = data;
  renderMarket(data);
  renderTable(data.watchlist_summary);
  renderMarketCharts(data.charts.market);
  renderStocks(data.stocks);
  bindStockExtraInfo(document);
  if (!window.Chart) {
    const warning = document.createElement("p");
    warning.style.color = "#b47f00";
    warning.textContent = "차트 라이브러리를 불러오지 못해서 글자 정보만 보여주고 있습니다.";
    document.querySelector(".hero")?.appendChild(warning);
  }
}

boot().catch((error) => {
  document.body.innerHTML = `<main class="container"><section class="panel"><h2>데이터를 아직 불러오지 못했습니다</h2><p>${error.message}</p></section></main>`;
});
