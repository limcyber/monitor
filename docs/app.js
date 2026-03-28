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
  renderList(document.getElementById("marketPositiveFactors"), data.market.positive_factors, "뚜렷한 가산 요인이 많지 않습니다.");
  renderList(document.getElementById("marketNegativeFactors"), data.market.negative_factors, "큰 감점 요인은 없습니다.");

  const topbarMeta = document.querySelector(".site-topbar-time");
  if (topbarMeta) {
    topbarMeta.classList.remove("tone-success", "tone-warning", "tone-danger");
    topbarMeta.classList.add(marketTone(data.market.score));
  }
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
      <td data-label="메모">${row.note}</td>
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
    primary: "#203757",
    secondary: "#0f7b6c",
    warning: "#b47f00",
    danger: "#b94343",
    neutral: "#526171",
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

function lineChart(ctx, labels, datasets) {
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
      scales: {
        x: {
          display: true,
          grid: { color: theme.grid },
          title: {
            display: true,
            text: "날짜",
            color: theme.ticks,
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
          ticks: { color: theme.ticks },
        },
      },
      elements: { line: { borderWidth: 1.8 }, point: { radius: 0 } },
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

function destroyCharts() {
  appState.charts.forEach((chart) => chart?.destroy?.());
  appState.charts = [];
}

function renderMarketCharts(charts) {
  destroyCharts();
  const palette = seriesPalette();
  const labels = charts.dates;
  appState.charts.push(
    lineChart(document.getElementById("spyChart"), labels, [
      { label: "S&P500", data: charts.spx_close, borderColor: palette.primary },
      { label: "S&P500 200일선", data: charts.spx_dma200, borderColor: palette.warning },
      { label: "NASDAQ", data: charts.ndx_close, borderColor: palette.secondary },
      { label: "NASDAQ 200일선", data: charts.ndx_dma200, borderColor: palette.danger },
    ])
  );
  appState.charts.push(
    lineChart(document.getElementById("breadthChart"), labels, [
      { label: "20일선 위 종목 비율", data: charts.breadth_20, borderColor: palette.secondary },
      { label: "50일선 위 종목 비율", data: charts.breadth_50, borderColor: palette.primary },
    ])
  );
  appState.charts.push(
    lineChart(document.getElementById("stressChart"), labels, [
      { label: "VIX", data: charts.vix_close, borderColor: palette.danger },
      { label: "HYG", data: charts.hyg_close, borderColor: palette.secondary },
      { label: "10Y", data: charts.tnx_close, borderColor: palette.neutral },
      { label: "달러지수", data: charts.dxy_close, borderColor: palette.warning },
    ])
  );
}

function renderStocks(stocks) {
  const holder = document.getElementById("stockCards");
  holder.innerHTML = "";
  stocks.forEach((s) => {
    const card = document.createElement("article");
    card.className = "stock-card";
    card.innerHTML = `
      <div class="stock-top">
        <h3>${s.ticker}</h3>
        <span class="pill ${scoreTone(s.stock_score)}">${s.stock_state}</span>
      </div>
      <p style="margin:6px 0;color:${scoreColor(s.stock_score)};"><strong>점수:</strong> ${formatScore(s.stock_score)} | <strong>추천 행동:</strong> ${s.final_action}</p>
      <div class="mini-meta">
        <span>일정: ${s.event_flag}</span>
        <span>종가: ${formatClose(s.metrics.close, s.metrics.close_change_pct)}</span>
      </div>
      <div class="cross-highlight-block stock-cross-highlight">
        <h4>크로스 신호</h4>
        <ul>${(s.cross_highlights?.length ? s.cross_highlights : ["최근 눈에 띄는 골든크로스나 데드크로스는 없습니다."]).map((r) => `<li>${r}</li>`).join("")}</ul>
      </div>
      <p>${s.easy_explanation}</p>
      <ul>${(s.top_reasons || []).map((r) => `<li>${r}</li>`).join("")}</ul>
      <details class="extra-info-box stock-extra-info">
        <summary>추가 정보</summary>
        <div class="factor-grid stock-factor-grid">
          <details class="factor-box factor-box-positive">
            <summary>점수를 올린 항목</summary>
            <ul>${(s.positive_factors?.length ? s.positive_factors : ["뚜렷한 가산 요인이 많지 않습니다."]).map((r) => `<li>${r}</li>`).join("")}</ul>
          </details>
          <details class="factor-box factor-box-negative">
            <summary>점수를 깎았거나 불리한 항목</summary>
            <ul>${(s.negative_factors?.length ? s.negative_factors : ["큰 감점 요인은 없습니다."]).map((r) => `<li>${r}</li>`).join("")}</ul>
          </details>
        </div>
        <div class="tag-row compact-tag-row">
          <h4>변화/히스토리</h4>
          <div class="tag-list">${(s.change_tags?.length ? s.change_tags : ["오늘 변화 없음"]).concat(s.history_tags?.length ? s.history_tags : []).map((r) => `<span class="mini-tag ${tagTone(r)}">${escapeHtml(r)}</span>`).join("")}</div>
        </div>
        <div class="tag-row compact-tag-row">
          <h4>운용/알림</h4>
          <div class="tag-list">${(s.position_tags?.length ? s.position_tags : ["기본 운용"]).concat(s.alerts?.length ? s.alerts : []).map((r) => `<span class="mini-tag ${tagTone(r)}">${escapeHtml(r)}</span>`).join("")}</div>
        </div>
        <div class="tag-row compact-tag-row">
          <h4>주의</h4>
          <div class="tag-list">${(s.confidence_warnings?.length ? s.confidence_warnings : ["데이터 경고 없음"]).map((r) => `<span class="mini-tag ${tagTone(r)}">${escapeHtml(r)}</span>`).join("")}</div>
        </div>
      </details>
      <div class="chart-head stock-chart-head">
        <h4>가격 차트</h4>
        <p>종가, 20일선, 50일선</p>
      </div>
      <canvas id="chart-${s.ticker}" class="stock-chart"></canvas>
    `;
    holder.appendChild(card);
    lineChart(document.getElementById(`chart-${s.ticker}`), s.series.dates, [
      { label: `${s.ticker} 종가`, data: s.series.close, borderColor: seriesPalette().primary },
      { label: "20일선", data: s.series.dma20, borderColor: seriesPalette().secondary },
      { label: "50일선", data: s.series.dma50, borderColor: seriesPalette().warning },
    ]);
  });
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
