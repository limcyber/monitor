from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from generate_report import (
    DOCS_DATA_DIR,
    ET,
    build_notification,
    confidence_from_coverage,
    factor_text,
    load_json,
    load_price_frame,
    load_yaml,
    market_action,
    market_alert_tags,
    market_level,
    market_position_tags,
    market_state_name,
    pct_change_from_prev_close,
    percentile_rank,
    prioritize_market_factors,
    pick_market_reasons,
    parse_output_date,
    recent_cross_signal,
    score_history_tags,
    score_stock,
    slope_up,
    state_rank,
    stock_alert_tags,
    stock_change_tags,
    stock_confidence_warnings,
    stock_position_tags,
    update_history,
    zscore,
)

BASE_DIR = Path(__file__).resolve().parents[1]
KR_WATCHLIST_PATH = BASE_DIR / "config" / "watchlist_kr.yml"
KR_OUTPUT_PATH = DOCS_DATA_DIR / "latest_kr.json"
KR_HISTORY_PATH = DOCS_DATA_DIR / "history_kr.json"


def build_kr_notifications(as_of, previous_output: dict, market_output: dict, stock_reports: list[dict]) -> list[dict]:
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
        notifications.append(
            build_notification(
                f"kr-market-level-{direction}-{as_of.isoformat()}",
                priority,
                "kr_market_level_change",
                f"한국 시장 레벨 {direction}",
                f"한국 시장 레벨이 {prev_level}/6에서 {current_level}/6으로 {direction}했습니다. 현재 추천 행동은 '{market_output['action']}'입니다.",
            )
        )

    current_high_stress = bool(market_output["negative_filters"]["filter_3_high_stress"])
    prev_high_stress = bool(prev_filters.get("filter_3_high_stress"))
    if current_high_stress and not prev_high_stress:
        notifications.append(
            build_notification(
                f"kr-market-high-stress-{as_of.isoformat()}",
                "high",
                "kr_market_high_stress",
                "한국 시장 고스트레스 구간",
                "원달러와 해외 변동성 부담이 같이 높아졌습니다. 신규 진입은 더 보수적으로 보는 편이 좋습니다.",
            )
        )

    current_both_below = bool(
        market_output["metrics"]["kospi_close"] < market_output["metrics"]["kospi_dma200"]
        and market_output["metrics"]["kosdaq_close"] < market_output["metrics"]["kosdaq_dma200"]
    )
    prev_both_below = bool(
        prev_metrics
        and prev_metrics.get("kospi_close") is not None
        and prev_metrics.get("kospi_dma200") is not None
        and prev_metrics.get("kosdaq_close") is not None
        and prev_metrics.get("kosdaq_dma200") is not None
        and prev_metrics["kospi_close"] < prev_metrics["kospi_dma200"]
        and prev_metrics["kosdaq_close"] < prev_metrics["kosdaq_dma200"]
    )
    if current_both_below and not prev_both_below:
        notifications.append(
            build_notification(
                f"kr-market-both-below-200dma-{as_of.isoformat()}",
                "high",
                "kr_market_below_200dma",
                "한국 핵심 지수 200일선 이탈",
                "KOSPI와 KOSDAQ이 모두 200일선 아래에 있습니다. 방어적으로 보는 편이 좋습니다.",
            )
        )

    current_warnings = market_output.get("confidence_warnings", [])
    prev_warnings = prev_market.get("confidence_warnings", []) if isinstance(prev_market, dict) else []
    if current_warnings and current_warnings != prev_warnings:
        notifications.append(
            build_notification(
                f"kr-market-data-warning-{as_of.isoformat()}",
                "medium",
                "kr_data_warning",
                "한국 데이터 확인 필요",
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
        name = stock.get("name", ticker)

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
                    f"kr-stock-entry-{ticker}-{as_of.isoformat()}",
                    "medium",
                    "kr_stock_entry_candidate",
                    f"{name} 진입 후보",
                    f"{name}가 {stock['stock_score']}/100으로 올라왔고 추천 행동은 '{current_action}'입니다.",
                    scope="stock",
                    ticker=ticker,
                )
            )

        if prev_state and state_rank(prev_state) >= 3 and state_rank(current_state) <= 2:
            notifications.append(
                build_notification(
                    f"kr-stock-weakened-{ticker}-{as_of.isoformat()}",
                    "medium",
                    "kr_stock_weakened",
                    f"{name} 상태 약화",
                    f"{name} 상태가 {prev_state}에서 {current_state}(으)로 약해졌습니다. 지금은 더 보수적으로 보는 편이 좋습니다.",
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
                        f"kr-stock-dead-cross-{ticker}-{as_of.isoformat()}",
                        "medium",
                        "kr_stock_dead_cross",
                        f"{name} 데드크로스",
                        cross,
                        scope="stock",
                        ticker=ticker,
                    )
                )
                break
            if "골든크로스" in cross and current_level >= 4 and stock["stock_score"] >= 65:
                notifications.append(
                    build_notification(
                        f"kr-stock-golden-cross-{ticker}-{as_of.isoformat()}",
                        "low",
                        "kr_stock_golden_cross",
                        f"{name} 골든크로스",
                        cross,
                        scope="stock",
                        ticker=ticker,
                    )
                )
                break

    priority_rank = {"high": 0, "medium": 1, "low": 2}
    notifications.sort(key=lambda item: (priority_rank.get(item["priority"], 9), item["title"]))
    return notifications[:8]


