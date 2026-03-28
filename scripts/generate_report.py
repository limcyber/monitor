from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
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
EARNINGS_PATH = BASE_DIR / "config" / "earnings_calendar.yml"
OUTPUT_PATH = DOCS_DATA_DIR / "latest.json"
HISTORY_PATH = DOCS_DATA_DIR / "history.json"
ET = ZoneInfo("America/New_York")
MARKET_LEVELS_TOTAL = 6


@dataclass
class ScoreResult:
    score: int
    state: str
    action: str
    confidence: str
    reasons: list[str]
    invalidation: str
    easy_explanation: str
    cross_highlights: list[str]
    positive_factors: list[str]
    negative_factors: list[str]


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


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


def load_earnings_calendar() -> dict[str, date]:
    raw = load_yaml(EARNINGS_PATH)
    result: dict[str, date] = {}
    for ticker, value in (raw.get("earnings", {}) or {}).items():
        if not value:
            continue
        try:
            result[str(ticker).upper()] = datetime.strptime(str(value), "%Y-%m-%d").date()
        except Exception:
            continue
    return result


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


def is_intraday_session(now_et: datetime) -> bool:
    return now_et.weekday() < 5 and time(8, 30) <= now_et.time() <= time(16, 0)


def download_intraday_ohlcv(ticker: str, period: str = "5d") -> pd.DataFrame:
    df = yf.download(
        ticker,
        period=period,
        interval="5m",
        progress=False,
        auto_adjust=False,
        prepost=True,
        threads=False,
    )
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [col[0] for col in df.columns]
    if df.empty:
        return df
    if getattr(df.index, "tz", None) is None:
        df.index = df.index.tz_localize("UTC").tz_convert(ET)
    else:
        df.index = df.index.tz_convert(ET)
    df = df.dropna(subset=["Close"])
    session_mask = (
        (df.index.dayofweek < 5)
        & (df.index.time >= time(8, 30))
        & (df.index.time <= time(16, 0))
    )
    return df.loc[session_mask]


def overlay_intraday_bar(daily_df: pd.DataFrame, intraday_df: pd.DataFrame) -> tuple[pd.DataFrame, datetime | None]:
    if daily_df.empty or intraday_df.empty:
        return daily_df, None

    merged = daily_df.copy()
    latest_ts = intraday_df.index[-1].to_pydatetime()
    latest_bar = intraday_df.iloc[-1]
    session_date = latest_ts.astimezone(ET).date()
    target_index = pd.Timestamp(session_date)

    row = {}
    for col in merged.columns:
        if col in latest_bar.index and pd.notna(latest_bar[col]):
            row[col] = latest_bar[col]
        elif col == "Adj Close" and "Close" in latest_bar.index and pd.notna(latest_bar["Close"]):
            row[col] = latest_bar["Close"]
        elif col == "Volume":
            row[col] = float(latest_bar.get("Volume", 0) or 0)

    if merged.index[-1].date() == session_date:
        row_name = merged.index[-1]
        for col, value in row.items():
            merged.at[row_name, col] = value
    else:
        merged.loc[target_index] = {col: row.get(col, np.nan) for col in merged.columns}
        merged = merged.sort_index()

    return merged, latest_ts.astimezone(ET)


def load_price_frame(ticker: str, now_et: datetime, period: str = "1y") -> tuple[pd.DataFrame, datetime | None]:
    daily_df = download_ohlcv(ticker, period=period)
    if not is_intraday_session(now_et):
        return daily_df, None
    try:
        intraday_df = download_intraday_ohlcv(ticker)
    except Exception:
        return daily_df, None
    return overlay_intraday_bar(daily_df, intraday_df)


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
        6: "강한 상승장",
        5: "상승 우위",
        4: "회복 구간",
        3: "중립 / 혼조",
        2: "약화 / 주의",
        1: "방어 우선",
    }[level]


def market_action(level: int) -> str:
    return {
        6: "매수 / 강한 보유",
        5: "매수 / 보유",
        4: "소규모 매수 / 보유",
        3: "보유 / 비중 축소",
        2: "비중 축소",
        1: "신규 진입 자제 / 방어",
    }[level]


def stock_state(score: int) -> str:
    if score >= 80:
        return "강함"
    if score >= 65:
        return "양호"
    if score >= 50:
        return "애매"
    if score >= 35:
        return "약함"
    return "회피"


def combined_action(market_lvl: int, s_state: str) -> str:
    if market_lvl >= 5:
        if s_state == "강함":
            return "매수 가능"
        if s_state == "양호":
            return "선별 매수"
        return "보류 / 관찰"
    if market_lvl == 4:
        if s_state == "강함":
            return "소규모 매수"
        if s_state == "양호":
            return "매우 선별적 접근"
        return "관찰"
    if s_state == "강함":
        return "아주 소규모 / 대기"
    return "회피 / 비중 축소"


def confidence_from_coverage(total_metrics: int, valid_metrics: int) -> str:
    ratio = valid_metrics / max(total_metrics, 1)
    if ratio >= 0.85:
        return "높음"
    if ratio >= 0.65:
        return "보통"
    return "낮음"


def factor_text(text: str, points: int | str) -> str:
    if isinstance(points, int):
        if points == 0:
            return f"{text} (0)"
        return f"{text} ({points:+d})"
    return f"{text} ({points})"


def pct_change_from_prev_close(series: pd.Series) -> float | None:
    clean = series.dropna()
    if len(clean) < 2:
        return None
    prev = clean.iloc[-2]
    last = clean.iloc[-1]
    if prev == 0 or pd.isna(prev) or pd.isna(last):
        return None
    return float((last / prev - 1.0) * 100.0)


def volume_ratio(series: pd.Series, lookback: int = 20) -> float | None:
    avg = series.rolling(lookback).mean().iloc[-1]
    last = series.iloc[-1]
    if pd.isna(avg) or avg == 0 or pd.isna(last):
        return None
    return float(last / avg)


def market_volume_points(price_above_dma20: bool, ratio: float | None) -> tuple[int, str | None, str | None]:
    if ratio is None:
        return (0, None, None)
    if price_above_dma20 and ratio >= 1.25:
        return (5, factor_text("상승에 거래량이 강하게 붙었습니다", 5), None)
    if price_above_dma20 and ratio >= 1.05:
        return (3, factor_text("상승에 거래량이 어느 정도 붙었습니다", 3), None)
    if price_above_dma20 and ratio < 0.9:
        return (-3, None, factor_text("반등 시도 대비 거래량이 약합니다", -3))
    return (0, None, None)


def stock_volume_points(price_up: bool, ratio: float | None) -> tuple[int, str | None, str | None]:
    if ratio is None:
        return (0, None, None)
    if price_up and ratio >= 1.5:
        return (12, factor_text("상승할 때 거래량이 매우 강했습니다", 12), None)
    if price_up and ratio >= 1.2:
        return (10, factor_text("상승할 때 거래량이 평균보다 강했습니다", 10), None)
    if price_up and ratio >= 1.0:
        return (6, factor_text("상승할 때 거래량이 평균 수준은 나왔습니다", 6), None)
    if ratio < 0.85:
        return (-10, None, factor_text("거래량이 아직 약합니다", -10))
    if ratio < 1.0:
        return (0, None, factor_text("거래량이 강하게 붙는 모습은 아직 부족합니다", 0))
    return (0, None, None)


def recent_cross_signal(short_ma: pd.Series, long_ma: pd.Series, bull_text: str, bear_text: str, lookback: int = 5) -> tuple[str | None, str | None]:
    short_clean = short_ma.dropna()
    long_clean = long_ma.dropna()
    if len(short_clean) < lookback + 2 or len(long_clean) < lookback + 2:
        return (None, None)
    spread = (short_ma - long_ma).dropna()
    if len(spread) < lookback + 1:
        return (None, None)
    recent = spread.tail(lookback + 1)
    if recent.iloc[-1] > 0 and (recent <= 0).any():
        return (bull_text, None)
    if recent.iloc[-1] < 0 and (recent >= 0).any():
        return (None, bear_text)
    return (None, None)


def pick_market_reasons(level: int, positive_factors: list[str], negative_factors: list[str]) -> list[str]:
    positive_priority = [
        "S&P500이 200일선 위에 있습니다",
        "나스닥이 200일선 위에 있습니다",
        "KOSPI가 200일선 위에 있습니다",
        "KOSDAQ이 200일선 위에 있습니다",
        "S&P500의 50일선이 200일선 위에 있습니다",
        "나스닥의 50일선이 200일선 위에 있습니다",
        "KOSPI의 50일선이 200일선 위에 있습니다",
        "KOSDAQ의 50일선이 200일선 위에 있습니다",
        "20일선 위 종목 비율이 55%를 넘습니다",
        "50일선 위 종목 비율이 50%를 넘습니다",
        "상승 종목 수 흐름이 최근 5일 개선됐습니다",
        "반도체가 코스피보다 더 강합니다",
        "코스닥이 코스피에 크게 밀리지 않습니다",
    ]
    negative_priority = [
        "VIX가 매우 높아 점수 상한이 걸렸습니다",
        "원달러와 해외 변동성이 같이 높아 부담이 큽니다",
        "20일선 위 종목 비율이 너무 낮아 시장 폭이 크게 약합니다",
        "50일선 위 종목 비율이 낮아 중간 흐름도 약합니다",
        "지수는 반등해도 오르는 종목 수는 따라오지 못했습니다",
        "S&P500과 나스닥이 함께 중기 데드크로스",
        "S&P500과 나스닥이 함께 단기 데드크로스",
        "KOSPI와 KOSDAQ이 함께 중기 데드크로스",
        "KOSPI와 KOSDAQ이 함께 단기 데드크로스",
        "해외 변동성이 높아 국내장도 흔들릴 수 있습니다",
        "원달러가 많이 올라 외국인 수급 부담이 큽니다",
        "원달러가 올라 외국인 수급에는 부담입니다",
        "S&P500이 200일선 아래",
        "나스닥이 200일선 아래",
        "KOSPI가 200일선 아래에 있습니다",
        "KOSDAQ이 200일선 아래에 있습니다",
        "대형주 몇 종목에만 힘이 몰리고 있습니다",
        "소형주가 대형주보다 약해 공격적인 분위기가 아닙니다",
        "중소형주 쪽 힘이 약합니다",
        "반도체 ETF가 50일선 아래라 주도 업종 힘이 약합니다",
        "반도체가 코스피보다 약해지고 있습니다",
    ]

    def pick_by_priority(candidates: list[str], ordered: list[str]) -> list[str]:
        picked: list[str] = []
        for needle in ordered:
            for item in candidates:
                if needle in item and item not in picked:
                    picked.append(item)
                    break
            if len(picked) >= 3:
                return picked
        for item in candidates:
            if item not in picked:
                picked.append(item)
            if len(picked) >= 3:
                break
        return picked

    if level <= 2:
        primary = pick_by_priority(negative_factors, negative_priority)
        if primary:
            return primary
    if level == 3:
        mixed = pick_by_priority(negative_factors, negative_priority)[:2] + pick_by_priority(positive_factors, positive_priority)[:1]
        if mixed:
            return mixed[:3]
    primary = pick_by_priority(positive_factors, positive_priority)
    if primary:
        return primary
    return pick_by_priority(negative_factors, negative_priority)


