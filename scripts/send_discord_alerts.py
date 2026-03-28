from __future__ import annotations

import json
import os
from pathlib import Path

import requests

BASE_DIR = Path(__file__).resolve().parents[1]
LATEST_PATH = BASE_DIR / "docs" / "data" / "latest.json"
LATEST_KR_PATH = BASE_DIR / "docs" / "data" / "latest_kr.json"


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
    lines = [
        "시장 상태 요약",
        f"생성 시각: {payload.get('generated_at_et', '-')}",
        f"데이터 기준: {payload.get('market_data_as_of', '-')}",
        f"시장 상태: {market.get('state', '-')}",
        f"점수 / 행동: {market.get('score', '-')}/100 / {market.get('action', '-')}",
    ]
    if market.get("top_reasons"):
        lines.append(f"핵심 이유: {market['top_reasons'][0]}")
    if top_rows:
        top_text = ", ".join(
            f"{row.get('name', row.get('ticker', '-'))}: {row.get('stock_score', '-')}/100 {row.get('stock_state', '-')}"
            for row in top_rows
        )
        lines.append(f"상위 관심종목: {top_text}")
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


def main() -> None:
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
    if not webhook_url:
        print("DISCORD_WEBHOOK_URL not set, skipping.")
        return

    latest_path = resolve_latest_path()

    if not latest_path.exists():
        print(f"{latest_path.name} not found, skipping.")
        return

    with latest_path.open("r", encoding="utf-8") as f:
        payload = json.load(f)

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

    market = payload.get("market", {})
    lines = [
        alert_heading(),
        f"생성 시각: {payload.get('generated_at_et', '-')}",
        f"데이터 기준: {payload.get('market_data_as_of', '-')}",
        f"시장 상태: {market.get('state', '-')} / {market.get('score', '-')}/100 / {market.get('action', '-')}",
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