def load_kr_watchlist() -> list[dict]:
    raw = load_yaml(KR_WATCHLIST_PATH).get("watchlist", [])
    cleaned = []
    for item in raw:
        ticker = str(item.get("ticker", "")).upper().strip()
        if not ticker:
            continue
        cleaned.append(
            {
                "ticker": ticker,
                "name": str(item.get("name", ticker)).strip(),
                "market": str(item.get("market", "KOSPI")).upper().strip(),
            }
        )
    return cleaned


def compact_signed(value: int) -> str:
    return f"{value:+d}" if value else "0"


def kr_market_change_tags(previous_output: dict, current_market: dict) -> list[str]:
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
    usdkrw_change = current_market.get("metrics", {}).get("usdkrw_change_pct")
    if isinstance(usdkrw_change, (int, float)):
        tags.append(f"원달러 일간 {usdkrw_change:+.2f}%")
    return tags[:4]


def kr_confidence_warnings(data_map: dict[str, pd.DataFrame], stock_reports: list[dict]) -> list[str]:
    warnings = []
    missing = [label for label, df in data_map.items() if df.empty or len(df) < 60]
    if missing:
        warnings.append(f"지수 데이터 일부 누락: {', '.join(missing[:3])}")
    if any(len(stock.get("series", {}).get("dates", [])) < 60 for stock in stock_reports):
        warnings.append("일부 종목 히스토리가 짧습니다")
    return warnings[:3]