def prioritize_stock_reasons(reasons: list[str], state: str) -> list[str]:
    if not reasons:
        return []

    positive_priority = [
        "최근 중기 골든크로스가 나왔습니다",
        "최근 단기 골든크로스가 나왔습니다",
        "이 종목이 시장보다 더 잘 버팁니다",
        "최근 한 달 흐름이 시장보다 좋습니다",
        "상승할 때 거래량이 평균보다 강했습니다",
        "최근에는 상승일 거래량이 더 우세했습니다",
        "짧은 흐름이 중간 흐름보다 좋습니다",
        "20일선이 올라가는 중입니다",
        "50일선 위에 있습니다",
        "20일선 위에 있습니다",
    ]
    negative_priority = [
        "최근 중기 데드크로스가 나왔습니다",
        "최근 단기 데드크로스가 나왔습니다",
        "실적이 가까워 보수적으로 봐야 합니다",
        "실적 발표가 가까워 보수적으로 봐야 합니다",
        "거래량이 아직 약합니다",
        "최근 시장보다 힘이 약합니다",
        "최근 단기 급등이 커서 추격 매수는 부담입니다",
        "최근 한 달 흐름이 시장보다 약합니다",
        "최근 한 달 수익률이 시장보다 약합니다",
        "짧은 흐름이 중간 흐름보다 약합니다",
        "종가가 20일선 아래에 있습니다",
        "종가가 50일선 아래에 있습니다",
    ]

    ordered = negative_priority + positive_priority if state in {"약함", "회피"} else positive_priority + negative_priority
    picked = []
    for needle in ordered:
        for reason in reasons:
            if needle in reason and reason not in picked:
                picked.append(reason)
                break
        if len(picked) >= 3:
            break
    if len(picked) < 3:
        for reason in reasons:
            if reason not in picked:
                picked.append(reason)
            if len(picked) >= 3:
                break
    return picked


