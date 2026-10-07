"""
CrewAI Tool: Telegram Reporter
Ajanların detaylı raporlarını Telegram'a göndermesini sağlar.
"""

from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class TelegramReportInput(BaseModel):
    agent_name: str = Field(description="Raporu gönderen ajanın adı")
    report_type: str = Field(description="Rapor türü: task_update | bug_report | security_alert | test_result | daily_summary")
    title: str = Field(description="Rapor başlığı")
    content: str = Field(description="Rapor içeriği (Markdown desteklenir)")
    priority: str = Field(default="normal", description="Öncelik: low | normal | high | critical")


class TelegramReportTool(BaseTool):
    name: str = "telegram_reporter"
    description: str = (
        "Ajan raporlarını ve bildirimlerini Telegram'a gönderir. "
        "Görev güncellemeleri, hata raporları, güvenlik uyarıları ve "
        "test sonuçları için kullanılır."
    )
    args_schema: type[BaseModel] = TelegramReportInput

    def _run(
        self,
        agent_name: str,
        report_type: str,
        title: str,
        content: str,
        priority: str = "normal",
    ) -> str:
        from telegram_bot.notifier import send_agent_report
        success = send_agent_report(
            agent_name=agent_name,
            report_type=report_type,
            title=title,
            content=content,
            priority=priority,
        )
        if success:
            return f"✅ Rapor Telegram'a gönderildi: {title}"
        return f"❌ Telegram gönderimi başarısız: {title}"