def kr_market_guidance(score: int, market_data: dict) -> tuple[list[str], list[str], list[str], str]:
    kospi = market_data["KOSPI"]["Close"]
    kosdaq = market_data["KOSDAQ"]["Close"]
    kospi200 = market_data["KOSPI200"]["Close"]
    semicon = market_data["SEMICON"]["Close"]
    usdkrw = market_data["USDKRW"]["Close"]
    vix = market_data["VIX"]["Close"]

    positive_factors: list[str] = []
    negative_factors: list[str] = []
    reasons: list[str] = []
    cross_highlights: list[str] = []

    kospi_dma5 = kospi.rolling(5).mean()
    kospi_dma20 = kospi.rolling(20).mean()
    kospi_dma50 = kospi.rolling(50).mean()
    kospi_dma200 = kospi.rolling(200).mean()

    kosdaq_dma5 = kosdaq.rolling(5).mean()
    kosdaq_dma20 = kosdaq.rolling(20).mean()
    kosdaq_dma50 = kosdaq.rolling(50).mean()
    kosdaq_dma200 = kosdaq.rolling(200).mean()

    kospi200_dma50 = kospi200.rolling(50).mean()
    kospi200_dma200 = kospi200.rolling(200).mean()
    semicon_dma20 = semicon.rolling(20).mean()
    semicon_dma50 = semicon.rolling(50).mean()

    score_value = 0

    if kospi.iloc[-1] > kospi_dma200.iloc[-1]:
        score_value += 15
        positive_factors.append(factor_text("KOSPI가 200일선 위에 있습니다", 15))
        reasons.append("KOSPI가 200일선 위에 있습니다")
    if kospi_dma50.iloc[-1] > kospi_dma200.iloc[-1]:
        score_value += 8
        positive_factors.append(factor_text("KOSPI의 50일선이 200일선 위에 있습니다", 8))
    if slope_up(kospi_dma20):
        score_value += 7
        positive_factors.append(factor_text("KOSPI의 20일선이 올라가는 중입니다", 7))
        reasons.append("KOSPI의 20일선이 올라가는 중입니다")
    if kospi.iloc[-1] > kospi_dma20.iloc[-1]:
        score_value += 5
        positive_factors.append(factor_text("KOSPI가 20일선 위에 있습니다", 5))
    else:
        score_value -= 2
        negative_factors.append(factor_text("KOSPI가 20일선 아래라 단기 흐름이 약합니다", -2))

    if kosdaq.iloc[-1] > kosdaq_dma200.iloc[-1]:
        score_value += 12
        positive_factors.append(factor_text("KOSDAQ이 200일선 위에 있습니다", 12))
        reasons.append("KOSDAQ이 200일선 위에 있습니다")
    if kosdaq_dma50.iloc[-1] > kosdaq_dma200.iloc[-1]:
        score_value += 6
        positive_factors.append(factor_text("KOSDAQ의 50일선이 200일선 위에 있습니다", 6))
    if slope_up(kosdaq_dma20):
        score_value += 6
        positive_factors.append(factor_text("KOSDAQ의 20일선이 올라가는 중입니다", 6))
    if kosdaq.iloc[-1] > kosdaq_dma20.iloc[-1]:
        score_value += 5
        positive_factors.append(factor_text("KOSDAQ이 20일선 위에 있습니다", 5))
    else:
        score_value -= 2
        negative_factors.append(factor_text("KOSDAQ이 20일선 아래라 단기 흐름이 약합니다", -2))

    if kospi200.iloc[-1] > kospi200_dma50.iloc[-1]:
        score_value += 5
        positive_factors.append(factor_text("KOSPI200이 50일선 위에 있습니다", 5))
    if kospi200.iloc[-1] > kospi200_dma200.iloc[-1]:
        score_value += 5
        positive_factors.append(factor_text("KOSPI200이 200일선 위에 있습니다", 5))

    kosdaq_kospi_ratio = (kosdaq / kospi).dropna()
    if len(kosdaq_kospi_ratio) >= 20 and kosdaq_kospi_ratio.iloc[-1] >= kosdaq_kospi_ratio.iloc[-20]:
        score_value += 8
        positive_factors.append(factor_text("코스닥이 코스피에 크게 밀리지 않습니다", 8))
        reasons.append("코스닥이 코스피에 크게 밀리지 않습니다")
    elif len(kosdaq_kospi_ratio) >= 20:
        score_value -= 4
        negative_factors.append(factor_text("중소형주 쪽 힘이 약합니다", -4))
        reasons.append("중소형주 쪽 힘이 약합니다")

    semicon_kospi_ratio = (semicon / kospi).dropna()
    if semicon.iloc[-1] > semicon_dma50.iloc[-1]:
        score_value += 5
        positive_factors.append(factor_text("반도체 ETF가 50일선 위에 있습니다", 5))
        reasons.append("반도체 흐름이 아직 꺾이지 않았습니다")
    else:
        score_value -= 3
        negative_factors.append(factor_text("반도체 ETF가 50일선 아래라 주도 업종 힘이 약합니다", -3))
    if semicon.iloc[-1] > semicon_dma20.iloc[-1]:
        score_value += 3
        positive_factors.append(factor_text("반도체 ETF가 20일선 위에 있습니다", 3))
    else:
        score_value -= 1
        negative_factors.append(factor_text("반도체 ETF가 20일선 아래라 단기 흐름도 약합니다", -1))
    if len(semicon_kospi_ratio) >= 20 and semicon_kospi_ratio.iloc[-1] >= semicon_kospi_ratio.iloc[-20]:
        score_value += 4
        positive_factors.append(factor_text("반도체가 코스피보다 더 강합니다", 4))
        reasons.append("반도체가 코스피보다 더 강합니다")
    elif len(semicon_kospi_ratio) >= 20:
        score_value -= 4
        negative_factors.append(factor_text("반도체가 코스피보다 약해지고 있습니다", -4))

    usdkrw_z = zscore(usdkrw, 20)
    if usdkrw_z <= 0.8:
        score_value += 10
        positive_factors.append(factor_text("원달러 부담이 심하지 않습니다", 10))
    elif usdkrw_z <= 1.2:
        score_value += 4
        positive_factors.append(factor_text("원달러가 아주 나쁘진 않습니다", 4))
    elif usdkrw_z <= 1.5:
        score_value -= 4
        negative_factors.append(factor_text("원달러가 올라 외국인 수급에는 부담입니다", -4))
        reasons.append("원달러가 올라 외국인 수급에는 부담입니다")
    else:
        score_value -= 6
        negative_factors.append(factor_text("원달러가 많이 올라 외국인 수급 부담이 큽니다", -6))
        reasons.append("원달러가 올라 외국인 수급에는 부담입니다")

    vix_pct = percentile_rank(vix, 252)
    if vix_pct < 70:
        score_value += 8
        positive_factors.append(factor_text("해외 변동성 부담이 심하지 않습니다", 8))
    elif vix_pct > 80:
        score_value -= 5
        negative_factors.append(factor_text("해외 변동성이 높아 국내장도 흔들릴 수 있습니다", -5))
    else:
        score_value -= 3
        negative_factors.append(factor_text("해외 변동성이 높아 국내장도 흔들릴 수 있습니다", -3))

    kosdaq_vol = kosdaq.pct_change().rolling(20).std()
    kosdaq_vol_z = zscore(kosdaq_vol.dropna(), 20) if len(kosdaq_vol.dropna()) >= 20 else 0.0
    if kosdaq_vol_z <= 0.7:
        score_value += 5
        positive_factors.append(factor_text("코스닥 변동성이 과열 구간은 아닙니다", 5))
    else:
        score_value -= 2
        negative_factors.append(factor_text("코스닥 변동성이 커서 추격 매수는 부담입니다", -2))

    kospi_short_bull, kospi_short_bear = recent_cross_signal(
        kospi_dma5,
        kospi_dma20,
        factor_text("KOSPI에서 최근 5일선이 20일선을 상향 돌파했습니다", 2),
        factor_text("KOSPI에서 최근 5일선이 20일선을 하향 이탈했습니다", -5),
    )
    if kospi_short_bull:
        score_value += 2
        cross_highlights.append("KOSPI 최근 단기 골든크로스")
        positive_factors.append(kospi_short_bull)
        reasons.append("KOSPI에서 최근 단기 골든크로스가 나왔습니다")
    if kospi_short_bear:
        score_value -= 5
        cross_highlights.append("KOSPI 최근 단기 데드크로스")
        negative_factors.append(kospi_short_bear)
        reasons.append("KOSPI에서 최근 단기 데드크로스가 나왔습니다")

    kosdaq_short_bull, kosdaq_short_bear = recent_cross_signal(
        kosdaq_dma5,
        kosdaq_dma20,
        factor_text("KOSDAQ에서 최근 5일선이 20일선을 상향 돌파했습니다", 2),
        factor_text("KOSDAQ에서 최근 5일선이 20일선을 하향 이탈했습니다", -5),
    )
    if kosdaq_short_bull:
        score_value += 2
        cross_highlights.append("KOSDAQ 최근 단기 골든크로스")
        positive_factors.append(kosdaq_short_bull)
        reasons.append("KOSDAQ에서 최근 단기 골든크로스가 나왔습니다")
    if kosdaq_short_bear:
        score_value -= 5
        cross_highlights.append("KOSDAQ 최근 단기 데드크로스")
        negative_factors.append(kosdaq_short_bear)
        reasons.append("KOSDAQ에서 최근 단기 데드크로스가 나왔습니다")

    if kospi_short_bear and kosdaq_short_bear:
        score_value -= 4
        score_value = min(score_value, 75)
        negative_factors.append(factor_text("KOSPI와 KOSDAQ이 함께 단기 데드크로스라 공격 점수를 높게 주기 어렵습니다", "상한 75"))
        reasons.append("KOSPI와 KOSDAQ이 함께 단기 데드크로스입니다")

    kospi_mid_bull, kospi_mid_bear = recent_cross_signal(
        kospi_dma20,
        kospi_dma50,
        factor_text("KOSPI에서 최근 20일선이 50일선을 상향 돌파했습니다", 4),
        factor_text("KOSPI에서 최근 20일선이 50일선을 하향 이탈했습니다", -10),
        lookback=10,
    )
    if kospi_mid_bull:
        score_value += 4
        cross_highlights.append("KOSPI 최근 중기 골든크로스")
        positive_factors.append(kospi_mid_bull)
    if kospi_mid_bear:
        score_value -= 10
        cross_highlights.append("KOSPI 최근 중기 데드크로스")
        negative_factors.append(kospi_mid_bear)
        reasons.append("KOSPI에서 최근 중기 데드크로스가 나왔습니다")

    kosdaq_mid_bull, kosdaq_mid_bear = recent_cross_signal(
        kosdaq_dma20,
        kosdaq_dma50,
        factor_text("KOSDAQ에서 최근 20일선이 50일선을 상향 돌파했습니다", 4),
        factor_text("KOSDAQ에서 최근 20일선이 50일선을 하향 이탈했습니다", -10),
        lookback=10,
    )
    if kosdaq_mid_bull:
        score_value += 4
        cross_highlights.append("KOSDAQ 최근 중기 골든크로스")
        positive_factors.append(kosdaq_mid_bull)
    if kosdaq_mid_bear:
        score_value -= 10
        cross_highlights.append("KOSDAQ 최근 중기 데드크로스")
        negative_factors.append(kosdaq_mid_bear)
        reasons.append("KOSDAQ에서 최근 중기 데드크로스가 나왔습니다")

    if kospi_mid_bear and kosdaq_mid_bear:
        score_value = min(score_value, 55)
        negative_factors.append(factor_text("KOSPI와 KOSDAQ이 함께 중기 데드크로스라 회복 확인 전까지 보수적으로 보는 편이 좋습니다", "상한 55"))
        reasons.append("KOSPI와 KOSDAQ이 함께 중기 데드크로스입니다")

    if kospi.iloc[-1] <= kospi_dma50.iloc[-1]:
        score_value -= 3
        negative_factors.append(factor_text("KOSPI가 50일선 아래라 중간 흐름도 약합니다", -3))
    if kosdaq.iloc[-1] <= kosdaq_dma50.iloc[-1]:
        score_value -= 3
        negative_factors.append(factor_text("KOSDAQ이 50일선 아래라 중간 흐름도 약합니다", -3))
    if kospi.iloc[-1] <= kospi_dma50.iloc[-1] and kosdaq.iloc[-1] <= kosdaq_dma50.iloc[-1]:
        score_value -= 2
        negative_factors.append(factor_text("KOSPI와 KOSDAQ이 함께 50일선 아래라 회복 확인이 더 필요합니다", -2))

    if kospi.iloc[-1] <= kospi_dma200.iloc[-1]:
        negative_factors.append(factor_text("KOSPI가 200일선 아래에 있습니다", 0))
    if kosdaq.iloc[-1] <= kosdaq_dma200.iloc[-1]:
        negative_factors.append(factor_text("KOSDAQ이 200일선 아래에 있습니다", 0))
    if len(kosdaq_kospi_ratio) >= 20 and kosdaq_kospi_ratio.iloc[-1] < kosdaq_kospi_ratio.iloc[-20]:
        negative_factors.append(factor_text("중소형주 쪽 힘이 약합니다", 0))
    if semicon.iloc[-1] <= semicon_dma50.iloc[-1]:
        negative_factors.append(factor_text("반도체 ETF가 50일선 아래라 주도 업종 힘이 약합니다", 0))
    if len(semicon_kospi_ratio) >= 20 and semicon_kospi_ratio.iloc[-1] < semicon_kospi_ratio.iloc[-20]:
        negative_factors.append(factor_text("반도체가 코스피보다 약해지고 있습니다", 0))
    if len(kosdaq_kospi_ratio) >= 20 and kosdaq_kospi_ratio.iloc[-1] < kosdaq_kospi_ratio.iloc[-20] and len(semicon_kospi_ratio) >= 20 and semicon_kospi_ratio.iloc[-1] < semicon_kospi_ratio.iloc[-20]:
        score_value -= 4
        negative_factors.append(factor_text("코스닥과 반도체가 함께 약해 시장 체감이 좋지 않습니다", -4))

    if kospi.iloc[-1] <= kospi_dma200.iloc[-1] and kosdaq.iloc[-1] <= kosdaq_dma200.iloc[-1]:
        score_value = min(score_value, 45)
        negative_factors.append(factor_text("KOSPI와 KOSDAQ이 모두 200일선 아래라 상단 점수가 막힙니다", "상한 45"))

    if pct_change_from_prev_close(kospi) and pct_change_from_prev_close(kospi) > 0:
        if len(kosdaq_kospi_ratio) >= 5 and kosdaq_kospi_ratio.iloc[-1] < kosdaq_kospi_ratio.iloc[-5]:
            score_value -= 8
            negative_factors.append(factor_text("지수 반등인데 코스닥 참여는 약합니다", -8))

    if usdkrw_z > 1.2 and vix_pct > 80:
        score_value -= 4
        negative_factors.append(factor_text("원달러와 해외 변동성이 같이 높아 부담이 큽니다", -4))

    if (
        score_value < 50
        and kospi.iloc[-1] > kospi_dma200.iloc[-1]
        and kosdaq.iloc[-1] > kosdaq_dma200.iloc[-1]
        and kospi_dma50.iloc[-1] > kospi_dma200.iloc[-1]
        and kosdaq_dma50.iloc[-1] > kosdaq_dma200.iloc[-1]
        and not (kospi_short_bear and kosdaq_short_bear)
        and usdkrw_z <= 1.2
        and vix_pct < 80
    ):
        score_value = 50

    if kospi.iloc[-1] <= kospi_dma200.iloc[-1] and kosdaq.iloc[-1] <= kosdaq_dma200.iloc[-1]:
        invalidation = "KOSPI와 KOSDAQ이 모두 200일선 아래라면 반등이 나와도 쉽게 추격하기보다 방어적으로 보는 편이 좋습니다."
    elif usdkrw_z > 1.0:
        invalidation = "원달러가 더 올라가면 국내장 수급이 흔들릴 수 있어 보수적으로 보는 편이 좋습니다."
    else:
        invalidation = "KOSPI나 KOSDAQ이 20일선 아래로 다시 밀리고 원달러가 같이 오르면 공격적으로 보기 어렵습니다."

    positive_factors, negative_factors = prioritize_market_factors(positive_factors, negative_factors)
    return {
        "score": int(max(0, min(100, round(score_value)))),
        "reasons": reasons,
        "cross_highlights": cross_highlights[:4],
        "positive_factors": positive_factors[:6],
        "negative_factors": negative_factors[:6],
        "invalidation": invalidation,
    }


