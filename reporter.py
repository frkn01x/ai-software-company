"""
Reporter — Garantili Ajan Raporlama Sistemi (v3 — Obsidian Entegrasyonlu)

Üç katmanlı raporlama:
  1. task_callback  : CrewAI görevi bitince OTOMATIK → State + Telegram + Obsidian
  2. step_callback  : Ajan her adım attığında → Log + Obsidian vault
  3. conv_callback  : Görevler arası context geçişi → Obsidian conversations/

Obsidian vault ZIP'e eklenir, Telegram'dan indirilebilir.
Vault Obsidian'a sürükle-bırak ile açılır, tüm bağlantılar wikilink ile kurulmuş.
"""

import re
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from crewai.tasks.task_output import TaskOutput
from telegram_bot.notifier import send_message

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
#  Zaman takibi
# ─────────────────────────────────────────────
_task_start_times: dict[str, float] = {}

# ─────────────────────────────────────────────
#  Ajan etiket tablosu
# ─────────────────────────────────────────────
AGENT_LABELS = {
    "Chief Product Manager":                     ("PM",       "📋"),
    "VP of Engineering":                         ("EM",       "🏗️"),
    "Principal QA Engineer":                     ("QA",       "🧪"),
    "Principal UX/UI Designer":                  ("UX",       "🎨"),
    "Principal Security Engineer":               ("SEC",      "🔒"),
    "Principal Frontend Engineer":               ("FE",       "🖥️"),
    "Principal Python Backend Engineer":         ("BE-PY",    "🐍"),
    "Principal Node.js Backend Engineer":        ("BE-JS",    "🟨"),
    "Principal Go Engineer":                     ("BE-GO",    "🐹"),
    "Principal Rust Engineer":                   ("BE-RS",    "🦀"),
    "Principal .NET / ASP.NET Core Architect":   ("BE-NET",   "💜"),
    "Principal Database Engineer":               ("DB-SQL",   "🗄️"),
    "Principal NoSQL":                           ("DB-NOSQL", "🍃"),
    "Principal Code Quality Analyst":            ("ANALYST",  "🔍"),
    "Principal DevOps Engineer":                 ("DEVOPS",   "⚙️"),
    "Principal Solution Architect":              ("ARCH",     "🏛️"),
    "Principal Research Engineer":               ("RESEARCH", "🔭"),
    "Principal Business Analyst":                ("BA",       "📊"),
}

# Görev → ajan eşlemesi (context zinciri için)
TASK_AGENT_MAP = {
    "task_research":    "Principal Research Engineer",
    "task_pm":          "Chief Product Manager",
    "task_architect":   "Principal Solution Architect",
    "task_ux":          "Principal UX/UI Designer",
    "task_frontend":    "Principal Frontend Engineer",
    "task_backend_py":  "Principal Python Backend Engineer",
    "task_db_sql":      "Principal Database Engineer",
    "task_db_nosql":    "Principal NoSQL",
    "task_backend_net": "Principal .NET / ASP.NET Core Architect",
    "task_security":    "Principal Security Engineer",
    "task_qa":          "Principal QA Engineer",
    "task_ba":          "Principal Business Analyst",
    "task_analysis":    "Principal Code Quality Analyst",
    "task_devops":      "Principal DevOps Engineer",
    "task_em_final":    "VP of Engineering",
}

# Görevin bağlı olduğu önceki görevler (context konuşmaları için)
TASK_CONTEXTS = {
    "task_pm":          ["task_research"],
    "task_architect":   ["task_research", "task_pm"],
    "task_ux":          ["task_pm", "task_architect"],
    "task_frontend":    ["task_ux", "task_pm", "task_architect"],
    "task_backend_py":  ["task_pm", "task_architect", "task_frontend"],
    "task_db_sql":      ["task_pm", "task_backend_py"],
    "task_db_nosql":    ["task_pm", "task_db_sql"],
    "task_backend_net": ["task_pm", "task_db_sql", "task_db_nosql"],
    "task_security":    ["task_frontend", "task_backend_py", "task_db_sql", "task_db_nosql"],
    "task_qa":          ["task_frontend", "task_backend_py", "task_security"],
    "task_ba":          ["task_pm", "task_frontend", "task_backend_py", "task_security", "task_qa"],
    "task_analysis":    ["task_frontend", "task_backend_py", "task_qa", "task_ba"],
    "task_devops":      ["task_backend_py", "task_frontend", "task_qa", "task_ba"],
    "task_em_final":    ["task_research", "task_pm", "task_architect", "task_ux",
                         "task_frontend", "task_backend_py", "task_db_sql",
                         "task_db_nosql", "task_backend_net", "task_security",
                         "task_qa", "task_ba", "task_analysis", "task_devops"],
}


