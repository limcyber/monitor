from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from generate_report import (
    DOCS_DATA_DIR,
    ET,
    WATCHLIST_GEMINI_MODEL,
    append_ai_history,
    build_watchlist_ai_output,
    gemini_generate_text,
    load_json,
    parse_json_blob,
    summarize_ai_error,
)

BASE_DIR = Path(__file__).resolve().parents[1]
KR_OUTPUT_PATH = DOCS_DATA_DIR / "latest_kr.json"
KR_WATCHLIST_AI_OUTPUT_PATH = DOCS_DATA_DIR / "latest_watchlist_ai_kr.json"
KR_WATCHLIST_AI_HISTORY_PATH = DOCS_DATA_DIR / "watchlist_ai_history_kr.json"


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
            "signals": row.get("signals", {}),
        }
        for row in payload.get("watchlist", [])
        if row.get("ticker")
    }
    prompt = f"""
너는 한국 관심종목을 빠르게 정리하는 실전형 전문 애널리스트다.

아래는 최대 10개 한국 관심종목의 현재 데이터다.
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
6. 점수는 현재 추세와 뉴스 흐름을 함께 반영하되, 현재 규칙 기반 점수와 완전히 동떨어지지 않게 쓴다.
7. 길게 쓰지 말고 종목당 메모는 1~2문장으로 끝낸다.

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

    previous_output = load_json(KR_WATCHLIST_AI_OUTPUT_PATH)
    ai_generated_at_et = datetime.now(tz=ET).strftime("%Y-%m-%d %H:%M ET")
    current_output = generate_kr_watchlist_ai_analysis(output)
    current_output["generated_at_et"] = ai_generated_at_et

    latest_output = current_output
    if current_output.get("status") != "ok" and previous_output.get("status") == "ok":
        latest_output = previous_output

    DOCS_DATA_DIR.mkdir(parents=True, exist_ok=True)
    with KR_WATCHLIST_AI_OUTPUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(latest_output, f, indent=2, ensure_ascii=False)
    append_ai_history(KR_WATCHLIST_AI_HISTORY_PATH, current_output)


if __name__ == "__main__":
    main()