def score_market(as_of: date, market_data: dict, breadth: dict, events: dict) -> ScoreResult:
    score = 0
    reasons = []
    cross_highlights = []
    positive_factors = []
    negative_factors = []
    valid_count = 0
    total_count = 21

    spx = market_data["SPX"]
    ndx = market_data["NDX"]
    rut = market_data["RUT"]
    tnx = market_data["TNX"]
    spy_proxy = market_data["SPY_PROXY"]
    qqq_proxy = market_data["QQQ_PROXY"]
    rsp = market_data["RSP"]
    hyg = market_data["HYG"]
    dxy = market_data["DXY"]
    vix = market_data["VIX"]

    spx_close = spx["Close"]
    spx_dma5 = spx_close.rolling(5).mean()
    spx_dma20 = spx_close.rolling(20).mean()
    spx_dma50 = spx_close.rolling(50).mean()
    spx_dma200 = spx_close.rolling(200).mean()

    ndx_close = ndx["Close"]
    ndx_dma5 = ndx_close.rolling(5).mean()
    ndx_dma20 = ndx_close.rolling(20).mean()
    ndx_dma50 = ndx_close.rolling(50).mean()
    ndx_dma200 = ndx_close.rolling(200).mean()

    rut_close = rut["Close"]
    rut_dma20 = rut_close.rolling(20).mean()
    rut_dma50 = rut_close.rolling(50).mean()
    rut_dma200 = rut_close.rolling(200).mean()
    rut_spx_ratio = (rut_close / spx_close).dropna()

    tnx_close = tnx["Close"]

    spy_proxy_close = spy_proxy["Close"]
    spy_proxy_volume = spy_proxy["Volume"]
    qqq_proxy_close = qqq_proxy["Close"]
    qqq_proxy_volume = qqq_proxy["Volume"]

    if spx_close.iloc[-1] > spx_dma200.iloc[-1]:
        score += 10
        reasons.append("S&P500이 200일선 위에 있습니다")
        positive_factors.append(factor_text("S&P500이 200일선 위에 있습니다", 10))
    valid_count += 1
    if spx_dma50.iloc[-1] > spx_dma200.iloc[-1]:
        score += 8
        reasons.append("S&P500의 50일선이 200일선 위에 있습니다")
        positive_factors.append(factor_text("S&P500의 50일선이 200일선 위에 있습니다", 8))
    valid_count += 1
    if slope_up(spx_dma20):
        score += 5
        reasons.append("S&P500의 20일선이 올라가는 중입니다")
        positive_factors.append(factor_text("S&P500의 20일선이 올라가는 중입니다", 5))
    valid_count += 1
    if spx_close.iloc[-1] > spx_dma20.iloc[-1]:
        score += 5
        positive_factors.append(factor_text("S&P500이 20일선 위에 있습니다", 5))
    else:
        score -= 2
        negative_factors.append(factor_text("S&P500이 20일선 아래라 단기 흐름이 약합니다", -2))
    valid_count += 1

    spx_short_bull, spx_short_bear = recent_cross_signal(
        spx_dma5,
        spx_dma20,
        factor_text("S&P500에서 최근 5일선이 20일선을 상향 돌파했습니다", 2),
        factor_text("S&P500에서 최근 5일선이 20일선을 하향 이탈했습니다", -6),
    )
    if spx_short_bull:
        score += 2
        cross_highlights.append("S&P500 최근 단기 골든크로스: 5일선이 20일선을 위로 돌파했습니다.")
        positive_factors.append(spx_short_bull)
        reasons.append("S&P500에서 최근 단기 골든크로스가 나왔습니다")
    if spx_short_bear:
        score -= 6
        cross_highlights.append("S&P500 최근 단기 데드크로스: 5일선이 20일선 아래로 내려갔습니다.")
        negative_factors.append(spx_short_bear)
        reasons.append("S&P500에서 최근 단기 데드크로스가 나왔습니다")

    spx_mid_bull, spx_mid_bear = recent_cross_signal(
        spx_dma20,
        spx_dma50,
        factor_text("S&P500에서 최근 20일선이 50일선을 상향 돌파했습니다", 4),
        factor_text("S&P500에서 최근 20일선이 50일선을 하향 이탈했습니다", -10),
        lookback=10,
    )
    if spx_mid_bull:
        score += 4
        cross_highlights.append("S&P500 최근 중기 골든크로스: 20일선이 50일선을 위로 돌파했습니다.")
        positive_factors.append(spx_mid_bull)
    if spx_mid_bear:
        score -= 10
        cross_highlights.append("S&P500 최근 중기 데드크로스: 20일선이 50일선 아래로 내려갔습니다.")
        negative_factors.append(spx_mid_bear)
        reasons.append("S&P500에서 최근 중기 데드크로스가 나왔습니다")

    if ndx_close.iloc[-1] > ndx_dma200.iloc[-1]:
        score += 10
        reasons.append("나스닥이 200일선 위에 있습니다")
        positive_factors.append(factor_text("나스닥이 200일선 위에 있습니다", 10))
    valid_count += 1
    if ndx_dma50.iloc[-1] > ndx_dma200.iloc[-1]:
        score += 8
        reasons.append("나스닥의 50일선이 200일선 위에 있습니다")
        positive_factors.append(factor_text("나스닥의 50일선이 200일선 위에 있습니다", 8))
    valid_count += 1
    if slope_up(ndx_dma20):
        score += 5
        reasons.append("나스닥의 20일선이 올라가는 중입니다")
        positive_factors.append(factor_text("나스닥의 20일선이 올라가는 중입니다", 5))
    valid_count += 1
    if ndx_close.iloc[-1] > ndx_dma20.iloc[-1]:
        score += 5
        positive_factors.append(factor_text("나스닥이 20일선 위에 있습니다", 5))
    else:
        score -= 2
        negative_factors.append(factor_text("나스닥이 20일선 아래라 단기 흐름이 약합니다", -2))
    valid_count += 1

    ndx_short_bull, ndx_short_bear = recent_cross_signal(
        ndx_dma5,
        ndx_dma20,
        factor_text("나스닥에서 최근 5일선이 20일선을 상향 돌파했습니다", 2),
        factor_text("나스닥에서 최근 5일선이 20일선을 하향 이탈했습니다", -6),
    )
    if ndx_short_bull:
        score += 2
        cross_highlights.append("나스닥 최근 단기 골든크로스: 5일선이 20일선을 위로 돌파했습니다.")
        positive_factors.append(ndx_short_bull)
        reasons.append("나스닥에서 최근 단기 골든크로스가 나왔습니다")
    if ndx_short_bear:
        score -= 6
        cross_highlights.append("나스닥 최근 단기 데드크로스: 5일선이 20일선 아래로 내려갔습니다.")
        negative_factors.append(ndx_short_bear)
        reasons.append("나스닥에서 최근 단기 데드크로스가 나왔습니다")

    ndx_mid_bull, ndx_mid_bear = recent_cross_signal(
        ndx_dma20,
        ndx_dma50,
        factor_text("나스닥에서 최근 20일선이 50일선을 상향 돌파했습니다", 4),
        factor_text("나스닥에서 최근 20일선이 50일선을 하향 이탈했습니다", -10),
        lookback=10,
    )
    if ndx_mid_bull:
        score += 4
        cross_highlights.append("나스닥 최근 중기 골든크로스: 20일선이 50일선을 위로 돌파했습니다.")
        positive_factors.append(ndx_mid_bull)
    if ndx_mid_bear:
        score -= 10
        cross_highlights.append("나스닥 최근 중기 데드크로스: 20일선이 50일선 아래로 내려갔습니다.")
        negative_factors.append(ndx_mid_bear)
        reasons.append("나스닥에서 최근 중기 데드크로스가 나왔습니다")

    if spx_short_bear and ndx_short_bear:
        score -= 6
        score = min(score, 72)
        negative_factors.append(factor_text("S&P500과 나스닥이 함께 단기 데드크로스라 공격 점수를 높게 주기 어렵습니다", "상한 72"))
        reasons.append("S&P500과 나스닥이 함께 단기 데드크로스입니다")

    if spx_mid_bear and ndx_mid_bear:
        score = min(score, 55)
        negative_factors.append(factor_text("S&P500과 나스닥이 함께 중기 데드크로스라 회복 확인 전까지 보수적으로 보는 편이 좋습니다", "상한 55"))
        reasons.append("S&P500과 나스닥이 함께 중기 데드크로스입니다")

    if rut_close.iloc[-1] > rut_dma200.iloc[-1]:
        score += 6
        positive_factors.append(factor_text("소형주(RUT)가 200일선 위에 있습니다", 6))
    valid_count += 1
    if rut_close.iloc[-1] > rut_dma20.iloc[-1]:
        score += 3
        positive_factors.append(factor_text("소형주(RUT)가 20일선 위에 있습니다", 3))
    valid_count += 1
    if len(rut_spx_ratio) >= 20 and rut_spx_ratio.iloc[-1] >= rut_spx_ratio.iloc[-20]:
        score += 4
        positive_factors.append(factor_text("소형주도 대형주에 크게 밀리지 않습니다", 4))
    elif len(rut_spx_ratio) >= 20:
        score -= 2
        negative_factors.append(factor_text("소형주가 대형주보다 약해 공격적인 분위기가 아닙니다", -2))
    valid_count += 1

    if breadth["pct_above_20dma"] > 55:
        score += 5
        reasons.append("오르는 종목 수가 너무 적지는 않습니다")
        positive_factors.append(factor_text("20일선 위 종목 비율이 55%를 넘습니다", 5))
    elif breadth["pct_above_20dma"] < 35:
        score -= 6
        negative_factors.append(factor_text("20일선 위 종목 비율이 너무 낮아 시장 폭이 크게 약합니다", -6))
    elif breadth["pct_above_20dma"] < 45:
        score -= 3
        negative_factors.append(factor_text("20일선 위 종목 비율이 낮아 오르는 종목 수가 적습니다", -3))
    valid_count += 1
    if breadth["pct_above_50dma"] > 50:
        score += 5
        positive_factors.append(factor_text("50일선 위 종목 비율이 50%를 넘습니다", 5))
    elif breadth["pct_above_50dma"] < 40:
        score -= 3
        negative_factors.append(factor_text("50일선 위 종목 비율이 낮아 중간 흐름도 약합니다", -3))
    valid_count += 1
    if breadth["adline_5d_up"]:
        score += 3
        positive_factors.append(factor_text("상승 종목 수 흐름이 최근 5일 개선됐습니다", 3))
    valid_count += 1
    if breadth["rsp_spy_ratio_20d_up_or_flat"]:
        score += 2
        positive_factors.append(factor_text("대형주 몇 종목만 오르는 장은 아닙니다", 2))
    else:
        score -= 2
        negative_factors.append(factor_text("대형주 몇 종목에만 힘이 몰리고 있습니다", -2))
    valid_count += 1

    vix_pct = percentile_rank(vix["Close"])
    if vix_pct < 60:
        score += 12
        positive_factors.append(factor_text("VIX가 과도하게 높지 않습니다", 12))
    elif vix_pct > 80:
        score -= 5
        negative_factors.append(factor_text("VIX가 높아 투자 심리가 크게 불안합니다", -5))
    elif vix_pct > 70:
        score -= 3
        negative_factors.append(factor_text("VIX가 낮지 않아 투자 심리가 불안합니다", -3))
    valid_count += 1
    hyg_dma50 = hyg["Close"].rolling(50).mean()
    if hyg["Close"].iloc[-1] > hyg_dma50.iloc[-1]:
        score += 5
        positive_factors.append(factor_text("HYG가 50일선 위에 있습니다", 5))
    else:
        score -= 3
        negative_factors.append(factor_text("HYG가 50일선 아래라 위험자산 분위기가 약합니다", -3))
    valid_count += 1
    dxy_z = zscore(dxy["Close"], 20)
    if dxy_z <= 1.0:
        score += 5
        positive_factors.append(factor_text("달러 강세가 아직 심하지 않습니다", 5))
    else:
        score -= 2
        negative_factors.append(factor_text("달러가 강해 위험자산에는 부담입니다", -2))
    valid_count += 1
    tnx_z = zscore(tnx_close, 20)
    if tnx_z <= 0.8:
        score += 4
        positive_factors.append(factor_text("10년물 금리 부담이 아직 심하지 않습니다", 4))
    else:
        score -= 2
        negative_factors.append(factor_text("10년물 금리가 높아 성장주에 부담입니다", -2))
    valid_count += 1

    spy_vol_ratio = volume_ratio(spy_proxy_volume, 20)
    market_spy_vol_points, market_spy_vol_positive, market_spy_vol_negative = market_volume_points(
        bool(spx_close.iloc[-1] > spx_dma20.iloc[-1]),
        spy_vol_ratio,
    )
    score += market_spy_vol_points
    if market_spy_vol_positive:
        positive_factors.append(factor_text(f"S&P500 {market_spy_vol_positive.split(' (')[0]}", market_spy_vol_points))
    if market_spy_vol_negative:
        negative_factors.append(factor_text(f"S&P500 {market_spy_vol_negative.split(' (')[0]}", market_spy_vol_points))
    valid_count += 1
    qqq_vol_ratio = volume_ratio(qqq_proxy_volume, 20)
    market_qqq_vol_points, market_qqq_vol_positive, market_qqq_vol_negative = market_volume_points(
        bool(ndx_close.iloc[-1] > ndx_dma20.iloc[-1]),
        qqq_vol_ratio,
    )
    score += market_qqq_vol_points
    if market_qqq_vol_positive:
        positive_factors.append(factor_text(f"나스닥 {market_qqq_vol_positive.split(' (')[0]}", market_qqq_vol_points))
    if market_qqq_vol_negative:
        negative_factors.append(factor_text(f"나스닥 {market_qqq_vol_negative.split(' (')[0]}", market_qqq_vol_points))
    valid_count += 1
    event_risk, event_names = is_event_d0_d1(as_of, events)
    if not event_risk:
        score += 3
        positive_factors.append(factor_text("큰 이벤트가 바로 앞에 있지 않습니다", 3))
    else:
        negative_factors.append(factor_text(f"{', '.join(event_names)} 이벤트가 가까워 보수적으로 봐야 합니다", -3))

    if spx_close.iloc[-1] <= spx_dma50.iloc[-1]:
        score -= 3
        negative_factors.append(factor_text("S&P500이 50일선 아래라 중간 흐름도 약합니다", -3))
    if ndx_close.iloc[-1] <= ndx_dma50.iloc[-1]:
        score -= 3
        negative_factors.append(factor_text("나스닥이 50일선 아래라 중간 흐름도 약합니다", -3))
    if spx_close.iloc[-1] <= spx_dma50.iloc[-1] and ndx_close.iloc[-1] <= ndx_dma50.iloc[-1]:
        score -= 2
        negative_factors.append(factor_text("S&P500과 나스닥이 함께 50일선 아래라 회복 확인이 더 필요합니다", -2))
    if spx_close.iloc[-1] <= spx_dma200.iloc[-1] and ndx_close.iloc[-1] <= ndx_dma200.iloc[-1]:
        invalidation = "현재 S&P500과 나스닥이 모두 200일선 아래에 있습니다. 반등이 나오더라도 둘 다 200일선을 회복하지 못하고 오르는 종목 수까지 약하면 방어적으로 보는 편이 좋습니다."
    elif spx_close.iloc[-1] <= spx_dma200.iloc[-1] or ndx_close.iloc[-1] <= ndx_dma200.iloc[-1]:
        invalidation = "S&P500 또는 나스닥 중 하나가 아직 200일선 아래에 있습니다. 둘 중 약한 쪽이 계속 밀리면 공격적으로 보기 어렵습니다."
    elif spx_close.iloc[-1] <= spx_dma50.iloc[-1] or ndx_close.iloc[-1] <= ndx_dma50.iloc[-1]:
        invalidation = "S&P500과 나스닥이 200일선 위에 있더라도 둘 중 하나가 50일선을 지키지 못하고 오르는 종목 수도 줄면 경계가 필요합니다."
    else:
        invalidation = "S&P500과 나스닥 중 하나라도 50일선 아래로 밀리고 오르는 종목 수도 함께 줄면 경계가 필요합니다."
    if event_risk:
        invalidation = f"{', '.join(event_names)} 이벤트가 가까워 공격적으로 대응하기는 부담스럽습니다."

    if (spx_close.iloc[-1] > spx_close.iloc[-2] or ndx_close.iloc[-1] > ndx_close.iloc[-2]) and (not breadth["adline_5d_up"] or breadth["pct_above_20dma_change"] < 0):
        score -= 6
        negative_factors.append(factor_text("지수는 반등해도 오르는 종목 수는 따라오지 못했습니다", -6))
    rsp_spx_ratio = (rsp["Close"] / spx_close).dropna()
    if (spx_close.iloc[-1] > spx_dma50.iloc[-1] or ndx_close.iloc[-1] > ndx_dma50.iloc[-1]) and len(rsp_spx_ratio) >= 20 and rsp_spx_ratio.iloc[-1] < rsp_spx_ratio.iloc[-20]:
        negative_factors.append(factor_text("대형주 몇 종목만 버티고 있고 시장 전체 힘은 약합니다", 0))
    if vix_pct > 85:
        negative_factors.append(factor_text("VIX가 매우 높아 점수 상한이 걸렸습니다", "상한 50"))
        score = min(score, 50)
    if dxy_z > 1.0 and tnx_z > 0.8:
        negative_factors.append(factor_text("달러와 금리가 함께 높아 성장주와 위험자산에 부담입니다", 0))

    if breadth["pct_above_20dma"] <= 55 and breadth["pct_above_20dma"] >= 45:
        negative_factors.append(factor_text("20일선 위 종목 비율이 낮아 오르는 종목 수가 적습니다", 0))
    if breadth["pct_above_50dma"] <= 50 and breadth["pct_above_50dma"] >= 40:
        negative_factors.append(factor_text("50일선 위 종목 비율이 낮아 중간 흐름도 약합니다", 0))
    if not breadth["adline_5d_up"]:
        negative_factors.append(factor_text("최근 5일 기준 상승 종목 수 흐름이 약합니다", 0))
    if not breadth["rsp_spy_ratio_20d_up_or_flat"]:
        negative_factors.append(factor_text("대형주 몇 종목에만 힘이 몰리고 있습니다", 0))
    if rut_close.iloc[-1] <= rut_dma200.iloc[-1]:
        negative_factors.append(factor_text("소형주가 약해서 시장 전체 힘도 약합니다", 0))
    if len(rut_spx_ratio) >= 20 and rut_spx_ratio.iloc[-1] < rut_spx_ratio.iloc[-20]:
        negative_factors.append(factor_text("소형주가 대형주보다 약해 공격적인 분위기가 아닙니다", 0))
    if vix_pct >= 60 and vix_pct <= 85:
        negative_factors.append(factor_text("VIX가 낮지 않아 투자 심리가 불안합니다", 0))
    if hyg["Close"].iloc[-1] <= hyg_dma50.iloc[-1]:
        negative_factors.append(factor_text("HYG가 50일선 아래라 위험자산 분위기가 약합니다", 0))
    if dxy_z > 1.0:
        negative_factors.append(factor_text("달러가 강해 위험자산에는 부담입니다", 0))
    if tnx_z > 0.8:
        negative_factors.append(factor_text("10년물 금리가 높아 성장주에 부담입니다", 0))

    available_checks = [
        bool(pd.notna(spx_dma200.iloc[-1])),
        bool(pd.notna(spx_dma50.iloc[-1]) and pd.notna(spx_dma200.iloc[-1])),
        bool(len(spx_dma20.dropna()) >= 20),
        bool(pd.notna(spx_dma20.iloc[-1])),
        bool(pd.notna(ndx_dma200.iloc[-1])),
        bool(pd.notna(ndx_dma50.iloc[-1]) and pd.notna(ndx_dma200.iloc[-1])),
        bool(len(ndx_dma20.dropna()) >= 20),
        bool(pd.notna(ndx_dma20.iloc[-1])),
        bool(pd.notna(rut_dma200.iloc[-1])),
        bool(pd.notna(rut_dma20.iloc[-1])),
        bool(len(rut_spx_ratio) >= 20),
        bool(not math.isnan(breadth["pct_above_20dma"])),
        bool(not math.isnan(breadth["pct_above_50dma"])),
        bool(breadth.get("adline_available", False)),
        bool(breadth.get("rsp_spy_available", False)),
        bool(len(vix["Close"].dropna()) >= 30),
        bool(pd.notna(hyg_dma50.iloc[-1])),
        bool(len(dxy["Close"].dropna()) >= 20),
        bool(len(tnx_close.dropna()) >= 20),
        bool(spy_vol_ratio is not None),
        bool(qqq_vol_ratio is not None),
    ]
    valid_count = sum(available_checks)

    score = int(max(0, min(100, round(score))))
    if (
        score < 15
        and spx_dma50.iloc[-1] > spx_dma200.iloc[-1]
        and ndx_dma50.iloc[-1] > ndx_dma200.iloc[-1]
    ):
        score = 15
    lvl = market_level(score)
    confidence = confidence_from_coverage(total_count, valid_count)
    top_reasons = pick_market_reasons(lvl, positive_factors, negative_factors)
    easy = (
        "시장 분위기가 비교적 괜찮아 강한 종목은 선별해서 접근해볼 수 있습니다."
        if lvl >= 5
        else "시장 분위기가 좋지 않아서 서두르기보다 방어적으로 보는 편이 좋습니다."
    )
    return ScoreResult(
        score=score,
        state=f"레벨 {lvl}/{MARKET_LEVELS_TOTAL} - {market_state_name(lvl)}",
        action=market_action(lvl),
        confidence=confidence,
        reasons=top_reasons if top_reasons else ["오늘은 시장을 좋게 볼 만한 신호가 많지 않습니다"],
        invalidation=invalidation,
        easy_explanation=easy + f" 신뢰도는 {confidence}입니다.",
        cross_highlights=cross_highlights[:4],
        positive_factors=positive_factors[:6],
        negative_factors=negative_factors[:6],
    )


