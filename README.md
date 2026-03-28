# Simple Market Regime Monitor

Market-first investment decision assistant with a fixed 5-stock watchlist.
Repository: `limcyber/monitor`
Live site: https://limcyber.github.io/monitor/

## What this project does

- Scores the overall market (0-100) using trend, breadth, stress, and execution factors.
- Applies market negative filters (breadth divergence, big-cap concentration, stress cap, event risk).
- Scores 5 predefined watchlist stocks with the same daily timestamp.
- Combines market state + stock state into final action guidance.
- Publishes a daily dashboard to GitHub Pages.

## Stack

- Data + scoring: Python (`pandas`, `numpy`, `yfinance`)
- Automation: GitHub Actions
- UI: Static HTML/CSS/JS + Chart.js on GitHub Pages

## Project structure

```text
config/
  watchlist.yml
  economic_calendar.yml
scripts/
  generate_report.py
docs/
  index.html
  app.js
  styles.css
  data/latest.json
.github/workflows/
  daily-monitor.yml
```

## Configure

1. Edit `config/watchlist.yml` with exactly 5 tickers.
2. Update `config/economic_calendar.yml` for FOMC/CPI/NFP dates.
3. Enable GitHub Pages:
   - Repository Settings > Pages > Source: GitHub Actions.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/generate_report.py
```

The report JSON is generated at `docs/data/latest.json`.

## GitHub Actions schedule

- Runs every weekday at `21:20 UTC` (after US market close).
- Also supports manual run via `workflow_dispatch`.

## Notes

- This is an analysis and monitoring tool, not financial advice.
- Event dates are configured manually for transparency and control.
