from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from generate_report import (
    DOCS_DATA_DIR,
    ET,
    MARKET_GEMINI_MODEL,
    WATCHLIST_GEMINI_MODEL,
    append_ai_history,
    build_market_ai_output,
    build_watchlist_ai_output,
    gemini_generate_text,
    latest_market_ai_text,
    load_json,
    parse_json_blob,
    summarize_ai_error,
)

BASE_DIR = Path(__file__).resolve().parents[1]
KR_OUTPUT_PATH = DOCS_DATA_DIR / "latest_kr.json"
KR_AI_OUTPUT_PATH = DOCS_DATA_DIR / "latest_ai_kr.json"
KR_AI_HISTORY_PATH = DOCS_DATA_DIR / "ai_history_kr.json"
KR_WATCHLIST_AI_OUTPUT_PATH = DOCS_DATA_DIR / "latest_watchlist_ai_kr.json"
KR_WATCHLIST_AI_HISTORY_PATH = DOCS_DATA_DIR / "watchlist_ai_history_kr.json"


def build_kr_market_ai_payload(output: dict) -> dict:
    market = output.get("market", {})
    metrics = market.get("metrics", {})
    summary_rows = []
    for row in output.get("watchlist_summary", [])[:8]:
        summary_rows.append(
            {
                "ticker": row.get("ticker"),
                "name": row.get("name"),
                "score": row.get("stock_score"),
                "state": row.get("stock_state"),
                "action": row.get("final_action"),
                "note": row.get("note"),
                "close": row.get("close"),
                "change_pct": row.get("close_change_pct"),
                "rsi14": row.get("rsi14"),
            }
        )

    return {
        "generated_at_et": output.get("generated_at_et"),
        "market_data_as_of": output.get("market_data_as_of"),
        "market": {
            "score": market.get("score"),
            "state": market.get("state"),
            "action": market.get("action"),
            "top_reasons": market.get("top_reasons", [])[:4],
            "cross_highlights": market.get("cross_highlights", [])[:3],
            "cross_details": market.get("cross_highlights", [])[:3],
            "positive_factors": market.get("positive_factors", [])[:4],
            "negative_factors": market.get("negative_factors", [])[:4],
            "alerts": market.get("alerts", [])[:4],
            "metrics": {
                "kospi_close": metrics.get("kospi_close"),
                "kospi_change_pct": metrics.get("kospi_change_pct"),
                "kosdaq_close": metrics.get("kosdaq_close"),
                "kosdaq_change_pct": metrics.get("kosdaq_change_pct"),
                "kospi200_close": metrics.get("kospi200_close"),
                "kospi200_change_pct": metrics.get("kospi200_change_pct"),
                "usdkrw_close": metrics.get("usdkrw_close"),
                "usdkrw_change_pct": metrics.get("usdkrw_change_pct"),
                "vix_close": metrics.get("vix_close"),
                "vix_change_pct": metrics.get("vix_change_pct"),
                "vix_percentile": metrics.get("vix_percentile"),
                "kospi_rsi14": metrics.get("kospi_rsi14"),
                "kosdaq_rsi14": metrics.get("kosdaq_rsi14"),
                "kospi_volume_ratio_20d": metrics.get("kospi_volume_ratio_20d"),
                "kosdaq_volume_ratio_20d": metrics.get("kosdaq_volume_ratio_20d"),
                "semicon_close": metrics.get("semicon_close"),
                "semicon_change_pct": metrics.get("semicon_change_pct"),
                "brent_close": metrics.get("brent_close"),
                "brent_change_pct": metrics.get("brent_change_pct"),
            },
        },
        "watchlist_summary": summary_rows,
    }