def score_stock(
    ticker: str,
    stock_df: pd.DataFrame,
    benchmark_df: pd.DataFrame,
    market_lvl: int,
    earnings_soon: bool | None,
    earnings_date: date | None,
    neutral_missing_earnings: bool = False,
) -> dict:
    close = stock_df["Close"]
    vol = stock_df["Volume"]
    dma5 = close.rolling(5).mean()
    dma20 = close.rolling(20).mean()
    dma50 = close.rolling(50).mean()

    score = 0
    reasons = []
    cross_highlights = []
    positive_factors = []
    negative_factors = []
    if close.iloc[-1] > dma20.iloc[-1]:
        score += 10
        reasons.append("20일선 위에 있습니다")
        positive_factors.append(factor_text("종가가 20일선 위에 있습니다", 10))
    else:
        score -= 4
        reasons.append("종가가 20일선 아래에 있습니다")
        negative_factors.append(factor_text("종가가 20일선 아래에 있습니다", -4))
    if close.iloc[-1] > dma50.iloc[-1]:
        score += 10
        reasons.append("50일선 위에 있습니다")
        positive_factors.append(factor_text("종가가 50일선 위에 있습니다", 10))
    else:
        score -= 6
        reasons.append("종가가 50일선 아래에 있습니다")
        negative_factors.append(factor_text("종가가 50일선 아래에 있습니다", -6))
    if dma20.iloc[-1] > dma50.iloc[-1]:
        score += 10
        positive_factors.append(factor_text("짧은 흐름이 중간 흐름보다 좋습니다", 10))
    else:
        score -= 2
        negative_factors.append(factor_text("짧은 흐름이 중간 흐름보다 약합니다", -2))
    if slope_up(dma20):
        score += 10
        positive_factors.append(factor_text("20일선이 올라가는 중입니다", 10))
    else:
        score -= 2
        negative_factors.append(factor_text("20일선이 아직 올라가는 모습은 아닙니다", -2))

    short_bull, short_bear = recent_cross_signal(
        dma5,
        dma20,
        factor_text("최근 5일선이 20일선을 상향 돌파했습니다", 2),
        factor_text("최근 5일선이 20일선을 하향 이탈했습니다", -4),
    )
    if short_bull:
        score += 2
        cross_highlights.append(f"{ticker} 최근 단기 골든크로스: 5일선이 20일선을 위로 돌파했습니다.")
        positive_factors.append(short_bull)
        reasons.append("최근 단기 골든크로스가 나왔습니다")
    if short_bear:
        score -= 4
        cross_highlights.append(f"{ticker} 최근 단기 데드크로스: 5일선이 20일선 아래로 내려갔습니다.")
        negative_factors.append(short_bear)
        reasons.append("최근 단기 데드크로스가 나왔습니다")

    mid_bull, mid_bear = recent_cross_signal(
        dma20,
        dma50,
        factor_text("최근 20일선이 50일선을 상향 돌파했습니다", 4),
        factor_text("최근 20일선이 50일선을 하향 이탈했습니다", -8),
        lookback=10,
    )
    if mid_bull:
        score += 4
        cross_highlights.append(f"{ticker} 최근 중기 골든크로스: 20일선이 50일선을 위로 돌파했습니다.")
        positive_factors.append(mid_bull)
        reasons.append("최근 중기 골든크로스가 나왔습니다")
    if mid_bear:
        score -= 8
        cross_highlights.append(f"{ticker} 최근 중기 데드크로스: 20일선이 50일선 아래로 내려갔습니다.")
        negative_factors.append(mid_bear)
        reasons.append("최근 중기 데드크로스가 나왔습니다")

    rs = (close / benchmark_df["Close"]).dropna()
    if len(rs) >= 20 and rs.iloc[-1] > rs.iloc[-20]:
        score += 15
        reasons.append("이 종목이 시장보다 더 잘 버팁니다")
        positive_factors.append(factor_text("시장보다 더 잘 버팁니다", 15))

    stk_ret20 = close.pct_change(20).iloc[-1] if len(close) >= 21 else 0
    benchmark_ret20 = benchmark_df["Close"].pct_change(20).iloc[-1] if len(benchmark_df["Close"]) >= 21 else 0
    if stk_ret20 > benchmark_ret20:
        score += 10
        positive_factors.append(factor_text("최근 한 달 흐름이 시장보다 좋습니다", 10))

    vol20 = vol.rolling(20).mean()
    has_strong_volume = bool(close.iloc[-1] > close.iloc[-2] and vol.iloc[-1] > vol20.iloc[-1])
    if has_strong_volume:
        score += 10
        positive_factors.append(factor_text("상승할 때 거래량이 평균보다 강했습니다", 10))

    up_days = stock_df[stock_df["Close"].pct_change() > 0]["Volume"].tail(20).mean()
    down_days = stock_df[stock_df["Close"].pct_change() < 0]["Volume"].tail(20).mean()
    if pd.notna(up_days) and pd.notna(down_days) and up_days > down_days:
        score += 5
        positive_factors.append(factor_text("최근에는 상승일 거래량이 더 우세했습니다", 5))

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
        positive_factors.append(factor_text("흔들림이 과하지 않습니다", 5))

    recent_5d = close.pct_change(5).iloc[-1] if len(close) >= 6 else 0
    overheated = recent_5d > 0.2
    if not overheated:
        score += 5
        positive_factors.append(factor_text("최근 너무 급하게 오른 상태는 아닙니다", 5))
    else:
        score -= 4
        negative_factors.append(factor_text("최근 단기 급등이 커서 추격 매수는 부담입니다", -4))

    event_flag = "특이 일정 없음"
    if earnings_soon is False:
        score += 5
        positive_factors.append(factor_text("가까운 실적 일정 부담이 없습니다", 5))
    elif earnings_soon is True:
        reasons.append("실적이 가까워 보수적으로 봐야 합니다")
        score -= 6
        negative_factors.append(factor_text("실적 발표가 가까워 보수적으로 봐야 합니다", -6))
        event_flag = "실적 7일 이내"
    elif neutral_missing_earnings:
        event_flag = "실적 미반영"
    else:
        score -= 4
        negative_factors.append(factor_text("실적 일정 확인이 안 돼서 조심해서 봐야 합니다", -4))
        event_flag = "실적 일정 확인 필요"

    rs_10d_weaker = bool(len(rs) >= 10 and rs.iloc[-1] < rs.iloc[-10])
    if close.iloc[-1] > dma20.iloc[-1] and vol.iloc[-1] < vol20.iloc[-1]:
        score -= 6
        reasons.append("거래량이 아직 약합니다")
        negative_factors.append(factor_text("거래량이 아직 약합니다", -6))
    if rs_10d_weaker:
        score -= 6
        reasons.append("최근 시장보다 힘이 약합니다")
        negative_factors.append(factor_text("시장보다 덜 강하게 움직입니다", -6))

    if close.iloc[-1] <= dma20.iloc[-1]:
        negative_factors.append(factor_text("종가가 20일선 아래에 있습니다", 0))
    if close.iloc[-1] <= dma50.iloc[-1]:
        negative_factors.append(factor_text("종가가 50일선 아래에 있습니다", 0))
    if dma20.iloc[-1] <= dma50.iloc[-1]:
        negative_factors.append(factor_text("짧은 흐름이 중간 흐름보다 약합니다", 0))
    if not slope_up(dma20):
        negative_factors.append(factor_text("20일선이 아직 올라가는 모습은 아닙니다", 0))
    if len(rs) >= 20 and rs.iloc[-1] <= rs.iloc[-20]:
        negative_factors.append(factor_text("최근 한 달 흐름이 시장보다 약했습니다", 0))
    if stk_ret20 <= benchmark_ret20:
        negative_factors.append(factor_text("최근 한 달 수익률이 시장보다 약합니다", 0))
    if not has_strong_volume:
        negative_factors.append(factor_text("거래량이 강하게 붙는 모습은 아직 부족합니다", 0))
    if not (pd.notna(up_days) and pd.notna(down_days) and up_days > down_days):
        negative_factors.append(factor_text("오를 때 거래량이 뚜렷하게 붙지 않았습니다", 0))
    if atr_ratio >= 0.06:
        negative_factors.append(factor_text("움직임이 커서 흔들릴 수 있습니다", 0))

    score = int(max(0, min(100, round(score))))
    s_state = stock_state(score)
    action = combined_action(market_lvl, s_state)
    if earnings_soon is True or (earnings_soon is None and not neutral_missing_earnings) or overheated:
        if action == "매수 가능":
            action = "소규모 매수"
        elif action == "선별 매수":
            action = "관찰"

    easy = (
        "이 종목은 관심종목 안에서 비교적 괜찮은 편입니다. 다만 한 번에 크게 들어가기보다 차분히 접근하는 편이 좋습니다."
        if s_state in {"강함", "양호"}
        else "지금은 확실히 강하다고 보기 어렵습니다. 서두르기보다 조금 더 지켜보는 편이 좋습니다."
    )
    reasons = prioritize_stock_reasons(reasons, s_state)
    note = summarize_stock_note(score, s_state, reasons, earnings_soon, overheated)
    return {
        "ticker": ticker,
        "stock_score": score,
        "stock_state": s_state,
        "final_action": action,
        "top_reasons": reasons[:3] if reasons else ["뚜렷하게 강하다고 보긴 어렵습니다"],
        "invalidation": "20일선 아래로 밀리고 시장보다 덜 강하게 움직이면 더 보수적으로 봐야 합니다.",
        "easy_explanation": easy,
        "note": note,
        "cross_highlights": cross_highlights[:2],
        "event_flag": event_flag,
        "earnings_date": earnings_date.isoformat() if earnings_date else None,
        "earnings_date_label": earnings_date.strftime("%Y-%m-%d") if earnings_date else "미확인",
        "earnings_soon": None if earnings_soon is None else bool(earnings_soon),
        "overheated": bool(overheated),
        "positive_factors": positive_factors[:6],
        "negative_factors": negative_factors[:6],
        "metrics": {
            "close": float(close.iloc[-1]),
            "close_change_pct": pct_change_from_prev_close(close),
            "dma5": float(dma5.iloc[-1]) if pd.notna(dma5.iloc[-1]) else None,
            "dma20": float(dma20.iloc[-1]) if pd.notna(dma20.iloc[-1]) else None,
            "dma50": float(dma50.iloc[-1]) if pd.notna(dma50.iloc[-1]) else None,
            "volume_ratio_20d": float(vol.iloc[-1] / vol20.iloc[-1]) if pd.notna(vol20.iloc[-1]) else None,
            "atr_ratio": atr_ratio,
            "rs_20d_change": float(rs.iloc[-1] / rs.iloc[-20] - 1) if len(rs) >= 20 else None,
        },
        "series": {
            "dates": [d.strftime("%Y-%m-%d") for d in close.tail(120).index],
            "close": [float(v) for v in close.tail(120).tolist()],
            "volume": [float(v) for v in vol.tail(120).tolist()],
            "volume_dma20": [None if pd.isna(v) else float(v) for v in vol.rolling(20).mean().tail(120).tolist()],
            "dma5": [None if pd.isna(v) else float(v) for v in dma5.tail(120).tolist()],
            "dma20": [None if pd.isna(v) else float(v) for v in dma20.tail(120).tolist()],
            "dma50": [None if pd.isna(v) else float(v) for v in dma50.tail(120).tolist()],
            "rs": [float(v) for v in rs.tail(120).tolist()],
        },
    }