# ─────────────────────────────────────────────
#  Yardımcılar
# ─────────────────────────────────────────────

def _short_label(agent_role: str) -> tuple[str, str]:
    for key, val in AGENT_LABELS.items():
        if key.lower() in agent_role.lower():
            return val
    return ("AGENT", "🤖")


def _extract_files_created(output_text: str) -> list[str]:
    patterns = [
        r"Dosya kaydedildi[:\s]+`([^`]+)`",
        r"filepath=['\"]([^'\"]+)['\"]",
        r"output/\S+?/([^\s]+\.\w+)",
    ]
    files = []
    for pat in patterns:
        files.extend(re.findall(pat, output_text))
    return list(dict.fromkeys(files))


def _extract_e2b_result(output_text: str) -> Optional[str]:
    if "TEST GEÇTİ" in output_text or "✅ Başarılı: True" in output_text:
        return "✅ Geçti"
    if "TEST BAŞARISIZ" in output_text or "❌ Başarılı: False" in output_text:
        return "❌ Başarısız"
    passed = re.search(r"Geçti[:\s]+(\d+)", output_text)
    failed = re.search(r"Başarısız[:\s]+(\d+)", output_text)
    if passed or failed:
        p = passed.group(1) if passed else "?"
        f = failed.group(1) if failed else "?"
        return f"✅ {p} geçti / ❌ {f} başarısız"
    return None


def _extract_decisions(output_text: str) -> list[str]:
    """Çıktıdan önemli kararları çıkarır (ADR için)."""
    decisions = []
    patterns = [
        r"Karar[:\s]+(.+?)(?:\n|$)",
        r"ADR[:\s]+(.+?)(?:\n|$)",
        r"Seçilen[:\s]+(.+?)(?:\n|$)",
        r"Tercih[:\s]+(.+?)(?:\n|$)",
    ]
    for pat in patterns:
        matches = re.findall(pat, output_text, re.IGNORECASE)
        decisions.extend(m.strip() for m in matches if len(m.strip()) > 10)
    return decisions[:5]


def _summarize_output(text: str, max_len: int = 600) -> str:
    if not text:
        return "_Çıktı yok_"
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    compact = "\n".join(lines)
    if len(compact) <= max_len:
        return compact
    half = max_len // 2
    return compact[:half] + "\n\n_[...kısaltıldı...]_\n\n" + compact[-half:]


# ─────────────────────────────────────────────
#  Vault bağlantı yardımcısı
# ─────────────────────────────────────────────

def _get_vault():
    """Aktif vault'u güvenli şekilde döner (yoksa None)."""
    try:
        from obsidian_vault import get_vault
        return get_vault()
    except Exception:
        return None


# ─────────────────────────────────────────────
#  CrewAI callback'leri
# ─────────────────────────────────────────────

def task_start_callback(task_name: str):
    """Görev başladığında çağrılır — süre ölçümü ve vault kaydı."""
    _task_start_times[task_name] = time.time()
    logger.info("Görev başladı: %s", task_name)

    # Vault: görev başlangıcını kaydet
    vault = _get_vault()
    if vault:
        try:
            agent_role = TASK_AGENT_MAP.get(task_name, "Bilinmeyen Ajan")
            vault.record_task_start(
                task_name=task_name,
                agent_role=agent_role,
                description=f"Görev başladı: {task_name}",
            )
        except Exception as exc:
            logger.debug("Vault task_start hatası: %s", exc)


