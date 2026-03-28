from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
LATEST_US_PATH = BASE_DIR / "docs" / "data" / "latest.json"
DEFAULT_MODEL = "gemini-2.5-flash"


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


def build_prompt(mode: str) -> str:
    if mode == "simple":
        return "현재 미국 시장을 볼 때 핵심 체크 포인트 5개를 한국어로 아주 짧게 정리해줘."

    payload = load_latest_market_payload()
    return f"""
너는 미국 주식 시장을 보는 실전형 전문 애널리스트다.

아래는 규칙 기반으로 계산한 미국 시장 모니터 데이터다.
1. 이 규칙 기반 시장 상태 및 흐름이 대체로 맞는지 먼저 판단한다.
2. 검색으로 확인된 최신 뉴스, 지정학, 금리, 변동성, 주도 업종 상황만 반영하고, 확인되지 않은 내용은 단정하지 않는다.
3. 규칙 기반 데이터에 이미 들어 있는 점수 이유를 반복하지 말고, 그 바깥의 외부 변수와 맥락을 중심으로 설명한다.
4. 시장 점수나 breadth, VIX 같은 지표 문장을 그대로 다시 풀어쓰지 말고, 왜 그런 환경이 만들어졌는지를 짚는다.
5. 확인된 뉴스가 뚜렷하지 않으면 억지로 채우지 말고 생략한다.
6. 한국어로만, 짧고 깔끔하게 답한다.
7. 출력 형식은 아래 3줄만 쓴다.
AI 판단: ... (AI 점수: xx/100, AI 매매 여건: ..., AI 추천 행동: ...)
확인 포인트: ...
결론: ...
8. 각 줄은 한두 문장 이내로 짧게 쓴다. 결론은 중요한 이슈가 있으면 불릿 포인트로 2~3개까지 정리한다.
9. 과장하지 말고, 규칙 기반 판단과 다르면 왜 다른지도 짚는다.
10. 결론은 시장 분위기, 가장 큰 위험 요인, 가장 중요한 긍정 요인 순서로 정리한다.
11. 마크다운 굵게 표시(**)는 쓰지 않는다.

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
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Gemini model name")
    parser.add_argument("--mode", choices=["simple", "market"], default="simple", help="Prompt mode")
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
    print(f"Model: {args.model}")
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
                model=args.model,
                contents=prompt,
                config=config,
            )
            text = (getattr(response, "text", None) or "").strip()
        else:
            if args.with_search:
                print("Google Search requires google-genai; continuing without search on the legacy backend.", file=sys.stderr)
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(args.model)
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