def build_kr_market_output(now_et: datetime, previous_output: dict) -> tuple[dict, list[datetime], dict[str, pd.DataFrame]]:
    latest_intraday_points: list[datetime] = []

    kospi, ts = load_price_frame("^KS11", now_et)
    if ts:
        latest_intraday_points.append(ts)
    kosdaq, ts = load_price_frame("^KQ11", now_et)
    if ts:
        latest_intraday_points.append(ts)
    kospi200, ts = load_price_frame("^KS200", now_et)
    if ts:
        latest_intraday_points.append(ts)
    semicon, ts = load_price_frame("091160.KS", now_et)
    if ts:
        latest_intraday_points.append(ts)
    usdkrw, ts = load_price_frame("KRW=X", now_et)
    if ts:
        latest_intraday_points.append(ts)
    vix, ts = load_price_frame("^VIX", now_et)
    if ts:
        latest_intraday_points.append(ts)

    market_data = {
        "KOSPI": kospi,
        "KOSDAQ": kosdaq,
        "KOSPI200": kospi200,
        "SEMICON": semicon,
        "USDKRW": usdkrw,
        "VIX": vix,
    }
    scored = kr_market_guidance(0, market_data)
    score = scored["score"]
    level = market_level(score)
    confidence = confidence_from_coverage(6, sum(1 for df in market_data.values() if not df.empty and len(df) >= 60))
    usdkrw_z = zscore(usdkrw["Close"], 20)
    vix_pct = percentile_rank(vix["Close"], 252)
    high_stress = usdkrw_z > 1.2 or vix_pct > 80

    market_output = {
        "state": f"레벨 {level}/6 - {market_state_name(level)}",
        "score": score,
        "confidence": confidence,
        "execution_strength": "매우 보수적" if high_stress and level <= 3 else "보수적" if high_stress or level <= 3 else "보통" if level == 4 else "좋음",
        "action": market_action(level),
        "top_reasons": pick_market_reasons(level, scored["positive_factors"], scored["negative_factors"]),
        "cross_highlights": scored["cross_highlights"],
        "positive_factors": scored["positive_factors"],
        "negative_factors": scored["negative_factors"],
        "invalidation": scored["invalidation"],
        "easy_explanation": (
            "국내장 분위기가 비교적 괜찮아 대표주 위주로 선별 접근을 볼 수 있습니다."
            if level >= 5
            else "국내장은 아직 조심해서 보는 편이 좋습니다. 강한 종목도 분할 접근이 더 안전합니다."
        ),
        "negative_filters": {
            "filter_1_divergence": any("코스닥 참여는 약합니다" in item for item in scored["negative_factors"]),
            "filter_2_bigcap_only": any("중소형주 쪽 힘이 약합니다" in item for item in scored["negative_factors"]),
            "filter_3_high_stress": high_stress,
            "filter_4_event_risk": False,
            "event_names": [],
        },
        "metrics": {
            "kospi_close": float(kospi["Close"].iloc[-1]),
            "kospi_change_pct": pct_change_from_prev_close(kospi["Close"]),
            "kospi_dma200": float(kospi["Close"].rolling(200).mean().iloc[-1]),
            "kosdaq_close": float(kosdaq["Close"].iloc[-1]),
            "kosdaq_change_pct": pct_change_from_prev_close(kosdaq["Close"]),
            "kosdaq_dma200": float(kosdaq["Close"].rolling(200).mean().iloc[-1]),
            "kospi200_close": float(kospi200["Close"].iloc[-1]),
            "kospi200_change_pct": pct_change_from_prev_close(kospi200["Close"]),
            "semicon_close": float(semicon["Close"].iloc[-1]),
            "semicon_change_pct": pct_change_from_prev_close(semicon["Close"]),
            "usdkrw_close": float(usdkrw["Close"].iloc[-1]),
            "usdkrw_change_pct": pct_change_from_prev_close(usdkrw["Close"]),
            "vix_close": float(vix["Close"].iloc[-1]),
            "vix_change_pct": pct_change_from_prev_close(vix["Close"]),
            "usdkrw_20d_zscore": zscore(usdkrw["Close"], 20),
            "vix_percentile": percentile_rank(vix["Close"], 252),
            "kosdaq_kospi_ratio_change_20d": float((kosdaq["Close"].iloc[-1] / kospi["Close"].iloc[-1]) / (kosdaq["Close"].iloc[-20] / kospi["Close"].iloc[-20]) - 1) if len(kospi) >= 20 and len(kosdaq) >= 20 else 0.0,
        },
    }
    market_output["change_tags"] = kr_market_change_tags(previous_output, market_output)
    market_output["position_tags"] = market_position_tags(level, False)
    market_output["alerts"] = market_alert_tags(market_output)
    market_output["sector_tags"] = []
    market_output["confidence_warnings"] = []
    return market_output, latest_intraday_points, market_data


