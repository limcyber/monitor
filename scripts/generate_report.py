from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from io import StringIO
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests
import yaml
import yfinance as yf

BASE_DIR = Path(__file__).resolve().parents[1]
DOCS_DATA_DIR = BASE_DIR / "docs" / "data"
WATCHLIST_PATH = BASE_DIR / "config" / "watchlist.yml"
CALENDAR_PATH = BASE_DIR / "config" / "economic_calendar.yml"
OUTPUT_PATH = DOCS_DATA_DIR / "latest.json"
ET = ZoneInfo("America/New_York")


@dataclass
class ScoreResult:
    score: int
    state: str
    action: str
    reasons: list[str]
    invalidation: str
    easy_explanation: str


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def to_date_list(values: list[str]) -> list[date]:
    result = []
    for value in values:
        result.append(datetime.strptime(value, "%Y-%m-%d").date())
    return result


def third_friday(any_day: date) -> date:
    first = any_day.replace(day=1)
    days_to_friday = (4 - first.weekday()) % 7
    first_friday = first + timedelta(days=days_to_friday)
    return first_friday + timedelta(days=14)


def load_events(as_of: date) -> dict:
    calendar = load_yaml(CALENDAR_PATH)
    op_ex = third_friday(as_of)
    return {
        "fomc": to_date_list(calendar.get("fomc", [])),
        "cpi": to_date_list(calendar.get("cpi", [])),
        "nfp": to_date_list(calendar.get("nfp", [])),
        "opex": [op_ex],
    }


def is_event_d0_d1(as_of: date, events: dict) -> tuple[bool, list[str]]:
    names = []
    for key, dates in events.items():
        for d in dates:
            if d in {as_of, as_of + timedelta(days=1)}:
                names.append(key.upper())
                break
    return (len(names) > 0, names)


def slope_up(series: pd.Series, lookback: int = 20) -> bool:
    series = series.dropna()
    if len(series) < lookback:
        return False
    y = series.iloc[-lookback:].values
    x = np.arange(len(y))
    m, _ = np.polyfit(x, y, 1)
    return bool(m > 0)


def zscore(series: pd.Series, lookback: int = 20) -> float:
    series = series.dropna()
    if len(series) < lookback:
        return 0.0
    window = series.iloc[-lookback:]
    std = window.std(ddof=0)
    if std == 0 or math.isnan(std):
        return 0.0
    return float((window.iloc[-1] - window.mean()) / std)


def percentile_rank(series: pd.Series, lookback: int = 252) -> float:
    series = series.dropna()
    if len(series) < 30:
        return 50.0
    window = series.iloc[-lookback:] if len(series) >= lookback else series
    last = window.iloc[-1]
    return float((window <= last).mean() * 100.0)


