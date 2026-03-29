from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

BASE_DIR = Path(__file__).resolve().parents[1]
LATEST_PATH = BASE_DIR / "docs" / "data" / "latest.json"
LATEST_KR_PATH = BASE_DIR / "docs" / "data" / "latest_kr.json"
LATEST_AI_PATH = BASE_DIR / "docs" / "data" / "latest_ai.json"
ET = ZoneInfo("America/New_York")


def priority_label(priority: str) -> str:
    return {
        "high": "[HIGH]",
        "medium": "[MEDIUM]",
        "low": "[LOW]",
    }.get(priority, "[INFO]")


def env_flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def build_market_summary(payload: dict) -> str:
    market = payload.get("market", {})
    summary = payload.get("watchlist_summary", [])
    top_rows = sorted(summary, key=lambda row: row.get("stock_score", 0), reverse=True)[:3]
    cross_items = market.get("cross_highlights", []) or []
    cross_text = " / ".join(item.split(":")[0].strip() for item in cross_items[:2]) if cross_items else "뚜렷한 신호 없음"
    lines = [
        "시장 상태 요약",
        f"생성: {payload.get('generated_at_et', '-')}",
        f"상태/행동: {market.get('state', '-')} / {market.get('score', '-')}/100 / {market.get('action', '-')}",
        f"크로스: {cross_text}",
    ]
    if market.get("top_reasons"):
        lines.append(f"핵심: {market['top_reasons'][0]}")
    if top_rows:
        top_text = ", ".join(
            f"{row.get('name', row.get('ticker', '-'))}: {row.get('stock_score', '-')}/100 {row.get('stock_state', '-')}"
            for row in top_rows
        )
        lines.append(f"상위 종목: {top_text}")
    return "\n".join(lines)


def resolve_latest_path() -> Path:
    raw = os.environ.get("DISCORD_PAYLOAD_PATH", "").strip().lower()
    if raw in {"kr", "latest_kr.json", "korea", "korean"}:
        return LATEST_KR_PATH
    return LATEST_PATH


def summary_heading() -> str:
    return os.environ.get("DISCORD_SUMMARY_TITLE", "시장 상태 요약").strip() or "시장 상태 요약"


def alert_heading() -> str:
    return os.environ.get("DISCORD_ALERT_TITLE", "시장 모니터 알림").strip() or "시장 모니터 알림"


def ai_alert_heading() -> str:
    return os.environ.get("DISCORD_AI_ALERT_TITLE", "AI 시장 분석 알림").strip() or "AI 시장 분석 알림"


def build_test_message(kind: str, payload: dict) -> str:
    market = payload.get("market", {})
    generated_at = payload.get("generated_at_et", "-")
    as_of = payload.get("market_data_as_of", "-")
    state_line = f"{market.get('state', '-')} / {market.get('score', '-')}/100 / {market.get('action', '-')}"

    if kind == "summary":
        return "\n".join(
            [
                f"{summary_heading()} [TEST]",
                f"생성: {generated_at}",
                f"상태/행동: {state_line}",
                "핵심: 테스트용 기본 요약 메시지입니다.",
            ]
        )

    if kind == "important":
        return "\n".join(
            [
                f"{alert_heading()} [TEST]",
                f"생성: {generated_at}",
                "",
                "[HIGH] 시장 레벨 하락",
                "테스트용 중요 알림입니다. 실제 조건과 무관하게 전송됩니다.",
            ]
        )

    if kind == "ai":
        return "\n".join(
            [
                f"{ai_alert_heading()} [TEST]",
                f"업데이트: {generated_at}",
                "",
                "[HIGH] 시장 레벨 급변",
                "테스트용 AI 알림입니다. 실제 AI 조건과 무관하게 전송됩니다.",
            ]
        )

    raise ValueError(f"Unknown DISCORD_TEST_KIND: {kind}")


def is_quiet_hours() -> bool:
    now_et = datetime.now(ET)
    minute_of_day = now_et.hour * 60 + now_et.minute
    return 0 <= minute_of_day < (2 * 60 + 30)


def main() -> None:
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
    if not webhook_url:
        print("DISCORD_WEBHOOK_URL not set, skipping.")
        return

    if env_flag("DISCORD_AI_ALERTS", default=False):
        latest_path = LATEST_AI_PATH
    else:
        latest_path = resolve_latest_path()

    if not latest_path.exists():
        print(f"{latest_path.name} not found, skipping.")
        return

    with latest_path.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    test_kind = os.environ.get("DISCORD_TEST_KIND", "").strip().lower()
    if test_kind:
        content = build_test_message(test_kind, payload)
        response = requests.post(webhook_url, json={"content": content}, timeout=15)
        response.raise_for_status()
        print(f"Sent Discord test message for kind={test_kind}.")
        return

    if is_quiet_hours():
        now_et = datetime.now(ET).strftime("%Y-%m-%d %H:%M ET")
        print(f"Discord send skipped during quiet hours: {now_et}")
        return

    if env_flag("DISCORD_AI_ALERTS", default=False):
        notifications = payload.get("ai_notifications", {}).get("items", [])
        if not notifications:
            print("No AI notifications to send.")
            return
        lines = [
            ai_alert_heading(),
            f"업데이트: {payload.get('generated_at_et', '-')}",
            "",
        ]
        for item in notifications[:8]:
            lines.append(f"{priority_label(item.get('priority', ''))} {item.get('title', '-')}")
            lines.append(item.get("message", "-"))
            lines.append("")

        content = "\n".join(lines).strip()
        if len(content) > 1800:
            content = f"{content[:1790]}\n..."

        response = requests.post(webhook_url, json={"content": content}, timeout=15)
        response.raise_for_status()
        print(f"Sent Discord AI message with {len(notifications)} AI notifications.")
        return

    if env_flag("DISCORD_MARKET_SUMMARY", default=False):
        content = build_market_summary(payload).replace("시장 상태 요약", summary_heading(), 1)
        response = requests.post(webhook_url, json={"content": content}, timeout=15)
        response.raise_for_status()
        print("Sent Discord market summary.")
        return

    notifications = payload.get("notifications", {}).get("items", [])
    if not notifications:
        print("No notifications to send.")
        return

    lines = [
        alert_heading(),
        f"생성: {payload.get('generated_at_et', '-')}",
        "",
    ]
    for item in notifications[:8]:
        lines.append(f"{priority_label(item.get('priority', ''))} {item.get('title', '-')}")
        lines.append(item.get("message", "-"))
        lines.append("")

    content = "\n".join(lines).strip()
    if len(content) > 1800:
        content = f"{content[:1790]}\n..."

    response = requests.post(webhook_url, json={"content": content}, timeout=15)
    response.raise_for_status()
    print(f"Sent Discord message with {len(notifications)} important notifications.")


if __name__ == "__main__":
    main()
