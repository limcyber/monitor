from __future__ import annotations

import json
import os
from pathlib import Path

import requests

BASE_DIR = Path(__file__).resolve().parents[1]
LATEST_PATH = BASE_DIR / "docs" / "data" / "latest.json"


def priority_label(priority: str) -> str:
    return {
        "high": "[HIGH]",
        "medium": "[MEDIUM]",
        "low": "[LOW]",
    }.get(priority, "[INFO]")

def main() -> None:
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
    if not webhook_url:
        print("DISCORD_WEBHOOK_URL not set, skipping.")
        return

    if not LATEST_PATH.exists():
        print("latest.json not found, skipping.")
        return

    with LATEST_PATH.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    notifications = payload.get("notifications", {}).get("items", [])
    if not notifications:
        print("No notifications to send.")
        return

    market = payload.get("market", {})
    lines = [
        "시장 모니터 알림",
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
