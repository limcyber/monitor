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
    bwButton.textContent = "DARK";
    bwButton.setAttribute("aria-label", "Switch to dark mode");
  }
  if (colorButton) {
    colorButton.textContent = "WHITE";
    colorButton.setAttribute("aria-label", "Switch to color mode");
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
  let saved = "finviz";
  try {
    saved = localStorage.getItem("monitorTheme") || "finviz";
  } catch {
    saved = "finviz";
  }
  applyTheme(saved);
  document.getElementById("themeBw")?.addEventListener("click", () => applyTheme("bw"));
  document.getElementById("themeColor")?.addEventListener("click", () => applyTheme("finviz"));
}

function renderMarket(data) {
  setText("generatedAt", `Generated At: ${data.generated_at_et}`);
  setText("asOf", `Market Data As Of: ${data.market_data_as_of}`);
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
  setText("marketEasy", data.market.easy_explanation);
  setText("marketInvalidation", data.market.invalidation);

  const reasonsEl = document.getElementById("marketReasons");
  reasonsEl.innerHTML = "";
  (data.market.top_reasons || []).forEach((r) => {
    const li = document.createElement("li");
    li.textContent = r;
    reasonsEl.appendChild(li);
  });
}

function renderTable(rows) {
  const body = document.getElementById("watchlistTable");
  body.innerHTML = "";
  rows.forEach((row) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${row.ticker}</td>
      <td><span class="pill ${scoreTone(row.stock_score)}">${formatScore(row.stock_score)}</span></td>
      <td><span class="pill ${scoreTone(row.stock_score)}">${row.stock_state}</span></td>
      <td><span class="pill ${scoreTone(row.stock_score)}">${row.final_action}</span></td>
      <td>${row.note}</td>
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
  return new Chart(ctx, {
    type: "line",
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      scales: {
        x: {
          display: true,
          grid: { color: theme.grid },
          title: {
            display: true,
            text: "Date",
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
      { label: "SPY", data: charts.spy_close, borderColor: palette.primary },
      { label: "20DMA", data: charts.spy_dma20, borderColor: palette.secondary },
      { label: "50DMA", data: charts.spy_dma50, borderColor: palette.warning },
      { label: "200DMA", data: charts.spy_dma200, borderColor: palette.danger },
    ])
  );
  appState.charts.push(
    lineChart(document.getElementById("breadthChart"), labels, [
      { label: "% Above 20DMA", data: charts.breadth_20, borderColor: palette.secondary },
      { label: "% Above 50DMA", data: charts.breadth_50, borderColor: palette.primary },
    ])
  );
  appState.charts.push(
    lineChart(document.getElementById("stressChart"), labels, [
      { label: "VIX", data: charts.vix_close, borderColor: palette.danger },
      { label: "HYG", data: charts.hyg_close, borderColor: palette.secondary },
      { label: "DXY", data: charts.dxy_close, borderColor: palette.warning },
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
      <p style="margin:6px 0;color:${scoreColor(s.stock_score)};"><strong>Score:</strong> ${formatScore(s.stock_score)} | <strong>Action:</strong> ${s.final_action}</p>
      <div class="mini-meta">
        <span>Event: ${s.event_flag}</span>
        <span>Close: ${s.metrics.close.toFixed(2)}</span>
      </div>
      <p>${s.easy_explanation}</p>
      <ul>${(s.top_reasons || []).map((r) => `<li>${r}</li>`).join("")}</ul>
      <div class="chart-head stock-chart-head">
        <h4>Price Chart</h4>
        <p>Close, 20DMA, 50DMA</p>
      </div>
      <canvas id="chart-${s.ticker}" class="stock-chart"></canvas>
    `;
    holder.appendChild(card);
    lineChart(document.getElementById(`chart-${s.ticker}`), s.series.dates, [
      { label: `${s.ticker} Close`, data: s.series.close, borderColor: seriesPalette().primary },
      { label: "20DMA", data: s.series.dma20, borderColor: seriesPalette().secondary },
      { label: "50DMA", data: s.series.dma50, borderColor: seriesPalette().warning },
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
    warning.textContent = "Chart library failed to load. Text data is shown without charts.";
    document.querySelector(".hero")?.appendChild(warning);
  }
}

boot().catch((error) => {
  document.body.innerHTML = `<main class="container"><section class="panel"><h2>Data not ready</h2><p>${error.message}</p></section></main>`;
});