def summarize_stock_note(score: int, state: str, reasons: list[str], earnings_soon: bool, overheated: bool) -> str:
    if earnings_soon:
        return "지금은 보수적으로 보는 편이 좋습니다. 이유: 곧 실적 발표가 있습니다."
    if overheated:
        return "지금 바로 따라 사기엔 부담이 있습니다. 이유: 최근에 너무 빨리 올랐습니다."
    if state in {"강함", "양호"}:
        base = "관심 있게 볼 만합니다."
    elif state == "애매":
        base = "아직 확실하진 않습니다."
    elif state == "약함":
        base = "지금 서두를 필요는 없어 보입니다."
    else:
        base = "지금은 굳이 들어갈 이유가 약합니다."
    reason_text = pick_note_reason(reasons, state) or default_reason_for_state(state)
    return f"{base} 이유: {reason_text}."


def pick_note_reason(reasons: list[str], state: str) -> str | None:
    if not reasons:
        return None

    weak_generic = {"20일선 위에 있습니다", "50일선 위에 있습니다"}
    if state in {"약함", "회피"}:
        preferred = [
            "최근 중기 데드크로스가 나왔습니다",
            "최근 단기 데드크로스가 나왔습니다",
            "실적이 가까워 보수적으로 봐야 합니다",
            "실적 발표가 가까워 보수적으로 봐야 합니다",
            "거래량이 아직 약합니다",
            "최근 시장보다 힘이 약합니다",
            "최근 단기 급등이 커서 추격 매수는 부담입니다",
            "최근 한 달 흐름이 시장보다 약합니다",
            "최근 한 달 수익률이 시장보다 약합니다",
            "짧은 흐름이 중간 흐름보다 약합니다",
            "종가가 20일선 아래에 있습니다",
            "종가가 50일선 아래에 있습니다",
        ]
        for needle in preferred:
            match = next((reason for reason in reasons if needle in reason), None)
            if match:
                return translate_reason(match)
        for reason in reasons:
            if reason not in weak_generic:
                return translate_reason(reason)
        return None

    preferred = [
        "최근 중기 골든크로스가 나왔습니다",
        "최근 단기 골든크로스가 나왔습니다",
            "이 종목이 시장보다 더 잘 버팁니다",
            "최근 한 달 흐름이 시장보다 좋습니다",
            "상승할 때 거래량이 평균보다 강했습니다",
            "최근에는 상승일 거래량이 더 우세했습니다",
            "짧은 흐름이 중간 흐름보다 좋습니다",
            "20일선이 올라가는 중입니다",
            "50일선 위에 있습니다",
            "20일선 위에 있습니다",
    ]
    for needle in preferred:
        match = next((reason for reason in reasons if needle in reason), None)
        if match:
            return translate_reason(match)
    return translate_reason(reasons[0])


def translate_reason(reason: str) -> str:
    mapping = {
        "20일선 위에 있습니다": "20일선 위에 있습니다",
        "50일선 위에 있습니다": "50일선 위에 있습니다",
        "짧은 흐름이 중간 흐름보다 좋습니다": "짧은 흐름이 중간 흐름보다 좋습니다",
        "20일선이 올라가는 중입니다": "20일선이 올라가는 중입니다",
        "종가가 20일선 아래에 있습니다": "20일선 아래에 있습니다",
        "종가가 50일선 아래에 있습니다": "50일선 아래에 있습니다",
        "거래량이 아직 약합니다": "거래량이 아직 약합니다",
        "최근 시장보다 힘이 약합니다": "최근 시장보다 힘이 약합니다",
        "이 종목이 시장보다 더 잘 버팁니다": "이 종목이 시장보다 더 잘 버팁니다",
        "최근 중기 골든크로스가 나왔습니다": "최근 중기 골든크로스가 나왔습니다",
        "최근 단기 골든크로스가 나왔습니다": "최근 단기 골든크로스가 나왔습니다",
        "최근 중기 데드크로스가 나왔습니다": "최근 중기 데드크로스가 나왔습니다",
        "최근 단기 데드크로스가 나왔습니다": "최근 단기 데드크로스가 나왔습니다",
        "최근 한 달 흐름이 시장보다 좋습니다": "최근 한 달 흐름이 시장보다 좋습니다",
        "최근 한 달 수익률이 시장보다 약합니다": "최근 한 달 수익률이 시장보다 약합니다",
        "상승할 때 거래량이 평균보다 강했습니다": "상승할 때 거래량이 평균보다 강했습니다",
        "최근에는 상승일 거래량이 더 우세했습니다": "최근에는 상승일 거래량이 더 우세했습니다",
        "최근 한 달 흐름이 시장보다 약합니다": "최근 한 달 흐름이 시장보다 약합니다",
        "실적이 가까워 보수적으로 봐야 합니다": "실적이 가까워 보수적으로 봐야 합니다",
        "뚜렷하게 강하다고 보긴 어렵습니다": "뚜렷하게 강하다고 보긴 어렵습니다",
    }
    return mapping.get(reason, reason)