def task_callback(task_output: TaskOutput):
    """
    CrewAI'nin task_callback'i — her görev tamamlandığında OTOMATIK çağrılır.
    1. State'e tamamlandı yazar
    2. Telegram'a detaylı rapor gönderir
    3. Obsidian vault'a yazar (ajan sayfası + task sayfası + konuşmalar)
    """
    try:
        from state import mark_task_complete

        # ── Temel bilgiler ─────────────────────────────────────────────
        agent_role = str(getattr(task_output, "agent", "Bilinmeyen Ajan"))
        task_name  = str(
            getattr(task_output, "name", "")
            or getattr(task_output, "description", "")[:60]
        )
        raw_output = str(
            getattr(task_output, "raw_output", "")
            or getattr(task_output, "raw", "")
            or ""
        )
        ts = datetime.utcnow().strftime("%H:%M UTC")

        short_label, emoji = _short_label(agent_role)

        # ── 1. STATE KAYDET ────────────────────────────────────────────
        task_id = task_name.strip()[:80]
        mark_task_complete(task_id, raw_output)
        logger.info("State güncellendi: '%s' tamamlandı.", task_id)

        # ── 2. Süre hesabı ─────────────────────────────────────────────
        elapsed_secs = 0
        start = _task_start_times.pop(task_name, None)
        if start:
            elapsed_secs = int(time.time() - start)
        elapsed_str = f"⏱️ Süre: {elapsed_secs // 60}dk {elapsed_secs % 60}sn\n" if elapsed_secs else ""

        # ── 3. Çıktı analizi ───────────────────────────────────────────
        files     = _extract_files_created(raw_output)
        e2b       = _extract_e2b_result(raw_output)
        decisions = _extract_decisions(raw_output)
        e2b_passed = (e2b == "✅ Geçti") if e2b else None

        files_text = ""
        if files:
            files_text = "📁 *Oluşturulan dosyalar:*\n" + "\n".join(f"  • `{f}`" for f in files[:10]) + "\n"
        e2b_text = f"🧪 *E2B Test:* {e2b}\n" if e2b else ""
        summary  = _summarize_output(raw_output)

        # ── 4. TELEGRAM RAPORU ─────────────────────────────────────────
        message = (
            f"{emoji} *[{short_label}] Görev Tamamlandı*\n"
            f"🕐 {ts}\n"
            f"{elapsed_str}"
            f"📌 *Görev:* _{task_name[:80]}_\n"
            f"{e2b_text}"
            f"{files_text}"
            f"{'─' * 28}\n"
            f"{summary}"
        )
        send_message(message)
        logger.info("Task callback Telegram raporu gönderildi: %s", short_label)

        # ── 5. OBSİDİAN VAULT ─────────────────────────────────────────
        vault = _get_vault()
        if vault:
            try:
                # 5a. Görev tamamlanma kaydı
                vault.record_task_complete(
                    task_name=task_id,
                    agent_role=agent_role,
                    output=raw_output,
                    duration_secs=elapsed_secs,
                    files_created=files if files else None,
                    e2b_passed=e2b_passed,
                )

                # 5b. Kararları ADR olarak kaydet
                for i, decision in enumerate(decisions):
                    vault.record_decision(
                        agent_role=agent_role,
                        title=decision[:80],
                        context=f"Görev '{task_id}' sırasında alınan karar.",
                        decision=decision,
                    )

                # 5c. Context konuşmalarını belgele
                # (Bu ajan hangi ajanlardan bilgi aldı?)
                ctx_tasks = TASK_CONTEXTS.get(task_id, [])
                for ctx_task in ctx_tasks[:4]:  # max 4 bağlantı
                    from_role = TASK_AGENT_MAP.get(ctx_task, "")
                    if from_role and from_role != agent_role:
                        vault.record_conversation(
                            from_agent=from_role,
                            to_agent=agent_role,
                            subject=f"{ctx_task} → {task_id} context",
                            content=(
                                f"**{from_role}** tamamladığı `{ctx_task}` görevinin "
                                f"çıktısını **{agent_role}** ajanına context olarak iletti.\n\n"
                                f"Bu bilgi `{task_id}` görevinin yürütülmesinde kullanıldı."
                            ),
                            task_context=task_id,
                        )

                logger.debug("Obsidian vault güncellendi: %s", task_id)

            except Exception as exc:
                logger.warning("Obsidian vault yazma hatası (sessiz): %s", exc)

    except Exception as exc:
        logger.error("task_callback ana hatası: %s", exc)