def download_ohlcv(ticker: str, period: str = "1y") -> pd.DataFrame:
    df = yf.download(ticker, period=period, interval="1d", progress=False, auto_adjust=False, threads=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [col[0] for col in df.columns]
    df = df.dropna(subset=["Close"])
    return df


def download_sp500_prices(period: str = "1y") -> pd.DataFrame:
    tickers: list[str] = []
    wiki_url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    try:
        resp = requests.get(wiki_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        resp.raise_for_status()
        tables = pd.read_html(StringIO(resp.text))
        tickers = tables[0]["Symbol"].astype(str).str.replace(".", "-", regex=False).tolist()
    except Exception:
        tickers = [
            "AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "GOOG", "BRK-B", "TSLA", "JPM",
            "AVGO", "UNH", "XOM", "V", "MA", "LLY", "COST", "PG", "HD", "MRK",
            "ABBV", "PEP", "KO", "ADBE", "NFLX", "AMD", "CSCO", "CRM", "WMT", "BAC",
            "CVX", "MCD", "ACN", "TMO", "INTU", "ABT", "LIN", "ORCL", "CMCSA", "DHR",
            "QCOM", "NKE", "WFC", "AMGN", "TXN", "PM", "MS", "INTC", "AMAT", "IBM",
            "GE", "CAT", "GS", "RTX", "SPGI", "BLK", "SYK", "NOW", "BA", "BKNG",
            "LOW", "PLD", "MDT", "SCHW", "ELV", "MU", "LRCX", "DE", "ADP", "T",
            "GILD", "PGR", "MMC", "CB", "TJX", "PANW", "VRTX", "UPS", "AXP", "ISRG",
            "SBUX", "C", "CI", "AMT", "MO", "MDLZ", "ADI", "ZTS", "DUK", "SO",
            "PYPL", "ETN", "NEE", "REGN", "SHW", "BDX", "APD", "HUM", "EOG", "COP",
        ]
    prices = yf.download(
        tickers,
        period=period,
        interval="1d",
        progress=False,
        auto_adjust=False,
        threads=True,
    )
    close = prices["Close"] if isinstance(prices.columns, pd.MultiIndex) else prices
    return close


def market_level(score: int) -> int:
    if score >= 85:
        return 6
    if score >= 70:
        return 5
    if score >= 55:
        return 4
    if score >= 40:
        return 3
    if score >= 25:
        return 2
    return 1


def market_state_name(level: int) -> str:
    return {
        6: "Strong Risk-On",
        5: "Risk-On",
        4: "Improving / Recovery",
        3: "Neutral / Mixed",
        2: "Weakening / Caution",
        1: "Risk-Off / Defensive",
    }[level]


def market_action(level: int) -> str:
    return {
        6: "Buy / Strong Hold",
        5: "Buy / Hold",
        4: "Small Buy / Hold",
        3: "Hold / Reduce",
        2: "Reduce",
        1: "Exit / Defensive Hold",
    }[level]


def stock_state(score: int) -> str:
    if score >= 80:
        return "Strong"
    if score >= 65:
        return "Good"
    if score >= 50:
        return "Mixed"
    if score >= 35:
        return "Weak"
    return "Avoid"


def combined_action(market_lvl: int, s_state: str) -> str:
    if market_lvl >= 5:
        if s_state == "Strong":
            return "Buy"
        if s_state == "Good":
            return "Selective Buy"
        return "Hold / Watch"
    if market_lvl == 4:
        if s_state == "Strong":
            return "Small Buy"
        if s_state == "Good":
            return "Very Selective"
        return "Watch"
    if s_state == "Strong":
        return "Tiny Position / Wait"
    return "Avoid / Reduce"


def confidence_from_coverage(total_metrics: int, valid_metrics: int) -> str:
    ratio = valid_metrics / max(total_metrics, 1)
    if ratio >= 0.85:
        return "High"
    if ratio >= 0.65:
        return "Medium"
    return "Low"


def score_market(as_of: date, market_data: dict, breadth: dict, events: dict) -> ScoreResult:
    score = 0
    reasons = []
    valid_count = 0
    total_count = 12

    spy = market_data["SPY"]
    rsp = market_data["RSP"]
    hyg = market_data["HYG"]
    dxy = market_data["DXY"]
    vix = market_data["VIX"]

    close = spy["Close"]
    volume = spy["Volume"]
    dma20 = close.rolling(20).mean()
    dma50 = close.rolling(50).mean()
    dma200 = close.rolling(200).mean()

    if close.iloc[-1] > dma200.iloc[-1]:
        score += 15
        reasons.append("SPY is above 200DMA")
    valid_count += 1
    if dma50.iloc[-1] > dma200.iloc[-1]:
        score += 10
        reasons.append("50DMA is above 200DMA")
    valid_count += 1
    if slope_up(dma20):
        score += 10
        reasons.append("20DMA slope is positive")
    valid_count += 1
    if close.iloc[-1] > dma20.iloc[-1]:
        score += 5
    valid_count += 1

    if breadth["pct_above_20dma"] > 55:
        score += 10
        reasons.append("Breadth above 20DMA is healthy")
    valid_count += 1
    if breadth["pct_above_50dma"] > 50:
        score += 10
    valid_count += 1
    if breadth["adline_5d_up"]:
        score += 5
    valid_count += 1
    if breadth["rsp_spy_ratio_20d_up_or_flat"]:
        score += 5
    valid_count += 1

    vix_pct = percentile_rank(vix["Close"])
    if vix_pct < 60:
        score += 10
    valid_count += 1
    hyg_dma50 = hyg["Close"].rolling(50).mean()
    if hyg["Close"].iloc[-1] > hyg_dma50.iloc[-1]:
        score += 5
    valid_count += 1
    dxy_z = zscore(dxy["Close"], 20)
    if dxy_z <= 1.0:
        score += 5
    valid_count += 1

    spy_vol20 = volume.rolling(20).mean()
    if close.iloc[-1] > dma20.iloc[-1] and volume.iloc[-1] > spy_vol20.iloc[-1]:
        score += 5
    valid_count += 1
    event_risk, event_names = is_event_d0_d1(as_of, events)
    if not event_risk:
        score += 5

    invalidation = "SPY loses 50DMA with breadth deterioration."
    if event_risk:
        invalidation = f"Event risk near term ({', '.join(event_names)}); reduce aggressiveness."

    if close.iloc[-1] > close.iloc[-2] and (not breadth["adline_5d_up"] or breadth["pct_above_20dma_change"] < 0):
        score -= 15
    rsp_spy_ratio = (rsp["Close"] / spy["Close"]).dropna()
    if close.iloc[-1] > dma50.iloc[-1] and len(rsp_spy_ratio) >= 20 and rsp_spy_ratio.iloc[-1] < rsp_spy_ratio.iloc[-20]:
        score -= 10
    if vix_pct > 85:
        score = min(score, 55)

    score = int(max(0, min(100, round(score))))
    lvl = market_level(score)
    easy = (
        "Market internals are supportive and stress is contained, so selective risk-taking is allowed."
        if lvl >= 5
        else "Market is mixed or weak. Focus on capital protection and only take highly selective setups."
    )
    return ScoreResult(
        score=score,
        state=f"LEVEL {lvl} - {market_state_name(lvl)}",
        action=market_action(lvl),
        reasons=reasons[:3] if reasons else ["No strong positive signals today."],
        invalidation=invalidation,
        easy_explanation=easy + f" Confidence: {confidence_from_coverage(total_count, valid_count)}.",
    )


def score_stock(
    ticker: str,
    stock_df: pd.DataFrame,
    spy_df: pd.DataFrame,
    market_lvl: int,
    earnings_soon: bool,
) -> dict:
    close = stock_df["Close"]
    vol = stock_df["Volume"]
    dma20 = close.rolling(20).mean()
    dma50 = close.rolling(50).mean()

    score = 0
    reasons = []
    if close.iloc[-1] > dma20.iloc[-1]:
        score += 10
        reasons.append("Price above 20DMA")
    if close.iloc[-1] > dma50.iloc[-1]:
        score += 10
        reasons.append("Price above 50DMA")
    if dma20.iloc[-1] > dma50.iloc[-1]:
        score += 10
    if slope_up(dma20):
        score += 10

    rs = (close / spy_df["Close"]).dropna()
    if len(rs) >= 20 and rs.iloc[-1] > rs.iloc[-20]:
        score += 15
        reasons.append("Relative strength vs SPY is rising")

    stk_ret20 = close.pct_change(20).iloc[-1] if len(close) >= 21 else 0
    spy_ret20 = spy_df["Close"].pct_change(20).iloc[-1] if len(spy_df["Close"]) >= 21 else 0
    if stk_ret20 > spy_ret20:
        score += 10

    vol20 = vol.rolling(20).mean()
    if close.iloc[-1] > close.iloc[-2] and vol.iloc[-1] > vol20.iloc[-1]:
        score += 10

    up_days = stock_df[stock_df["Close"].pct_change() > 0]["Volume"].tail(20).mean()
    down_days = stock_df[stock_df["Close"].pct_change() < 0]["Volume"].tail(20).mean()
    if pd.notna(up_days) and pd.notna(down_days) and up_days > down_days:
        score += 5

    tr = pd.concat(
        [
            stock_df["High"] - stock_df["Low"],
            (stock_df["High"] - stock_df["Close"].shift(1)).abs(),
            (stock_df["Low"] - stock_df["Close"].shift(1)).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr14 = tr.rolling(14).mean()
    atr_ratio = float((atr14.iloc[-1] / close.iloc[-1]) if close.iloc[-1] else 0.0)
    if atr_ratio < 0.06:
        score += 5

    recent_5d = close.pct_change(5).iloc[-1] if len(close) >= 6 else 0
    overheated = recent_5d > 0.2
    if not overheated:
        score += 5

    if not earnings_soon:
        score += 5
    else:
        reasons.append("Earnings are close; execution should be reduced")
    score += 5

    if close.iloc[-1] > close.iloc[-2] and vol.iloc[-1] < vol20.iloc[-1]:
        score -= 10
    if close.iloc[-1] > close.iloc[-2] and len(rs) >= 10 and rs.iloc[-1] < rs.iloc[-10]:
        score -= 10

    score = int(max(0, min(100, round(score))))
    s_state = stock_state(score)
    action = combined_action(market_lvl, s_state)
    if earnings_soon or overheated:
        if action == "Buy":
            action = "Small Buy"
        elif action == "Selective Buy":
            action = "Watch"

    easy = (
        "This stock is one of the stronger names versus SPY and trend conditions are constructive."
        if s_state in {"Strong", "Good"}
        else "Signals are mixed or weak, so waiting for cleaner strength is safer."
    )
    return {
        "ticker": ticker,
        "stock_score": score,
        "stock_state": s_state,
        "final_action": action,
        "top_reasons": reasons[:3] if reasons else ["No strong setup confirmation."],
        "invalidation": "Loss of 20DMA with weak relative strength.",
        "easy_explanation": easy,
        "event_flag": "EARNINGS_WITHIN_7D" if earnings_soon else "NONE",
        "metrics": {
            "close": float(close.iloc[-1]),
            "dma20": float(dma20.iloc[-1]) if pd.notna(dma20.iloc[-1]) else None,
            "dma50": float(dma50.iloc[-1]) if pd.notna(dma50.iloc[-1]) else None,
            "volume_ratio_20d": float(vol.iloc[-1] / vol20.iloc[-1]) if pd.notna(vol20.iloc[-1]) else None,
            "atr_ratio": atr_ratio,
            "rs_20d_change": float(rs.iloc[-1] / rs.iloc[-20] - 1) if len(rs) >= 20 else None,
        },
        "series": {
            "dates": [d.strftime("%Y-%m-%d") for d in close.tail(120).index],
            "close": [float(v) for v in close.tail(120).tolist()],
            "dma20": [None if pd.isna(v) else float(v) for v in dma20.tail(120).tolist()],
            "dma50": [None if pd.isna(v) else float(v) for v in dma50.tail(120).tolist()],
            "rs": [float(v) for v in rs.tail(120).tolist()],
        },
    }


def get_earnings_within_7_days(ticker: str, as_of: date) -> bool:
    try:
        cal = yf.Ticker(ticker).calendar
        if cal is None or cal.empty:
            return False
        raw_date = cal.loc["Earnings Date"].iloc[0]
        if pd.isna(raw_date):
            return False
        earn_date = pd.Timestamp(raw_date).date()
        delta = (earn_date - as_of).days
        return 0 <= delta <= 7
    except Exception:
        return False


def main() -> None:
    now_et = datetime.now(tz=ET)
    as_of = now_et.date()

    watchlist = load_yaml(WATCHLIST_PATH).get("watchlist", [])
    if len(watchlist) != 6:
        raise ValueError("watchlist.yml must contain exactly 6 tickers.")

    spy = download_ohlcv("SPY")
    rsp = download_ohlcv("RSP")
    hyg = download_ohlcv("HYG")
    vix = download_ohlcv("^VIX")
    try:
        dxy = download_ohlcv("DX-Y.NYB")
        if dxy.empty:
            dxy = download_ohlcv("UUP")
    except Exception:
        dxy = download_ohlcv("UUP")

    sp500_close = download_sp500_prices()
    sp500_close = sp500_close.dropna(axis=1, how="all")
    sp500_ret = sp500_close.pct_change()
    ad_daily = (sp500_ret > 0).sum(axis=1) - (sp500_ret < 0).sum(axis=1)
    ad_line = ad_daily.fillna(0).cumsum()

    pct_above_20 = ((sp500_close.iloc[-1] > sp500_close.rolling(20).mean().iloc[-1]).mean() * 100.0)
    pct_above_50 = ((sp500_close.iloc[-1] > sp500_close.rolling(50).mean().iloc[-1]).mean() * 100.0)
    pct_above_20_prev = ((sp500_close.iloc[-2] > sp500_close.rolling(20).mean().iloc[-2]).mean() * 100.0)
    rsp_spy = (rsp["Close"] / spy["Close"]).dropna()

    events = load_events(as_of)
    market_data = {"SPY": spy, "RSP": rsp, "HYG": hyg, "DXY": dxy, "VIX": vix}
    breadth = {
        "pct_above_20dma": float(pct_above_20),
        "pct_above_50dma": float(pct_above_50),
        "pct_above_20dma_change": float(pct_above_20 - pct_above_20_prev),
        "adline_5d_up": bool(len(ad_line) >= 6 and ad_line.iloc[-1] > ad_line.iloc[-6]),
        "rsp_spy_ratio_20d_up_or_flat": bool(len(rsp_spy) >= 20 and rsp_spy.iloc[-1] >= rsp_spy.iloc[-20]),
    }
    market = score_market(as_of, market_data, breadth, events)
    lvl = market_level(market.score)

    event_risk, event_names = is_event_d0_d1(as_of, events)
    execution_strength = "Normal"
    if event_risk:
        execution_strength = "Reduced (Event D-1/D0)"
    elif lvl <= 3:
        execution_strength = "Reduced (Weak market regime)"

    stock_reports = []
    for ticker in watchlist:
        sdf = download_ohlcv(ticker)
        earnings_soon = get_earnings_within_7_days(ticker, as_of)
        stock_reports.append(score_stock(ticker, sdf, spy, lvl, earnings_soon))

    summary_table = [
        {
            "ticker": s["ticker"],
            "stock_score": s["stock_score"],
            "stock_state": s["stock_state"],
            "final_action": s["final_action"],
            "note": s["event_flag"],
        }
        for s in stock_reports
    ]

    output = {
        "generated_at_et": now_et.strftime("%Y-%m-%d %H:%M ET"),
        "market_data_as_of": f"{spy.index[-1].strftime('%Y-%m-%d')} 16:00 ET (Close)",
        "market": {
            "state": market.state,
            "score": market.score,
            "confidence": confidence_from_coverage(12, 12),
            "execution_strength": execution_strength,
            "action": market.action,
            "top_reasons": market.reasons,
            "invalidation": market.invalidation,
            "easy_explanation": market.easy_explanation,
            "negative_filters": {
                "filter_1_divergence": close_true(spy) and (not breadth["adline_5d_up"] or breadth["pct_above_20dma_change"] < 0),
                "filter_2_bigcap_only": bool(len(rsp_spy) >= 20 and rsp_spy.iloc[-1] < rsp_spy.iloc[-20]),
                "filter_3_high_stress": percentile_rank(vix["Close"]) > 85,
                "filter_4_event_risk": event_risk,
                "event_names": event_names,
            },
            "metrics": {
                "pct_above_20dma": breadth["pct_above_20dma"],
                "pct_above_50dma": breadth["pct_above_50dma"],
                "vix_percentile": percentile_rank(vix["Close"]),
                "dxy_20d_zscore": zscore(dxy["Close"], 20),
            },
        },
        "watchlist_summary": summary_table,
        "stocks": stock_reports,
        "charts": {
            "market": {
                "dates": [d.strftime("%Y-%m-%d") for d in spy["Close"].tail(180).index],
                "spy_close": [float(v) for v in spy["Close"].tail(180).tolist()],
                "spy_dma20": [None if pd.isna(v) else float(v) for v in spy["Close"].rolling(20).mean().tail(180).tolist()],
                "spy_dma50": [None if pd.isna(v) else float(v) for v in spy["Close"].rolling(50).mean().tail(180).tolist()],
                "spy_dma200": [None if pd.isna(v) else float(v) for v in spy["Close"].rolling(200).mean().tail(180).tolist()],
                "breadth_20": [float(v) for v in ((sp500_close > sp500_close.rolling(20).mean()).mean(axis=1) * 100).tail(180).tolist()],
                "breadth_50": [float(v) for v in ((sp500_close > sp500_close.rolling(50).mean()).mean(axis=1) * 100).tail(180).tolist()],
                "vix_close": [float(v) for v in vix["Close"].tail(180).tolist()],
                "hyg_close": [float(v) for v in hyg["Close"].tail(180).tolist()],
                "dxy_close": [float(v) for v in dxy["Close"].tail(180).tolist()],
            }
        },
    }

    DOCS_DATA_DIR.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)


def close_true(spy: pd.DataFrame) -> bool:
    return bool(len(spy["Close"]) >= 2 and spy["Close"].iloc[-1] > spy["Close"].iloc[-2])


if __name__ == "__main__":
    main()