def default_reason_for_state(state: str) -> str:
    mapping = {
        "강함": "가격 흐름이 비교적 안정적입니다",
        "양호": "흐름이 나쁘지 않습니다",
        "애매": "강하다고 보기엔 아직 부족합니다",
        "약함": "주가 흐름이 약합니다",
        "회피": "지금은 좋은 진입 신호가 부족합니다",
    }
    return mapping.get(state, "판단할 만한 신호가 아직 부족합니다")


def get_earnings_info(ticker: str, as_of: date, manual_calendar: dict[str, date]) -> tuple[bool | None, date | None]:
    manual_date = manual_calendar.get(ticker.upper())
    if manual_date:
        delta = (manual_date - as_of).days
        return (0 <= delta <= 7, manual_date)
    if ticker.endswith("XX") or ticker in {"SPY", "QQQ", "RSP", "HYG", "UUP", "SOXX", "KORU", "^GSPC", "^IXIC", "^VIX"}:
        return (False, None)
    try:
        cal = yf.Ticker(ticker).calendar
        if cal is None or cal.empty:
            return (None, None)
        raw_date = cal.loc["Earnings Date"].iloc[0]
        if pd.isna(raw_date):
            return (None, None)
        earn_date = pd.Timestamp(raw_date).date()
        delta = (earn_date - as_of).days
        return (0 <= delta <= 7, earn_date)
    except Exception:
        return (None, None)


def compact_signed(value: int) -> str:
    return f"{value:+d}" if value else "0"


def score_history_tags(entries: list[dict]) -> list[str]:
    if not entries:
        return []
    tags = []
    if len(entries) >= 2:
        tags.append(f"1일 점수 {compact_signed(entries[-1]['score'] - entries[-2]['score'])}")
    if len(entries) >= 6:
        tags.append(f"5일 점수 {compact_signed(entries[-1]['score'] - entries[-6]['score'])}")
    if len(entries) >= 21:
        tags.append(f"20일 점수 {compact_signed(entries[-1]['score'] - entries[-21]['score'])}")
    window = entries[-30:]
    if window:
        tags.append(f"30일 최고 {max(x['score'] for x in window)}")
    return tags[:4]


def update_history(history: dict, output: dict, as_of: date) -> dict:
    date_key = as_of.strftime("%Y-%m-%d")
    market_entries = [x for x in history.get("market", []) if x.get("date") != date_key]
    market_entries.append({"date": date_key, "score": output["market"]["score"], "level": output["market"]["state"]})
    market_entries = market_entries[-30:]

    stock_history = history.get("stocks", {})
    next_stock_history = {}
    for stock in output["stocks"]:
        ticker = stock["ticker"]
        entries = [x for x in stock_history.get(ticker, []) if x.get("date") != date_key]
        entries.append({"date": date_key, "score": stock["stock_score"], "state": stock["stock_state"]})
        next_stock_history[ticker] = entries[-30:]
    return {"market": market_entries, "stocks": next_stock_history}


def market_exposure_band(level: int) -> str:
    return {
        6: "총 노출 80~100%",
        5: "총 노출 60~80%",
        4: "총 노출 30~50%",
        3: "총 노출 10~30%",
        2: "총 노출 0~15%",
        1: "총 노출 0~5%",
    }[level]


def market_position_tags(level: int, event_risk: bool) -> list[str]:
    tags = [market_exposure_band(level)]
    if level >= 5:
        tags.append("강한 종목 선별 접근")
    elif level == 4:
        tags.append("소규모 분할 진입")
    else:
        tags.append("현금 비중 높게 유지")
    if event_risk:
        tags.append("이벤트 전 레버리지 자제")
    return tags


def stock_position_tags(market_lvl: int, stock_state_value: str, earnings_soon: bool | None, overheated: bool) -> list[str]:
    if market_lvl <= 2:
        base = "권장 비중 0~2%"
    elif market_lvl == 3:
        base = "권장 비중 1~3%"
    elif market_lvl == 4:
        base = "권장 비중 2~5%"
    elif stock_state_value == "강함":
        base = "권장 비중 4~8%"
    elif stock_state_value == "양호":
        base = "권장 비중 3~6%"
    else:
        base = "권장 비중 0~3%"
    tags = [base, "분할 2~3회 접근"]
    if earnings_soon is True:
        tags.append("실적 전 비중 축소")
    if overheated:
        tags.append("추격 매수 금지")
    return tags[:3]


def market_change_tags(previous_output: dict, current_market: dict) -> list[str]:
    if not previous_output:
        return ["첫 생성 데이터"]
    prev_market = previous_output.get("market", {})
    tags = []
    prev_score = prev_market.get("score")
    if isinstance(prev_score, int):
        tags.append(f"점수 {compact_signed(current_market['score'] - prev_score)}")
    prev_state = prev_market.get("state")
    if prev_state and prev_state != current_market["state"]:
        tags.append(f"레벨 변화: {prev_state} -> {current_market['state']}")
    elif prev_state:
        tags.append("레벨 변화 없음")
    prev_vix = prev_market.get("metrics", {}).get("vix_change_pct")
    curr_vix = current_market.get("metrics", {}).get("vix_change_pct")
    if isinstance(curr_vix, (int, float)):
        tags.append(f"VIX 일간 {curr_vix:+.2f}%")
    return tags[:4]


def stock_change_tags(previous_output: dict, stock: dict) -> list[str]:
    if not previous_output:
        return ["첫 생성 데이터"]
    previous_stock = next((x for x in previous_output.get("stocks", []) if x.get("ticker") == stock["ticker"]), None)
    if not previous_stock:
        return ["첫 생성 데이터"]
    tags = [f"점수 {compact_signed(stock['stock_score'] - previous_stock.get('stock_score', stock['stock_score']))}"]
    if previous_stock.get("stock_state") != stock["stock_state"]:
        tags.append(f"상태 변화: {previous_stock.get('stock_state')} -> {stock['stock_state']}")
    if previous_stock.get("final_action") != stock["final_action"]:
        tags.append(f"행동 변화: {previous_stock.get('final_action')} -> {stock['final_action']}")
    return tags[:3]


def market_alert_tags(market_output: dict) -> list[str]:
    alerts = []
    if market_output["negative_filters"]["filter_3_high_stress"]:
        alerts.append("고스트레스 구간")
    if market_output["negative_filters"]["filter_4_event_risk"]:
        alerts.append(f"{', '.join(market_output['negative_filters']['event_names'])} 경계")
    if any("데드크로스" in x for x in market_output.get("cross_highlights", [])):
        alerts.append("데드크로스 확인")
    elif any("골든크로스" in x for x in market_output.get("cross_highlights", [])):
        alerts.append("골든크로스 확인")
    if market_output["score"] <= 39:
        alerts.append("방어 모드 유지")
    return alerts[:4]


def stock_alert_tags(stock: dict) -> list[str]:
    alerts = []
    if stock["event_flag"] == "실적 7일 이내":
        alerts.append("실적 임박")
    if any("데드크로스" in x for x in stock.get("cross_highlights", [])):
        alerts.append("데드크로스 발생")
    elif any("골든크로스" in x for x in stock.get("cross_highlights", [])):
        alerts.append("골든크로스 발생")
    if stock["stock_score"] >= 70:
        alerts.append("상위 점수권")
    if "회피" in stock["final_action"]:
        alerts.append("신규 진입 자제")
    return alerts[:4]


def sector_strength_label(close: pd.Series) -> str:
    dma50 = close.rolling(50).mean()
    ret20 = close.pct_change(20).iloc[-1] if len(close) >= 21 else 0
    above50 = bool(pd.notna(dma50.iloc[-1]) and close.iloc[-1] > dma50.iloc[-1])
    if above50 and ret20 > 0.03:
        return "강함"
    if above50 or ret20 > 0:
        return "보통"
    return "약함"


def sector_display_name(label: str) -> str:
    return {
        "SOXX": "SOXX (반도체)",
        "XLK": "XLK (기술)",
        "XLF": "XLF (금융)",
        "XLY": "XLY (소비재)",
    }.get(label, label)


def sector_tags(sector_map: dict[str, pd.DataFrame]) -> list[dict]:
    tags = []
    for label, df in sector_map.items():
        if df.empty or "Close" not in df.columns:
            continue
        change_pct = pct_change_from_prev_close(df["Close"])
        tags.append(
            {
                "name": sector_display_name(label),
                "status": sector_strength_label(df["Close"]),
                "change_pct": change_pct,
            }
        )
    return tags


def market_confidence_warnings(sp500_count: int, dxy_source: str, stock_reports: list[dict]) -> list[str]:
    warnings = []
    if sp500_count < 450:
        warnings.append(f"Breadth 표본 축소: {sp500_count}종목")
    if dxy_source != "DX-Y.NYB":
        warnings.append("달러지수 대체값 사용")
    unknown_earnings = sum(1 for stock in stock_reports if stock["event_flag"] == "실적 일정 확인 필요")
    if unknown_earnings:
        warnings.append(f"실적 일정 확인 필요 {unknown_earnings}종목")
    return warnings[:4]


def stock_confidence_warnings(stock: dict) -> list[str]:
    warnings = []
    if stock["event_flag"] == "실적 일정 확인 필요":
        warnings.append("실적 일정 확인 필요")
    volume_ratio_20d = stock["metrics"].get("volume_ratio_20d")
    if isinstance(volume_ratio_20d, float) and volume_ratio_20d < 0.85:
        warnings.append("거래량 약함")
    rs_change = stock["metrics"].get("rs_20d_change")
    if isinstance(rs_change, float) and rs_change < 0:
        warnings.append("시장 대비 약세")
    return warnings[:4]


