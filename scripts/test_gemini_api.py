from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
LATEST_US_PATH = BASE_DIR / "docs" / "data" / "latest.json"
LATEST_AI_PATH = BASE_DIR / "docs" / "data" / "latest_ai.json"
MARKET_MODEL = "gemini-2.5-flash"
WATCHLIST_MODEL = "gemini-2.5-flash-lite"
SIMPLE_MODEL = MARKET_MODEL


def load_latest_market_payload() -> dict:
    data = json.loads(LATEST_US_PATH.read_text(encoding="utf-8"))
    market = data.get("market", {})
    metrics = market.get("metrics", {})
    watchlist = []
    for row in data.get("watchlist_summary", [])[:8]:
        watchlist.append(
            {
                "ticker": row.get("ticker"),
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
        "generated_at_et": data.get("generated_at_et"),
        "market_data_as_of": data.get("market_data_as_of"),
        "market": {
            "score": market.get("score"),
            "state": market.get("state"),
            "action": market.get("action"),
            "top_reasons": market.get("top_reasons", [])[:5],
            "cross_highlights": market.get("cross_highlights", [])[:4],
            "cross_details": market.get("cross_highlights", [])[:4],
            "positive_factors": market.get("positive_factors", [])[:5],
            "negative_factors": market.get("negative_factors", [])[:6],
            "alerts": market.get("alerts", [])[:4],
            "metrics": {
                "spx_close": metrics.get("spx_close"),
                "spx_change_pct": metrics.get("spx_change_pct"),
                "ndx_close": metrics.get("ndx_close"),
                "ndx_change_pct": metrics.get("ndx_change_pct"),
                "rut_close": metrics.get("rut_close"),
                "rut_change_pct": metrics.get("rut_change_pct"),
                "vix_close": metrics.get("vix_close"),
                "vix_change_pct": metrics.get("vix_change_pct"),
                "vix_percentile": metrics.get("vix_percentile"),
                "tnx_close": metrics.get("tnx_close"),
                "tnx_change_pct": metrics.get("tnx_change_pct"),
                "spx_rsi14": metrics.get("spx_rsi14"),
                "ndx_rsi14": metrics.get("ndx_rsi14"),
                "spy_volume_ratio_20d": metrics.get("spy_volume_ratio_20d"),
                "qqq_volume_ratio_20d": metrics.get("qqq_volume_ratio_20d"),
                "dxy_20d_zscore": metrics.get("dxy_20d_zscore"),
                "tnx_20d_zscore": metrics.get("tnx_20d_zscore"),
                "pct_above_20dma": metrics.get("pct_above_20dma"),
                "pct_above_50dma": metrics.get("pct_above_50dma"),
                "brent_close": metrics.get("brent_close"),
                "brent_change_pct": metrics.get("brent_change_pct"),
            },
        },
        "watchlist_summary": watchlist,
    }


def load_latest_watchlist_payload() -> dict:
    data = json.loads(LATEST_US_PATH.read_text(encoding="utf-8"))
    market = data.get("market", {})
    stocks_by_ticker = {stock.get("ticker"): stock for stock in data.get("stocks", [])}
    rows = []
    for row in data.get("watchlist_summary", [])[:10]:
        ticker = row.get("ticker")
        stock = stocks_by_ticker.get(ticker, {})
        rows.append(
            {
                "ticker": ticker,
                "close": row.get("close"),
                "change_pct": row.get("close_change_pct"),
                "score": row.get("stock_score"),
                "state": row.get("stock_state"),
                "action": row.get("final_action"),
                "note": row.get("note"),
                "cross_highlights": stock.get("cross_highlights", [])[:3],
                "top_reasons": stock.get("top_reasons", [])[:4],
                "earnings_date": stock.get("earnings_date"),
                "volume_ratio_20d": stock.get("metrics", {}).get("volume_ratio_20d"),
                "rsi14": stock.get("metrics", {}).get("rsi14"),
            }
        )
    return {
        "generated_at_et": data.get("generated_at_et"),
        "market_data_as_of": data.get("market_data_as_of"),
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


def load_latest_ai_text() -> str:
    if not LATEST_AI_PATH.exists():
        return "이전 AI 분석 없음"
    try:
        data = json.loads(LATEST_AI_PATH.read_text(encoding="utf-8"))
    except Exception:
        return "이전 AI 분석 없음"
    ai_analysis = data.get("ai_analysis", {})
    if not isinstance(ai_analysis, dict):
        return "이전 AI 분석 없음"
    status = str(ai_analysis.get("status") or "").strip().lower()
    content = str(ai_analysis.get("content") or "").strip()
    if status == "ok" and content:
        return content
    return "이전 AI 분석 없음"


def build_prompt(mode: str) -> str:
    if mode == "simple":
        return "현재 미국 시장을 볼 때 핵심 체크 포인트 5개를 한국어로 아주 짧게 정리해줘."

    if mode == "watchlist":
        payload = load_latest_watchlist_payload()
        return f"""
너는 미국 관심종목을 빠르게 정리하는 실전형 전문 애널리스트다.

아래는 최대 10개 미국 관심종목의 현재 데이터다.
1. 각 종목마다 검색으로 확인된 최신 주요 헤드라인 뉴스와 현재 추세를 함께 본다.
2. 확인되지 않은 내용은 단정하지 않는다.
3. 한국어로만 짧고 실전적으로 쓴다.
4. 반드시 JSON 배열만 출력한다. 마크다운이나 설명 문장은 쓰지 않는다.
5. 각 원소는 아래 키만 가진다.
   - ticker: 문자열
   - ai_score: 0~100 정수
   - ai_state: 짧은 상태 문자열
   - ai_action: 짧은 추천 행동 문자열
   - ai_note: 한두 문장 메모. 가능하면 최신 헤드라인 뉴스 한 가지와 현재 추세를 함께 넣는다.
6. 점수는 현재 추세와 뉴스 흐름을 함께 반영하되, 현재 규칙 기반 점수와 완전히 같은 값으로 맞추지 말고 독립적으로 판단한다.
7. 상태와 추천 행동도 규칙 기반과 꼭 같게 맞추려 하지 말고, 뉴스와 추세가 다르면 표현을 조정한다.
8. 크로스 신호에 함께 들어간 거래량과 RSI 정보도 같이 보고, 신호 강도가 실리는 구간인지 판단에 반영한다.
9. 길게 쓰지 말고 종목당 메모는 1~2문장으로 끝낸다.

종목 데이터:
{json.dumps(payload, ensure_ascii=False, indent=2)}
""".strip()

    payload = load_latest_market_payload()
    previous_text = load_latest_ai_text()
    return f"""
너는 미국 주식 시장을 보는 실전형 전문 애널리스트다.

아래는 규칙 기반으로 계산한 미국 시장 모니터 데이터다.
1. 이 규칙 기반 시장 상태 및 흐름이 대체로 맞는지 먼저 판단한다.
2. 검색으로 확인된 최신 뉴스, 지정학, 금리, 변동성, 주도 업종 상황만 반영하고, 확인되지 않은 내용은 단정하지 않는다.
3. 규칙 기반 데이터에 이미 들어 있는 점수 이유를 반복하지 말고, 그 바깥의 외부 변수와 맥락을 중심으로 설명한다.
4. AI 점수와 매매 여건은 규칙 기반 점수와 꼭 같게 맞추지 말고, 독립적으로 판단한다.
5. 크로스 신호에 함께 들어간 거래량과 RSI 정보도 같이 보고, 신호 강도가 실제로 실릴 만한지 판단에 반영한다.
6. 시장 점수나 breadth, VIX 같은 지표 문장을 그대로 다시 풀어쓰지 말고, 왜 그런 환경이 만들어졌는지를 짚는다.
7. 아래에 첨부된 가장 최근 AI 분석 내용을 참고해서, 이번 답변이 이전보다 무엇이 달라졌는지 확인한다.
8. 새로 확인된 속보나 업데이트된 이슈가 있으면 `속보 요약`에 이전보다 더 최근 정보를 반영한다.
9. 이전 AI 분석과 같은 내용만 반복하지 말고, 달라진 점이나 새로 확인된 점이 있으면 우선해서 반영한다.
10. 확인된 뉴스가 뚜렷하지 않으면 억지로 채우지 말고 생략한다.
11. 한국어로만, 짧고 깔끔하게 답한다.
12. 출력 형식은 아래 4줄만 쓴다.
AI 판단: 먼저 한 문장으로 현재 시장 판단을 쓰고, 바로 다음 줄 괄호에 (AI 점수: xx/100, AI 매매 여건: ..., AI 추천 행동: ...) 형식으로 쓴다.
확인 포인트: ...
결론: ...
속보 요약: ...
13. 각 줄은 한두 문장 이내로 짧게 쓴다. 결론은 중요한 이슈가 있으면 불릿 포인트로 2~3개까지 정리한다.
14. 과장하지 말고, 규칙 기반 판단과 다르면 왜 다른지도 짚는다.
15. 결론은 시장 분위기, 가장 큰 위험 요인, 가장 중요한 긍정 요인 순서로 정리한다.
16. 마크다운 굵게 표시(**)는 쓰지 않는다.
17. 속보 요약에는 시장에 바로 영향을 줄 수 있는 최신 뉴스나 헤드라인만 1~3개까지 짧게 정리한다. 새 속보가 많지 않더라도 기존 속보 흐름을 이어서 최신 내용으로 압축해 쓴다.
18. AI 판단 줄에는 점수 괄호만 쓰지 말고, 반드시 설명 문장을 먼저 쓴다.
19. 이전 AI 분석과 비교해도 새로 업데이트된 정보가 없으면, 기존 요약을 불필요하게 크게 바꾸지 않는다.

가장 최근 AI 분석:
{previous_text}

시장 데이터:
{json.dumps(payload, ensure_ascii=False, indent=2)}
""".strip()


def import_gemini():
    try:
        from google import genai as modern_genai
        from google.genai import types
        return ("genai", modern_genai, types)
    except Exception as first_exc:
        try:
            import google.generativeai as legacy_genai
            return ("generativeai", legacy_genai, None)
        except Exception as second_exc:
            raise ImportError(
                "Google Gemini SDK import failed. Install it with 'pip install -r requirements.txt'."
            ) from second_exc if second_exc else first_exc


def main() -> int:
    parser = argparse.ArgumentParser(description="Gemini API local smoke test")
    parser.add_argument("--model", help="Gemini model name")
    parser.add_argument("--mode", choices=["simple", "market", "watchlist"], default="simple", help="Prompt mode")
    parser.add_argument("--with-search", dest="with_search", action="store_true", help="Enable Google Search tool")
    parser.add_argument("--no-search", dest="with_search", action="store_false", help="Disable Google Search tool")
    parser.set_defaults(with_search=True)
    args = parser.parse_args()

    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("GOOGLE_API_KEY or GEMINI_API_KEY is not set.", file=sys.stderr)
        return 1

    try:
        backend, genai, types = import_gemini()
    except Exception as exc:
        print(f"Failed to import Gemini SDK: {exc}", file=sys.stderr)
        return 1

    prompt = build_prompt(args.mode)
    selected_model = args.model or (
        WATCHLIST_MODEL if args.mode == "watchlist" else MARKET_MODEL if args.mode == "market" else SIMPLE_MODEL
    )
    print(f"Model: {selected_model}")
    print(f"Backend: {backend}")
    print(f"Mode: {args.mode}")
    print(f"Google Search: {'on' if args.with_search else 'off'}")
    print("-" * 60)

    try:
        if backend == "genai":
            client = genai.Client(api_key=api_key)
            config = types.GenerateContentConfig(temperature=0.2)
            if args.with_search:
                config.tools = [types.Tool(google_search=types.GoogleSearch())]
            response = client.models.generate_content(
                model=selected_model,
                contents=prompt,
                config=config,
            )
            text = (getattr(response, "text", None) or "").strip()
        else:
            if args.with_search:
                print("Google Search requires google-genai; continuing without search on the legacy backend.", file=sys.stderr)
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(selected_model)
            response = model.generate_content(prompt)
            text = (getattr(response, "text", None) or "").strip()
    except Exception as exc:
        print(f"Gemini request failed: {exc}", file=sys.stderr)
        return 2

    if not text:
        print("Gemini returned an empty response.", file=sys.stderr)
        return 3

    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