def generate_kr_market_ai_analysis(output: dict, previous_ai_output: dict | None = None) -> dict:
    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return {
            "status": "disabled",
            "model": MARKET_GEMINI_MODEL,
            "content": "GOOGLE_API_KEY가 없어 한국 시장 AI 분석을 건너뛰었습니다.",
        }

    payload = build_kr_market_ai_payload(output)
    previous_text = latest_market_ai_text(previous_ai_output or {})
    prompt = f"""
너는 한국 주식 시장을 보는 실전형 전문 애널리스트다.

아래는 규칙 기반으로 계산한 한국 시장 모니터 데이터다.
1. 이 규칙 기반 시장 상태 및 흐름이 대체로 맞는지 먼저 판단한다.
2. 검색은 한국 뉴스와 한국 포털(예: 네이버)에서 확인되는 내용을 우선하고, 최신 뉴스, 지정학, 환율, 금리, 변동성, 주도 업종 상황만 반영하며, 확인되지 않은 내용은 단정하지 않는다.
3. 규칙 기반 데이터에 이미 들어 있는 점수 이유를 반복하지 말고, 그 바깥의 외부 변수와 맥락을 중심으로 설명한다.
4. AI 점수와 매매 여건은 규칙 기반 점수를 무시하고 독립적으로 평가한다.
5. 크로스 신호에 함께 들어간 거래량과 RSI 정보도 같이 보고, 신호 강도가 실제로 실릴 만한지 판단에 반영한다.
6. KOSPI, KOSDAQ, 원달러, 반도체, 국제유가, 해외 변동성이 왜 지금 한국 시장 분위기에 영향을 주는지 짚는다.
7. 아래에 첨부된 가장 최근 AI 분석 내용을 참고해서, 이번 답변이 이전보다 무엇이 달라졌는지 확인한다.
8. 새로 확인된 속보나 업데이트된 이슈가 있으면 `속보 요약`에 이전보다 더 최근 정보를 반영한다.
9. 이전 AI 분석과 같은 내용만 반복하지 말고, 달라진 점이나 새로 확인된 점이 있으면 우선해서 반영한다.
10. 확인된 뉴스가 뚜렷하지 않으면 억지로 채우지 말고 생략한다.
11. 단기투자 팁은 반드시 한 줄의 완전한 문장으로 채운다. 어떤 상황에서도 초단기 기준의 대응 방향을 분명히 제시하고, 지금 매수/추격/대기/비중축소/손절관리 중 무엇이 맞는지 이유를 붙여 짧고 명확하게 쓴다. `대기` 같은 한 단어만 쓰지 않는다.
12. 한국어로만, 짧고 깔끔하게 답한다.
13. 출력 형식은 아래 5줄만 쓴다.
AI 판단: 먼저 한 문장으로 현재 시장 판단을 쓰고, 바로 다음 줄 괄호에 (AI 점수: xx/100, AI 매매 여건: ..., AI 추천 행동: ...) 형식으로 쓴다.
확인 포인트: ...
결론: ...
속보 요약: ...
단기투자 팁: ...
14. 각 줄은 한두 문장 이내로 짧게 쓴다. 결론은 중요한 이슈가 있으면 불릿 포인트로 2~3개까지 정리한다.
15. 과장하지 말고, 규칙 기반 판단과 다르면 왜 다른지도 짚는다.
16. 결론은 시장 분위기, 가장 큰 위험 요인, 가장 중요한 긍정 요인 순서로 정리한다.
17. 마크다운 굵게 표시(**)는 쓰지 않는다.
18. 속보 요약에는 한국 시장에 바로 영향을 줄 수 있는 최신 뉴스나 헤드라인만 1~3개까지 짧게 정리한다. 새 속보가 많지 않더라도 기존 속보 흐름을 이어서 최신 내용으로 압축해 쓴다.
19. AI 판단 줄에는 점수 괄호만 쓰지 말고, 반드시 설명 문장을 먼저 쓴다.
20. 이전 AI 분석과 비교해도 새로 업데이트된 정보가 없으면, 기존 요약을 불필요하게 크게 바꾸지 않는다.

가장 최근 AI 분석:
{previous_text}

시장 데이터:
{json.dumps(payload, ensure_ascii=False, indent=2)}
""".strip()

    try:
        text = gemini_generate_text(prompt, api_key, MARKET_GEMINI_MODEL)
        return {
            "status": "ok",
            "model": MARKET_GEMINI_MODEL,
            "content": text,
        }
    except Exception as exc:
        return {
            "status": "error",
            "model": MARKET_GEMINI_MODEL,
            "content": f"한국 시장 AI 분석 실패: {summarize_ai_error(exc)}",
        }