def step_callback(step_output):
    """
    CrewAI'nin step_callback'i — ajan her adım attığında çağrılır.
    Loglara + Obsidian vault'a yazar (Telegram'a göndermez — çok sık olur).
    """
    try:
        agent_role = str(getattr(step_output, "agent", "?"))
        action     = getattr(step_output, "action", None)
        tool_name  = getattr(action, "tool", None) if action else None
        tool_input = str(getattr(action, "tool_input", ""))[:300] if action else ""
        result     = str(getattr(step_output, "result", ""))[:400]
        thought    = str(getattr(action, "log", ""))[:400] if action else ""

        # ── Log ───────────────────────────────────────────────────────
        short_label, _ = _short_label(agent_role)
        if tool_name:
            logger.info("[STEP] %s → tool=%s | input=%s | result=%s",
                        short_label, tool_name, tool_input[:100], result[:100])
        else:
            logger.debug("[STEP] %s → %s", short_label, result[:100])

        # ── Obsidian vault ────────────────────────────────────────────
        vault = _get_vault()
        if vault:
            try:
                if tool_name:
                    # Tool kullanımı — daha önemli
                    vault.record_step(
                        agent_role=agent_role,
                        action_type="tool_use",
                        content=f"**Input:** `{tool_input[:200]}`",
                        tool_name=tool_name,
                        tool_result=result[:300] if result else None,
                    )
                elif thought and len(thought) > 20:
                    # Düşünce adımı
                    vault.record_step(
                        agent_role=agent_role,
                        action_type="thought",
                        content=thought[:400],
                    )
                elif result and len(result) > 20:
                    # Gözlem adımı
                    vault.record_step(
                        agent_role=agent_role,
                        action_type="observation",
                        content=result[:400],
                    )
            except Exception as exc:
                logger.debug("Obsidian step yazma hatası (sessiz): %s", exc)

    except Exception:
        pass  # step_callback asla crew'u durdurmamalı


# ─────────────────────────────────────────────
#  Manuel raporlama yardımcıları
# ─────────────────────────────────────────────

def report_project_start(project_brief: str, project_name: str, agent_count: int):
    """Proje başlangıcında Telegram'a bildirim + vault başlatma."""

    # Vault'u başlat
    try:
        from obsidian_vault import init_vault
        init_vault(project_name=project_name, project_brief=project_brief)
        vault_note = "\n🗂️ _Obsidian vault kaydediliyor..._"
        logger.info("Obsidian vault başlatıldı: %s", project_name)
    except Exception as exc:
        vault_note = ""
        logger.warning("Vault başlatma hatası: %s", exc)

    send_message(
        f"🚀 *Proje Başladı*\n\n"
        f"📋 Brief: _{project_brief[:200]}_\n"
        f"📁 Proje: `output/{project_name}/`\n"
        f"👥 Ajan sayısı: {agent_count}\n"
        f"⚙️ Süreç: Hiyerarşik\n"
        f"📊 Görev sayısı: {15}\n\n"
        f"_Her görev bitişinde otomatik rapor gelecek_ 📩"
        f"{vault_note}"
    )


def report_project_complete(project_name: str, total_files: int, zip_sent: bool):
    """Proje tamamlandığında vault'u finalize et ve bildir."""

    # Vault'u kapat
    vault_added = False
    try:
        from obsidian_vault import finalize_vault
        vault_dir = finalize_vault()
        if vault_dir and vault_dir.exists():
            vault_added = True
            logger.info("Obsidian vault finalize edildi: %s", vault_dir)
    except Exception as exc:
        logger.warning("Vault finalize hatası: %s", exc)

    status = "✅ ZIP gönderildi" if zip_sent else "⚠️ ZIP gönderilemedi"
    vault_status = "📒 Obsidian vault ZIP içinde" if vault_added else "⚠️ Vault eklenemedi"

    send_message(
        f"🏁 *Proje Tamamlandı!*\n\n"
        f"📁 Proje: `{project_name}`\n"
        f"📦 Toplam dosya: {total_files}\n"
        f"📤 ZIP: {status}\n"
        f"{vault_status}\n\n"
        f"_ZIP'i aç → `vault/` klasörünü Obsidian'a sürükle_ 🗂️"
    )


def report_error(agent_role: str, task_name: str, error: str):
    short_label, emoji = _short_label(agent_role)

    # Vault'a hata kaydı
    vault = _get_vault()
    if vault:
        try:
            vault.record_step(
                agent_role=agent_role,
                action_type="error",
                content=f"**Görev:** `{task_name}`\n\n```\n{error[:400]}\n```",
            )
        except Exception:
            pass

    send_message(
        f"❌ *[{short_label}] Hata!*\n\n"
        f"📌 Görev: _{task_name[:80]}_\n"
        f"{'─' * 28}\n"
        f"```\n{error[:600]}\n```"
    )