def parse_output_date(output: dict) -> date | None:
    raw = output.get("market_data_as_of") or output.get("generated_at_et")
    if not raw:
        return None
    try:
        return datetime.strptime(str(raw)[:10], "%Y-%m-%d").date()
    except Exception:
        return None


def state_rank(state_value: str) -> int:
    return {
        "강함": 4,
        "양호": 3,
        "애매": 2,
        "약함": 1,
        "회피": 0,
    }.get(state_value, 0)


def build_notification(
    notification_id: str,
    priority: str,
    kind: str,
    title: str,
    message: str,
    scope: str = "market",
    ticker: str | None = None,
) -> dict:
    item = {
        "id": notification_id,
        "priority": priority,
        "kind": kind,
        "scope": scope,
        "title": title,
        "message": message,
    }
    if ticker:
        item["ticker"] = ticker
    return item


def build_notifications(as_of: date, previous_output: dict, market_output: dict, stock_reports: list[dict]) -> list[dict]:
    notifications: list[dict] = []
    current_level = market_level(market_output["score"])
    prev_market = previous_output.get("market", {}) if previous_output else {}
    prev_level = market_level(prev_market["score"]) if isinstance(prev_market.get("score"), int) else None
    prev_metrics = prev_market.get("metrics", {}) if isinstance(prev_market, dict) else {}
    prev_filters = prev_market.get("negative_filters", {}) if isinstance(prev_market, dict) else {}
    prev_output_date = parse_output_date(previous_output) if previous_output else None

    if prev_level is not None and current_level != prev_level:
        direction = "하락" if current_level < prev_level else "회복"
        priority = "high" if current_level < prev_level else "medium"
        message = (
            f"시장 레벨이 {prev_level}/{MARKET_LEVELS_TOTAL}에서 {current_level}/{MARKET_LEVELS_TOTAL}로 {direction}했습니다. "
            f"현재 추천 행동은 '{market_output['action']}'입니다."
        )
        notifications.append(
            build_notification(
                f"market-level-{direction}-{as_of.isoformat()}",
                priority,
                "market_level_change",
                f"시장 레벨 {direction}",
                message,
            )
        )

    current_high_stress = bool(market_output["negative_filters"]["filter_3_high_stress"])
    prev_high_stress = bool(prev_filters.get("filter_3_high_stress"))
    if current_high_stress and not prev_high_stress:
        notifications.append(
            build_notification(
                f"market-high-stress-{as_of.isoformat()}",
                "high",
                "market_high_stress",
                "고스트레스 구간 진입",
                "VIX가 높은 구간으로 올라왔습니다. 신규 진입은 더 보수적으로 보는 편이 좋습니다.",
            )
        )

    current_both_below = bool(
        market_output["metrics"]["spx_close"] < market_output["metrics"]["spx_dma200"]
        and market_output["metrics"]["ndx_close"] < market_output["metrics"]["ndx_dma200"]
    )
    prev_both_below = bool(
        prev_metrics
        and prev_metrics.get("spx_close") is not None
        and prev_metrics.get("spx_dma200") is not None
        and prev_metrics.get("ndx_close") is not None
        and prev_metrics.get("ndx_dma200") is not None
        and prev_metrics["spx_close"] < prev_metrics["spx_dma200"]
        and prev_metrics["ndx_close"] < prev_metrics["ndx_dma200"]
    )
    if current_both_below and not prev_both_below:
        notifications.append(
            build_notification(
                f"market-both-below-200dma-{as_of.isoformat()}",
                "high",
                "market_below_200dma",
                "핵심 지수 200일선 이탈",
                "S&P500과 Nasdaq이 모두 200일선 아래에 있습니다. 방어적으로 보는 편이 좋습니다.",
            )
        )

    current_event_names = market_output["negative_filters"].get("event_names", [])
    prev_event_names = prev_filters.get("event_names", [])
    if market_output["negative_filters"]["filter_4_event_risk"] and current_event_names != prev_event_names:
        notifications.append(
            build_notification(
                f"market-event-risk-{as_of.isoformat()}",
                "high",
                "market_event_risk",
                "중요 일정 임박",
                f"{', '.join(current_event_names)} 일정이 가까워졌습니다. 변동성이 커질 수 있어 보수적으로 보는 편이 좋습니다.",
            )
        )

    current_warnings = market_output.get("confidence_warnings", [])
    prev_warnings = prev_market.get("confidence_warnings", []) if isinstance(prev_market, dict) else []
    if current_warnings and current_warnings != prev_warnings:
        notifications.append(
            build_notification(
                f"market-data-warning-{as_of.isoformat()}",
                "medium",
                "data_warning",
                "데이터 확인 필요",
                f"데이터 주의 항목: {', '.join(current_warnings)}",
            )
        )

    previous_stock_map = {
        stock.get("ticker"): stock for stock in previous_output.get("stocks", [])
    } if previous_output else {}
    buy_actions = {"매수 가능", "선별 매수", "소규모 매수"}

    for stock in stock_reports:
        ticker = stock["ticker"]
        previous_stock = previous_stock_map.get(ticker, {})
        prev_state = previous_stock.get("stock_state")
        current_state = stock["stock_state"]
        prev_action = previous_stock.get("final_action", "")
        current_action = stock["final_action"]

        if (
            stock["stock_score"] >= 70
            and current_level >= 4
            and current_action in buy_actions
            and not (
                previous_stock
                and previous_stock.get("stock_score", 0) >= 70
                and prev_action in buy_actions
            )
        ):
            notifications.append(
                build_notification(
                    f"stock-entry-{ticker}-{as_of.isoformat()}",
                    "medium",
                    "stock_entry_candidate",
                    f"{ticker} 진입 후보",
                    f"{ticker}가 {stock['stock_score']}/100으로 올라왔고 추천 행동은 '{current_action}'입니다.",
                    scope="stock",
                    ticker=ticker,
                )
            )

        if prev_state and state_rank(prev_state) >= 3 and state_rank(current_state) <= 2:
            notifications.append(
                build_notification(
                    f"stock-weakened-{ticker}-{as_of.isoformat()}",
                    "medium",
                    "stock_weakened",
                    f"{ticker} 상태 약화",
                    f"{ticker} 상태가 {prev_state}에서 {current_state}(으)로 약해졌습니다. 지금은 더 보수적으로 보는 편이 좋습니다.",
                    scope="stock",
                    ticker=ticker,
                )
            )

        earnings_date_raw = stock.get("earnings_date")
        if earnings_date_raw:
            try:
                earnings_date = datetime.strptime(earnings_date_raw, "%Y-%m-%d").date()
            except Exception:
                earnings_date = None
            if earnings_date:
                current_delta = (earnings_date - as_of).days
                prev_delta = None
                if prev_output_date:
                    prev_delta = (earnings_date - prev_output_date).days
                if 0 <= current_delta <= 3 and (prev_delta is None or prev_delta > 3):
                    notifications.append(
                        build_notification(
                            f"stock-earnings-near-{ticker}-{as_of.isoformat()}",
                            "medium",
                            "stock_earnings_near",
                            f"{ticker} 실적 임박",
                            f"{ticker} 실적발표일이 {stock['earnings_date_label']}로 가까워졌습니다. 신규 진입은 더 보수적으로 보는 편이 좋습니다.",
                            scope="stock",
                            ticker=ticker,
                        )
                    )

        current_crosses = set(stock.get("cross_highlights", []))
        prev_crosses = set(previous_stock.get("cross_highlights", [])) if previous_stock else set()
        new_crosses = [item for item in current_crosses if item not in prev_crosses]
        for cross in new_crosses:
            if "데드크로스" in cross:
                notifications.append(
                    build_notification(
                        f"stock-dead-cross-{ticker}-{as_of.isoformat()}",
                        "medium",
                        "stock_dead_cross",
                        f"{ticker} 데드크로스",
                        cross,
                        scope="stock",
                        ticker=ticker,
                    )
                )
                break
            if "골든크로스" in cross and current_level >= 4 and stock["stock_score"] >= 65:
                notifications.append(
                    build_notification(
                        f"stock-golden-cross-{ticker}-{as_of.isoformat()}",
                        "low",
                        "stock_golden_cross",
                        f"{ticker} 골든크로스",
                        cross,
                        scope="stock",
                        ticker=ticker,
                    )
                )
                break

    priority_rank = {"high": 0, "medium": 1, "low": 2}
    notifications.sort(key=lambda item: (priority_rank.get(item["priority"], 9), item["title"]))
    return notifications[:8]