def main() -> None:
    now_et = datetime.now(tz=ET)
    as_of = now_et.date()
    previous_output = load_json(KR_OUTPUT_PATH)
    existing_history = load_json(KR_HISTORY_PATH)

    watchlist = load_kr_watchlist()
    if len(watchlist) != 8:
        raise ValueError("watchlist_kr.yml must contain exactly 8 stocks.")

    market_output, latest_intraday_points, market_frames = build_kr_market_output(now_et, previous_output)
    level = market_level(market_output["score"])

    stock_reports = []
    for item in watchlist:
        sdf, ts = load_price_frame(item["ticker"], now_et)
        if ts:
            latest_intraday_points.append(ts)
        benchmark = market_frames["KOSDAQ"] if item["market"] == "KOSDAQ" else market_frames["KOSPI"]
        stock = score_stock(item["ticker"], sdf, benchmark, level, None, None, neutral_missing_earnings=True)
        stock["name"] = item["name"]
        stock["market_label"] = item["market"]
        stock["display_label"] = f"{item['name']} ({item['ticker']})"
        stock["cross_highlights"] = [text.replace(item["ticker"], item["name"]) for text in stock.get("cross_highlights", [])]
        stock["change_tags"] = stock_change_tags(previous_output, stock)
        stock["position_tags"] = stock_position_tags(level, stock["stock_state"], False, stock.get("overheated", False))
        stock["alerts"] = stock_alert_tags(stock)
        stock["confidence_warnings"] = stock_confidence_warnings(stock)
        stock_reports.append(stock)

    market_output["confidence_warnings"] = kr_confidence_warnings(market_frames, stock_reports)

    summary_table = [
        {
            "ticker": stock["ticker"],
            "name": stock["name"],
            "market_label": stock["market_label"],
            "stock_score": stock["stock_score"],
            "stock_state": stock["stock_state"],
            "final_action": stock["final_action"],
            "note": stock["note"],
            "close": stock["metrics"]["close"],
            "close_change_pct": stock["metrics"]["close_change_pct"],
        }
        for stock in stock_reports
    ]

    latest_intraday_at = max(latest_intraday_points) if latest_intraday_points else None
    intraday_mode = latest_intraday_at is not None and latest_intraday_at.date() == now_et.date()

    output = {
        "generated_at_et": now_et.strftime("%Y-%m-%d %H:%M ET"),
        "market_data_as_of": (
            f"{latest_intraday_at.strftime('%Y-%m-%d %H:%M ET')} (5분봉)"
            if intraday_mode
            else f"{market_frames['KOSPI'].index[-1].strftime('%Y-%m-%d')} 15:30 KST (Close)"
        ),
        "market": market_output,
        "watchlist_summary": summary_table,
        "stocks": stock_reports,
        "charts": {
            "market": {
                "dates": [d.strftime("%Y-%m-%d") for d in market_frames["KOSPI"]["Close"].tail(63).index],
                "kospi_close": [float(v) for v in market_frames["KOSPI"]["Close"].tail(63).tolist()],
                "kospi_dma200": [None if pd.isna(v) else float(v) for v in market_frames["KOSPI"]["Close"].rolling(200).mean().tail(63).tolist()],
                "kosdaq_close": [float(v) for v in market_frames["KOSDAQ"]["Close"].tail(63).tolist()],
                "kosdaq_dma200": [None if pd.isna(v) else float(v) for v in market_frames["KOSDAQ"]["Close"].rolling(200).mean().tail(63).tolist()],
                "kospi200_close": [float(v) for v in market_frames["KOSPI200"]["Close"].tail(63).tolist()],
                "semicon_close": [float(v) for v in market_frames["SEMICON"]["Close"].tail(63).tolist()],
                "usdkrw_close": [float(v) for v in market_frames["USDKRW"]["Close"].tail(63).tolist()],
                "vix_close": [float(v) for v in market_frames["VIX"]["Close"].tail(63).tolist()],
                "kosdaq_kospi_ratio": [
                    float(v) for v in (market_frames["KOSDAQ"]["Close"] / market_frames["KOSPI"]["Close"]).tail(63).tolist()
                ],
            }
        },
    }
    output["notifications"] = {
        "count": 0,
        "items": [],
    }
    output["notifications"]["items"] = build_kr_notifications(as_of, previous_output, market_output, stock_reports)
    output["notifications"]["count"] = len(output["notifications"]["items"])

    history = update_history(existing_history, output, as_of)
    output["market"]["history_tags"] = score_history_tags(history.get("market", []))
    for stock in output["stocks"]:
        stock["history_tags"] = score_history_tags(history.get("stocks", {}).get(stock["ticker"], []))
    output["history"] = history

    DOCS_DATA_DIR.mkdir(parents=True, exist_ok=True)
    with KR_OUTPUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    with KR_HISTORY_PATH.open("w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
