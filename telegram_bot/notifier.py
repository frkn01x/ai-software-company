"""
Telegram Notifier — asenkron değil, sync HTTP ile çalışır.
Crew'dan çağrılır; ajanlar raporlarını buraya gönderir.
"""

import logging
import requests
from config import cfg
from datetime import datetime

logger = logging.getLogger(__name__)

PRIORITY_EMOJIS = {
    "low":      "🔵",
    "normal":   "🟢",
    "high":     "🟡",
    "critical": "🔴",
}

REPORT_TYPE_EMOJIS = {
    "task_update":    "📋",
    "bug_report":     "🐛",
    "security_alert": "🔒",
    "test_result":    "🧪",
    "daily_summary":  "📊",
    "info":           "ℹ️",
    "error":          "❌",
}


def send_message(text: str, parse_mode: str = "Markdown") -> bool:
    """Ham mesaj gönderir."""
    token   = cfg.telegram_token
    chat_id = cfg.telegram_chat_id

    if not token or not chat_id:
        logger.warning("Telegram token veya chat_id eksik, mesaj atlandı.")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id":    chat_id,
        "text":       text[:4096],  # Telegram limiti
        "parse_mode": parse_mode,
    }
    try:
        resp = requests.post(url, json=payload, timeout=15)
        resp.raise_for_status()
        return True
    except Exception as exc:
        logger.error("Telegram send error: %s", exc)
        return False


def send_agent_report(
    agent_name: str,
    report_type: str,
    title: str,
    content: str,
    priority: str = "normal",
) -> bool:
    """Ajan raporu formatında mesaj gönderir."""
    ts      = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    p_emoji = PRIORITY_EMOJIS.get(priority, "🟢")
    r_emoji = REPORT_TYPE_EMOJIS.get(report_type, "📄")

    header = (
        f"{p_emoji} {r_emoji} *{title}*\n"
        f"👤 Ajan: `{agent_name}`\n"
        f"🕐 {ts}\n"
        f"{'─' * 30}\n"
    )

    # İçeriği 3800 karakterle sınırla (header için yer bırak)
    body = content[:3800]
    message = header + body

    return send_message(message)


def send_file_as_message(filename: str, content: str) -> bool:
    """Büyük çıktıları parçalara bölerek gönderir."""
    chunks = [content[i:i+3500] for i in range(0, len(content), 3500)]
    success = True
    for i, chunk in enumerate(chunks, 1):
        text = f"📄 *{filename}* ({i}/{len(chunks)})\n```\n{chunk}\n```"
        if not send_message(text):
            success = False
    return success