def build_kr_watchlist_ai_payload(output: dict) -> dict:
    stocks_by_ticker = {stock.get("ticker"): stock for stock in output.get("stocks", [])}
    rows = []
    for row in output.get("watchlist_summary", [])[:10]:
        ticker = row.get("ticker")
        stock = stocks_by_ticker.get(ticker, {})
        rows.append(
            {
                "ticker": ticker,
                "name": row.get("name"),
                "market_label": row.get("market_label"),
                "close": row.get("close"),
                "change_pct": row.get("close_change_pct"),
                "score": row.get("stock_score"),
                "state": row.get("stock_state"),
                "action": row.get("final_action"),
                "note": row.get("note"),
                "cross_highlights": stock.get("cross_highlights", [])[:3],
                "top_reasons": stock.get("top_reasons", [])[:4],
                "volume_ratio_20d": stock.get("metrics", {}).get("volume_ratio_20d"),
                "rsi14": stock.get("metrics", {}).get("rsi14"),
                "signals": stock.get("signals", {}),
            }
        )

    market = output.get("market", {})
    return {
        "generated_at_et": output.get("generated_at_et"),
        "market_data_as_of": output.get("market_data_as_of"),
        "market": {
            "score": market.get("score"),
            "state": market.get("state"),
            "action": market.get("action"),
            "top_reasons": market.get("top_reasons", [])[:4],
            "cross_highlights": market.get("cross_highlights", [])[:3],
            "cross_details": market.get("cross_highlights", [])[:3],
        },
        "watchlist": rows,
    }