def main() -> None:
    now_et = datetime.now(tz=ET)
    as_of = now_et.date()
    previous_output = load_json(OUTPUT_PATH)
    existing_history = load_json(HISTORY_PATH)

    watchlist = load_yaml(WATCHLIST_PATH).get("watchlist", [])
    if len(watchlist) != 8:
        raise ValueError("watchlist.yml must contain exactly 8 tickers.")

    latest_intraday_points: list[datetime] = []

    spx, ts = load_price_frame("^GSPC", now_et)
    if ts:
        latest_intraday_points.append(ts)
    ndx, ts = load_price_frame("^IXIC", now_et)
    if ts:
        latest_intraday_points.append(ts)
    rut, ts = load_price_frame("^RUT", now_et)
    if ts:
        latest_intraday_points.append(ts)
    tnx, ts = load_price_frame("^TNX", now_et)
    if ts:
        latest_intraday_points.append(ts)
    spy_proxy, ts = load_price_frame("SPY", now_et)
    if ts:
        latest_intraday_points.append(ts)
    qqq_proxy, ts = load_price_frame("QQQ", now_et)
    if ts:
        latest_intraday_points.append(ts)
    rsp, ts = load_price_frame("RSP", now_et)
    if ts:
        latest_intraday_points.append(ts)
    hyg, ts = load_price_frame("HYG", now_et)
    if ts:
        latest_intraday_points.append(ts)
    soxx, ts = load_price_frame("SOXX", now_et)
    if ts:
        latest_intraday_points.append(ts)
    xlk, ts = load_price_frame("XLK", now_et)
    if ts:
        latest_intraday_points.append(ts)
    xlf, ts = load_price_frame("XLF", now_et)
    if ts:
        latest_intraday_points.append(ts)
    xly, ts = load_price_frame("XLY", now_et)
    if ts:
        latest_intraday_points.append(ts)
    vix, ts = load_price_frame("^VIX", now_et)
    if ts:
        latest_intraday_points.append(ts)
    dxy_source = "DX-Y.NYB"
    try:
        dxy, ts = load_price_frame("DX-Y.NYB", now_et)
        if ts:
            latest_intraday_points.append(ts)
        if dxy.empty:
            dxy_source = "UUP"
            dxy, ts = load_price_frame("UUP", now_et)
            if ts:
                latest_intraday_points.append(ts)
    except Exception:
        dxy_source = "UUP"
        dxy, ts = load_price_frame("UUP", now_et)
        if ts:
            latest_intraday_points.append(ts)

    sp500_close = download_sp500_prices()
    sp500_close = sp500_close.dropna(axis=1, how="all")
    sp500_ret = sp500_close.pct_change()
    ad_daily = (sp500_ret > 0).sum(axis=1) - (sp500_ret < 0).sum(axis=1)
    ad_line = ad_daily.fillna(0).cumsum()

    pct_above_20 = ((sp500_close.iloc[-1] > sp500_close.rolling(20).mean().iloc[-1]).mean() * 100.0)
    pct_above_50 = ((sp500_close.iloc[-1] > sp500_close.rolling(50).mean().iloc[-1]).mean() * 100.0)
    pct_above_20_prev = ((sp500_close.iloc[-2] > sp500_close.rolling(20).mean().iloc[-2]).mean() * 100.0)
    rsp_spx = (rsp["Close"] / spx["Close"]).dropna()

    events = load_events(as_of)
    earnings_calendar = load_earnings_calendar()
    market_data = {"SPX": spx, "NDX": ndx, "RUT": rut, "TNX": tnx, "SPY_PROXY": spy_proxy, "QQQ_PROXY": qqq_proxy, "RSP": rsp, "HYG": hyg, "DXY": dxy, "VIX": vix}
    breadth = {
        "pct_above_20dma": float(pct_above_20),
        "pct_above_50dma": float(pct_above_50),
        "pct_above_20dma_change": float(pct_above_20 - pct_above_20_prev),
        "adline_available": bool(len(ad_line) >= 6),
        "adline_5d_up": bool(len(ad_line) >= 6 and ad_line.iloc[-1] > ad_line.iloc[-6]),
        "rsp_spy_available": bool(len(rsp_spx) >= 20),
        "rsp_spy_ratio_20d_up_or_flat": bool(len(rsp_spx) >= 20 and rsp_spx.iloc[-1] >= rsp_spx.iloc[-20]),
    }
    market = score_market(as_of, market_data, breadth, events)
    lvl = market_level(market.score)

    event_risk, event_names = is_event_d0_d1(as_of, events)
    execution_strength = "좋음"
    if event_risk:
        execution_strength = "매우 보수적"
    elif lvl <= 3:
        execution_strength = "보수적"
    elif lvl == 4:
        execution_strength = "보통"

    stock_reports = []
    for ticker in watchlist:
        sdf, ts = load_price_frame(ticker, now_et)
        if ts:
            latest_intraday_points.append(ts)
        earnings_soon, earnings_date = get_earnings_info(ticker, as_of, earnings_calendar)
        stock_reports.append(score_stock(ticker, sdf, spx, lvl, earnings_soon, earnings_date))

    for stock in stock_reports:
        stock["change_tags"] = stock_change_tags(previous_output, stock)
        stock["position_tags"] = stock_position_tags(lvl, stock["stock_state"], stock.get("earnings_soon"), stock.get("overheated", False))
        stock["alerts"] = stock_alert_tags(stock)
        stock["confidence_warnings"] = stock_confidence_warnings(stock)

    summary_table = [
        {
            "ticker": s["ticker"],
            "stock_score": s["stock_score"],
            "stock_state": s["stock_state"],
            "final_action": s["final_action"],
            "note": s["note"],
            "close": s["metrics"]["close"],
            "close_change_pct": s["metrics"]["close_change_pct"],
        }
        for s in stock_reports
    ]

    market_output = {
        "state": market.state,
        "score": market.score,
        "confidence": market.confidence,
        "execution_strength": execution_strength,
        "action": market.action,
        "top_reasons": market.reasons,
        "cross_highlights": market.cross_highlights,
        "positive_factors": market.positive_factors,
        "negative_factors": market.negative_factors,
        "invalidation": market.invalidation,
        "easy_explanation": market.easy_explanation,
        "negative_filters": {
            "filter_1_divergence": close_true(spx) and (not breadth["adline_5d_up"] or breadth["pct_above_20dma_change"] < 0),
            "filter_2_bigcap_only": bool(len(rsp_spx) >= 20 and rsp_spx.iloc[-1] < rsp_spx.iloc[-20]),
            "filter_3_high_stress": percentile_rank(vix["Close"]) > 85,
            "filter_4_event_risk": event_risk,
            "event_names": event_names,
        },
        "metrics": {
            "spx_close": float(spx["Close"].iloc[-1]),
            "spx_change_pct": pct_change_from_prev_close(spx["Close"]),
            "spx_dma200": float(spx["Close"].rolling(200).mean().iloc[-1]),
            "ndx_close": float(ndx["Close"].iloc[-1]),
            "ndx_change_pct": pct_change_from_prev_close(ndx["Close"]),
            "ndx_dma200": float(ndx["Close"].rolling(200).mean().iloc[-1]),
            "rut_close": float(rut["Close"].iloc[-1]),
            "rut_change_pct": pct_change_from_prev_close(rut["Close"]),
            "vix_close": float(vix["Close"].iloc[-1]),
            "vix_change_pct": pct_change_from_prev_close(vix["Close"]),
            "tnx_close": float(tnx["Close"].iloc[-1]),
            "tnx_change_pct": pct_change_from_prev_close(tnx["Close"]),
            "pct_above_20dma": breadth["pct_above_20dma"],
            "pct_above_50dma": breadth["pct_above_50dma"],
            "vix_percentile": percentile_rank(vix["Close"]),
            "dxy_20d_zscore": zscore(dxy["Close"], 20),
            "tnx_20d_zscore": zscore(tnx["Close"], 20),
        },
    }
    market_output["change_tags"] = market_change_tags(previous_output, market_output)
    market_output["position_tags"] = market_position_tags(lvl, event_risk)
    market_output["alerts"] = market_alert_tags(market_output)
    market_output["sector_tags"] = sector_tags({"SOXX": soxx, "XLK": xlk, "XLF": xlf, "XLY": xly})
    market_output["confidence_warnings"] = market_confidence_warnings(sp500_close.shape[1], dxy_source, stock_reports)

    latest_intraday_at = max(latest_intraday_points) if latest_intraday_points else None
    intraday_mode = latest_intraday_at is not None and latest_intraday_at.date() == now_et.date()

    output = {
        "generated_at_et": now_et.strftime("%Y-%m-%d %H:%M ET"),
        "market_data_as_of": (
            f"{latest_intraday_at.strftime('%Y-%m-%d %H:%M ET')} (5분봉)"
            if intraday_mode
            else f"{spx.index[-1].strftime('%Y-%m-%d')} 16:00 ET (Close)"
        ),
        "market": market_output,
        "watchlist_summary": summary_table,
        "stocks": stock_reports,
        "charts": {
            "market": {
                "dates": [d.strftime("%Y-%m-%d") for d in spx["Close"].tail(63).index],
                "spx_close": [float(v) for v in spx["Close"].tail(63).tolist()],
                "spx_dma20": [None if pd.isna(v) else float(v) for v in spx["Close"].rolling(20).mean().tail(63).tolist()],
                "spx_dma50": [None if pd.isna(v) else float(v) for v in spx["Close"].rolling(50).mean().tail(63).tolist()],
                "spx_dma200": [None if pd.isna(v) else float(v) for v in spx["Close"].rolling(200).mean().tail(63).tolist()],
                "ndx_close": [float(v) for v in ndx["Close"].tail(63).tolist()],
                "ndx_dma20": [None if pd.isna(v) else float(v) for v in ndx["Close"].rolling(20).mean().tail(63).tolist()],
                "ndx_dma50": [None if pd.isna(v) else float(v) for v in ndx["Close"].rolling(50).mean().tail(63).tolist()],
                "ndx_dma200": [None if pd.isna(v) else float(v) for v in ndx["Close"].rolling(200).mean().tail(63).tolist()],
                "rut_close": [float(v) for v in rut["Close"].tail(63).tolist()],
                "breadth_20": [float(v) for v in ((sp500_close > sp500_close.rolling(20).mean()).mean(axis=1) * 100).tail(63).tolist()],
                "breadth_50": [float(v) for v in ((sp500_close > sp500_close.rolling(50).mean()).mean(axis=1) * 100).tail(63).tolist()],
                "vix_close": [float(v) for v in vix["Close"].tail(63).tolist()],
                "hyg_close": [float(v) for v in hyg["Close"].tail(63).tolist()],
                "tnx_close": [float(v) for v in tnx["Close"].tail(63).tolist()],
                "dxy_close": [float(v) for v in dxy["Close"].tail(63).tolist()],
            }
        },
    }
    output["notifications"] = {
        "count": 0,
        "items": [],
    }
    output["notifications"]["items"] = build_notifications(as_of, previous_output, market_output, stock_reports)
    output["notifications"]["count"] = len(output["notifications"]["items"])

    history = update_history(existing_history, output, as_of)
    output["market"]["history_tags"] = score_history_tags(history.get("market", []))
    for stock in output["stocks"]:
        stock["history_tags"] = score_history_tags(history.get("stocks", {}).get(stock["ticker"], []))
    output["history"] = history

    DOCS_DATA_DIR.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    with HISTORY_PATH.open("w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)


def close_true(spy: pd.DataFrame) -> bool:
    return bool(len(spy["Close"]) >= 2 and spy["Close"].iloc[-1] > spy["Close"].iloc[-2])


if __name__ == "__main__":
    main()