def generate_kr_watchlist_ai_analysis(output: dict) -> dict:
    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return build_watchlist_ai_output(
            output,
            [],
            "disabled",
            "GOOGLE_API_KEY가 없어 한국 종목 AI 분석을 건너뛰었습니다.",
        )

    payload = build_kr_watchlist_ai_payload(output)
    snapshot_by_ticker = {
        str(row.get("ticker") or "").upper(): {
            "close": row.get("close"),
            "change_pct": row.get("change_pct"),
            "score": row.get("score"),
            "state": row.get("state"),
            "action": row.get("action"),
            "cross_highlights": row.get("cross_highlights", []),
            "volume_ratio_20d": row.get("volume_ratio_20d"),
            "rsi14": row.get("rsi14"),
            "signals": row.get("signals", {}),
        }
        for row in payload.get("watchlist", [])
        if row.get("ticker")
    }
    prompt = f"""
너는 한국 관심종목을 빠르게 정리하는 실전형 전문 애널리스트다.

아래는 최대 10개 한국 관심종목의 현재 데이터다.
1. 각 종목마다 한국 뉴스와 한국 포털(예: 네이버)에서 검색으로 확인된 최신 주요 헤드라인 뉴스와 현재 추세를 함께 본다.
2. 확인되지 않은 내용은 단정하지 않는다.
3. 한국어로만 짧고 실전적으로 쓴다.
4. 반드시 JSON 배열만 출력한다. 마크다운이나 설명 문장은 쓰지 않는다.
5. 각 원소는 아래 키만 가진다.
   - ticker: 문자열
   - ai_score: 0~100 정수
   - ai_state: 짧은 상태 문자열
   - ai_action: 짧은 추천 행동 문자열
   - ai_note: 한두 문장 메모. 가능하면 최신 헤드라인 뉴스 한 가지와 현재 추세를 함께 넣고, 이미 보유 중일때는 짧은 탈출 전략도 함께 언급한다.
6. 점수는 현재 추세와 뉴스 흐름을 함께 반영하되, 현재 규칙 기반 점수와 완전히 같은 값으로 맞추지 말고 독립적으로 판단한다.
7. 상태와 추천 행동도 규칙 기반과 꼭 같게 맞추려 하지 말고, 뉴스와 추세가 다르면 표현을 조정한다.
8. 크로스 신호에 함께 들어간 거래량과 RSI 정보도 같이 보고, 신호 강도가 실리는 구간인지 판단에 반영한다.
9. 길게 쓰지 말고 종목당 메모는 1~2문장으로 끝낸다.

종목 데이터:
{json.dumps(payload, ensure_ascii=False, indent=2)}
""".strip()

    try:
        text = gemini_generate_text(prompt, api_key, WATCHLIST_GEMINI_MODEL)
        parsed = parse_json_blob(text)
        if not isinstance(parsed, list):
            raise ValueError("배열 형식 응답이 아닙니다.")

        items = []
        for row in parsed[:10]:
            if not isinstance(row, dict):
                continue
            ticker = str(row.get("ticker") or "").upper().strip()
            if not ticker:
                continue
            snapshot = snapshot_by_ticker.get(ticker, {})
            try:
                ai_score = int(max(0, min(100, int(row.get("ai_score", 0)))))
            except Exception:
                ai_score = 0
            items.append(
                {
                    "ticker": ticker,
                    "ai_score": ai_score,
                    "ai_state": str(row.get("ai_state") or "보통").strip()[:40],
                    "ai_action": str(row.get("ai_action") or "관찰").strip()[:60],
                    "ai_note": str(row.get("ai_note") or "").strip()[:240],
                    "close": snapshot.get("close"),
                    "change_pct": snapshot.get("change_pct"),
                    "score": snapshot.get("score"),
                    "state": snapshot.get("state"),
                    "action": snapshot.get("action"),
                    "cross_highlights": snapshot.get("cross_highlights", []),
                    "volume_ratio_20d": snapshot.get("volume_ratio_20d"),
                    "rsi14": snapshot.get("rsi14"),
                    "signals": snapshot.get("signals", {}),
                }
            )
        return build_watchlist_ai_output(output, items, "ok")
    except Exception as exc:
        return build_watchlist_ai_output(output, [], "error", f"한국 종목 AI 분석 실패: {summarize_ai_error(exc)}")


def main() -> None:
    output = load_json(KR_OUTPUT_PATH)
    if not output:
        raise RuntimeError("latest_kr.json not found or invalid")

    previous_market_output = load_json(KR_AI_OUTPUT_PATH)
    previous_output = load_json(KR_WATCHLIST_AI_OUTPUT_PATH)
    ai_generated_at_et = datetime.now(tz=ET).strftime("%Y-%m-%d %H:%M ET")
    market_ai = generate_kr_market_ai_analysis(output, previous_market_output)
    market_output = build_market_ai_output(output, market_ai, ai_generated_at_et)
    current_output = generate_kr_watchlist_ai_analysis(output)
    current_output["generated_at_et"] = ai_generated_at_et

    latest_market_output = market_output
    if market_output.get("ai_analysis", {}).get("status") != "ok" and previous_market_output.get("ai_analysis", {}).get("status") == "ok":
        latest_market_output = previous_market_output

    latest_output = current_output
    if current_output.get("status") != "ok" and previous_output.get("status") == "ok":
        latest_output = previous_output

    DOCS_DATA_DIR.mkdir(parents=True, exist_ok=True)
    with KR_AI_OUTPUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(latest_market_output, f, indent=2, ensure_ascii=False)
    with KR_WATCHLIST_AI_OUTPUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(latest_output, f, indent=2, ensure_ascii=False)
    append_ai_history(KR_AI_HISTORY_PATH, market_output)
    append_ai_history(KR_WATCHLIST_AI_HISTORY_PATH, current_output)


if __name__ == "__main__":
    main()
