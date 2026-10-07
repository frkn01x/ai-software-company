"""
Telegram Management Bot
Projeyi Telegram üzerinden yönetir.

  💬 NORMAL MESAJ — /run yazmana gerek yok!
                    Proje isteğini yaz, bot onay ister, ✅ bas, başlar.

  /start        — Komut listesi
  /status       — Proje durumu + kota
  /run <brief>  — Proje başlat
  /resume       — Kaldığı yerden devam
  /setkey <provider> <key>   — API key kaydet
  /switch <provider>         — Provider değiştir
  /setmodel <provider> <model> — Model seç
  /providers    — Provider listesi
  /getconfig    — Mevcut ayarlar
  /reset        — State sıfırla
  /logs         — Son loglar
  /help         — Yardım
"""

import logging
import threading

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import cfg
from state import load_state, reset_state, save_state
from telegram_bot.notifier import send_message

logger = logging.getLogger(__name__)

_project_thread: threading.Thread | None = None

# Onay bekleyen brief'leri geçici olarak sakla
# { user_id: brief_text }
_pending_briefs: dict[int, str] = {}


# ─────────────────────────────────────────────
#  Yetki kontrolü
# ─────────────────────────────────────────────

def _get_allowed_users() -> set[int]:
    raw = cfg.get("TELEGRAM_ALLOWED_USERS", "")
    if not raw:
        return set()
    try:
        return {int(uid.strip()) for uid in raw.split(",") if uid.strip()}
    except ValueError:
        return set()


def _is_allowed(update: Update) -> bool:
    allowed = _get_allowed_users()
    if not allowed:
        return True
    user_id = update.effective_user.id if update.effective_user else None
    return user_id in allowed


async def _reject(update: Update):
    logger.warning("Yetkisiz erişim: user_id=%s",
                   update.effective_user.id if update.effective_user else "?")
    if update.message:
        await update.message.reply_text("⛔ Bu bot özel kullanıma aittir.")
    elif update.callback_query:
        await update.callback_query.answer("⛔ Yetkisiz erişim.", show_alert=True)


# ─────────────────────────────────────────────
#  Komutlar
# ─────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_allowed(update):
        await _reject(update)
        return
    text = (
        "👋 *AI Software Company Bot*\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "💬 *En kolay yol:* Sadece proje isteğini yaz!\n"
        "   _\"Bir blog sitesi yap, yorum ve beğeni olsun\"_\n"
        "   Bot onay ister, ✅ bas, proje başlar.\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🚀 `/run <açıklama>` — Direkt proje başlat\n"
        "▶️ `/resume` — Kaldığı yerden devam et\n"
        "📊 `/status` — Durum + kota bilgisi\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🔀 `/switch <provider>` — LLM değiştir\n"
        "   `evrenllm` · `openrouter` · `deepseek` · `openai`\n\n"
        "🔑 `/setkey <provider> <key>` — API key kaydet\n"
        "🤖 `/setmodel <provider> <model>` — Model seç\n"
        "📋 `/providers` — Provider ve key durumu\n"
        "⚙️ `/getconfig` — Mevcut ayarlar\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🔄 `/reset` — Proje state sıfırla\n"
        "📜 `/logs` — Son loglar\n"
        "❓ `/help` — Bu mesaj\n"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_allowed(update):
        await _reject(update)
        return

    state = load_state()
    status  = state.get("status", "idle")
    current = state.get("current_task", "—")
    done    = state.get("completed_tasks", [])
    pending = state.get("pending_tasks", [])
    updated = state.get("updated_at", "—")
    err     = state.get("last_error", None)

    icons = {"idle": "💤", "running": "⚙️", "completed": "✅", "error": "❌"}
    icon  = icons.get(status, "❓")

    text = (
        f"{icon} *Proje Durumu: {status.upper()}*\n\n"
        f"🕐 Son güncelleme: `{updated}`\n"
        f"📌 Aktif görev: `{current}`\n"
        f"✅ Tamamlanan: {len(done)} görev\n"
        f"⏳ Bekleyen: {len(pending)} görev\n"
    )
    if done:
        text += "\n*Tamamlananlar:*\n" + "\n".join(f"  ✓ {t}" for t in done[:10])
    if err:
        text += f"\n\n⚠️ *Son hata:*\n```\n{err[:300]}\n```"

    if cfg.llm_provider == "evrenllm" and cfg.evrenllm_api_key:
        try:
            from llm_factory import check_evren_quota
            quota = check_evren_quota(cfg.evrenllm_api_key)
            if "remaining" in quota:
                text += (
                    f"\n\n🔋 *Evren LLM Kota:*\n"
                    f"  Kalan: `{quota['remaining']:,}` token\n"
                    f"  Sıfırlanma: `{quota.get('reset_at', '?')}`"
                )
        except Exception:
            pass

    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_run(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global _project_thread
    if not _is_allowed(update):
        await _reject(update)
        return

    if not context.args:
        await update.message.reply_text(
            "❌ Kullanım: `/run <proje açıklaması>`\n"
            "Örnek: `/run E-ticaret sitesi, ürün listeleme ve sepet`",
            parse_mode="Markdown",
        )
        return

    if _project_thread and _project_thread.is_alive():
        await update.message.reply_text(
            "⚠️ Zaten çalışan bir proje var.\n`/reset` ile durdur, sonra tekrar dene."
        )
        return

    brief = " ".join(context.args)
    await update.message.reply_text(
        f"🚀 *Proje başlatılıyor...*\n\n📋 Brief:\n_{brief}_",
        parse_mode="Markdown",
    )

    def run_in_thread():
        from crew_manager import run_project
        run_project(brief)

    _project_thread = threading.Thread(target=run_in_thread, daemon=True)
    _project_thread.start()


async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global _project_thread
    if not _is_allowed(update):
        await _reject(update)
        return

    state = load_state()
    brief = state.get("project_brief", "")

    if not brief:
        await update.message.reply_text("❌ Devam edilecek proje bulunamadı.")
        return
    if _project_thread and _project_thread.is_alive():
        await update.message.reply_text("⚠️ Proje zaten çalışıyor.")
        return

    completed = state.get("completed_tasks", [])
    await update.message.reply_text(
        f"▶️ *Proje devam ediyor...*\n\n"
        f"📋 Brief: _{brief[:200]}_\n"
        f"✅ {len(completed)} tamamlanan görev atlanıyor.",
        parse_mode="Markdown",
    )

    def run_in_thread():
        from crew_manager import run_project
        run_project(brief)

    _project_thread = threading.Thread(target=run_in_thread, daemon=True)
    _project_thread.start()


async def cmd_setkey(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_allowed(update):
        await _reject(update)
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "❌ Kullanım: `/setkey <provider> <key>`\n\n"
            "Örnekler:\n"
            "  `/setkey evrenllm evren_llm_...`\n"
            "  `/setkey openrouter sk-or-...`\n"
            "  `/setkey deepseek sk-...`\n"
            "  `/setkey openai sk-...`",
            parse_mode="Markdown",
        )
        return

    provider = context.args[0].lower()
    api_key  = context.args[1]

    provider_env_map = {
        "openai":     "OPENAI_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
        "deepseek":   "DEEPSEEK_API_KEY",
        "evrenllm":   "EVRENLLM_API_KEY",
        "github":     "GITHUB_TOKEN",
        "serper":     "SERPER_API_KEY",
    }

    if provider not in provider_env_map:
        await update.message.reply_text(
            f"❌ Geçersiz provider: `{provider}`\n"
            f"Geçerliler: {' · '.join(provider_env_map.keys())}",
            parse_mode="Markdown",
        )
        return

    cfg.set(provider_env_map[provider], api_key, persist=True)

    try:
        await update.message.delete()
    except Exception:
        pass

    masked = api_key[:8] + "..." + api_key[-4:] if len(api_key) > 12 else "***"

    # Hata durumundaki projede otomatik resume
    global _project_thread
    state = load_state()
    resume_msg = ""
    if state.get("status") == "error" and state.get("project_brief"):
        if not (_project_thread and _project_thread.is_alive()):
            brief = state["project_brief"]
            if provider != cfg.llm_provider:
                cfg.set("LLM_PROVIDER", provider, persist=True)
            resume_msg = "\n\n▶️ *Proje otomatik devam ediyor!*"

            def run_in_thread():
                from crew_manager import run_project
                run_project(brief)

            _project_thread = threading.Thread(target=run_in_thread, daemon=True)
            _project_thread.start()

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=(
            f"✅ *API Key Kaydedildi*\n\n"
            f"🔑 Provider: `{provider}`\n"
            f"🔒 Key: `{masked}`\n"
            f"⚙️ Aktif: `{cfg.llm_provider}`"
            + resume_msg
        ),
        parse_mode="Markdown",
    )


async def cmd_switch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_allowed(update):
        await _reject(update)
        return

    PROVIDERS = {
        "evrenllm":   ("EVRENLLM_API_KEY",  "evren_llm_...", "deepseek-v4.1-flash"),
        "openrouter": ("OPENROUTER_API_KEY", "sk-or-...",     "openai/gpt-4o"),
        "deepseek":   ("DEEPSEEK_API_KEY",   "sk-...",        "deepseek-chat"),
        "openai":     ("OPENAI_API_KEY",     "sk-...",        "gpt-4o"),
    }

    def mask(val):
        if not val:
            return None
        return val[:6] + "..." + val[-4:] if len(val) > 10 else "***"

    if not context.args:
        lines = ["🔀 *Provider Seç*\n\nKullanım: `/switch <provider>`\n"]
        for p, (env, fmt, model) in PROVIDERS.items():
            key_val = cfg.get(env)
            active  = " ◀ *AKTİF*" if p == cfg.llm_provider else ""
            icon    = "✅" if key_val else "❌"
            lines.append(f"{icon} `{p}`{active}\n   Model: `{model}`")
            if key_val:
                lines.append(f"   Key: `{mask(key_val)}`")
            else:
                lines.append(f"   Key yok → `/setkey {p} {fmt}`")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
        return

    provider = context.args[0].lower()
    if provider not in PROVIDERS:
        await update.message.reply_text(
            f"❌ Geçersiz: `{provider}`\nGeçerliler: {' · '.join(PROVIDERS.keys())}",
            parse_mode="Markdown",
        )
        return

    env_key, key_fmt, default_model = PROVIDERS[provider]
    if not cfg.get(env_key):
        await update.message.reply_text(
            f"⚠️ `{provider}` için key yok!\n"
            f"`/setkey {provider} {key_fmt}`",
            parse_mode="Markdown",
        )
        return

    old = cfg.llm_provider
    cfg.set("LLM_PROVIDER", provider, persist=True)

    # Model uyumsuzsa sıfırla
    model_note = ""
    cur = cfg.llm_model
    needs_reset = (
        (provider == "evrenllm"   and not any(m in cur for m in ["deepseek","glm","mimo","gemma","qwen","auto"])) or
        (provider == "openrouter" and "/" not in cur) or
        (provider == "deepseek"   and "deepseek" not in cur.lower()) or
        (provider == "openai"     and not cur.startswith("gpt"))
    )
    if needs_reset:
        cfg.set("LLM_MODEL", default_model, persist=True)
        model_note = f"\n🔄 Model `{default_model}` olarak sıfırlandı."

    await update.message.reply_text(
        f"✅ *Provider Değiştirildi*\n\n"
        f"📤 Eski: `{old}`\n"
        f"📥 Yeni: `{provider}`\n"
        f"🧠 Model: `{cfg.llm_model}`"
        f"{model_note}",
        parse_mode="Markdown",
    )


async def cmd_providers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_allowed(update):
        await _reject(update)
        return

    ENVS = {
        "evrenllm":   "EVRENLLM_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
        "deepseek":   "DEEPSEEK_API_KEY",
        "openai":     "OPENAI_API_KEY",
    }
    MODELS = {
        "evrenllm":   "deepseek-v4.1-flash · glm-5.3 · auto",
        "openrouter": "openai/gpt-4o · claude-3.5-sonnet",
        "deepseek":   "deepseek-chat · deepseek-coder",
        "openai":     "gpt-4o · gpt-4o-mini",
    }

    def mask(val):
        if not val:
            return "❌ Kayıtlı key yok"
        return f"✅ `{val[:6]}...{val[-4:]}`" if len(val) > 10 else "✅ `***`"

    lines = ["📋 *Provider Durumu*\n"]
    for p, env in ENVS.items():
        active = " ◀ *AKTİF*" if p == cfg.llm_provider else ""
        prefix = "▶️" if p == cfg.llm_provider else "  "
        lines.append(
            f"{prefix} *{p}*{active}\n"
            f"   Key: {mask(cfg.get(env))}\n"
            f"   Modeller: _{MODELS[p]}_\n"
        )

    lines.append(f"━━━━━━━━━━━━━━━━━━━")
    lines.append(f"🧠 Aktif model: `{cfg.llm_model}`")

    if cfg.llm_provider == "evrenllm" and cfg.evrenllm_api_key:
        try:
            from llm_factory import check_evren_quota
            quota = check_evren_quota(cfg.evrenllm_api_key)
            if "remaining" in quota:
                lines.append(
                    f"\n🔋 *Evren Kota:* `{quota['remaining']:,}` token kaldı\n"
                    f"  Sıfırlanma: `{quota.get('reset_at','?')}`"
                )
        except Exception:
            pass

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_setmodel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_allowed(update):
        await _reject(update)
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "❌ Kullanım: `/setmodel <provider> <model>`\n\n"
            "*EvrenLLM:*\n"
            "  `deepseek-v4.1-flash` · `glm-5.3` · `mimo-v2.6-pro`\n"
            "  `gemma-4-31b` · `qwen3.8-flash-next` · `auto`\n\n"
            "*Diğer:*\n"
            "  `/setmodel openai gpt-4o`\n"
            "  `/setmodel openrouter anthropic/claude-3.5-sonnet`",
            parse_mode="Markdown",
        )
        return

    provider = context.args[0].lower()
    model    = context.args[1]
    cfg.set("LLM_PROVIDER", provider, persist=True)
    cfg.set("LLM_MODEL",    model,    persist=True)

    await update.message.reply_text(
        f"✅ *Model Güncellendi*\n\n"
        f"🤖 Provider: `{provider}`\n"
        f"🧠 Model: `{model}`",
        parse_mode="Markdown",
    )


async def cmd_getconfig(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_allowed(update):
        await _reject(update)
        return

    def mask(val):
        if not val:
            return "❌ Yok"
        return val[:6] + "..." + val[-4:] if len(val) > 12 else "***"

    text = (
        "⚙️ *Konfigürasyon*\n\n"
        f"🔧 Provider: `{cfg.llm_provider}`\n"
        f"🧠 Model: `{cfg.llm_model}`\n\n"
        f"OpenAI: `{mask(cfg.openai_api_key)}`\n"
        f"OpenRouter: `{mask(cfg.openrouter_api_key)}`\n"
        f"DeepSeek: `{mask(cfg.deepseek_api_key)}`\n"
        f"EvrenLLM: `{mask(cfg.evrenllm_api_key)}`\n"
        f"E2B: `{mask(cfg.e2b_api_key)}`\n"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_allowed(update):
        await _reject(update)
        return
    reset_state()
    await update.message.reply_text(
        "🔄 *Proje durumu sıfırlandı.*\n\nYeni proje için bir şey yaz.",
        parse_mode="Markdown",
    )


async def cmd_logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_allowed(update):
        await _reject(update)
        return

    import os
    log_file = "logs/crew_output.log"
    if not os.path.exists(log_file):
        await update.message.reply_text("📜 Log henüz yok.")
        return

    with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    last = "".join(lines[-50:])
    await update.message.reply_text(
        f"📜 *Son Loglar*\n```\n{last[:3500]}\n```",
        parse_mode="Markdown",
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await cmd_start(update, context)


# ─────────────────────────────────────────────
#  Normal metin → proje onayı
# ─────────────────────────────────────────────

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_allowed(update):
        await _reject(update)
        return

    text = update.message.text.strip()

    if len(text) < 10:
        await update.message.reply_text(
            "💬 Biraz daha açar mısın? _(En az 10 karakter)_",
            parse_mode="Markdown",
        )
        return

    if _project_thread and _project_thread.is_alive():
        await update.message.reply_text(
            "⚠️ Aktif proje var!\n`/reset` ile durdur, sonra tekrar yaz.",
            parse_mode="Markdown",
        )
        return

    # Yarım kalmış proje varsa seçenek sun
    state = load_state()
    if state.get("status") == "error" and state.get("project_brief"):
        old_brief = state["project_brief"][:100]
        user_id = update.effective_user.id
        _pending_briefs[user_id] = text   # yeni brief'i sakla
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("▶️ Eski Projeyi Devam Ettir", callback_data="action:resume"),
                InlineKeyboardButton("🆕 Yeni Proje Başlat",        callback_data="action:confirm"),
            ],
            [InlineKeyboardButton("❌ İptal", callback_data="action:cancel")],
        ])
        await update.message.reply_text(
            f"⚠️ *Yarım kalmış proje var!*\n\n"
            f"📋 Eski: _{old_brief}..._\n\nNe yapmak istersin?",
            parse_mode="Markdown",
            reply_markup=keyboard,
        )
        return

    # Normal onay butonu
    user_id  = update.effective_user.id
    _pending_briefs[user_id] = text   # brief'i sakla, callback_data'ya koyma
    preview  = text[:200] + ("..." if len(text) > 200 else "")
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Evet, Başlat!", callback_data="action:confirm"),
            InlineKeyboardButton("❌ İptal",         callback_data="action:cancel"),
        ],
        [InlineKeyboardButton("✏️ Brief'i Düzenle", callback_data="action:edit")],
    ])

    await update.message.reply_text(
        f"💡 *Proje talebini anladım!*\n\n"
        f"📋 *Brief:*\n_{preview}_\n\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🤖 `{cfg.llm_provider}` / `{cfg.llm_model}`\n"
        f"👥 18 ajan hazır\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"Başlatayım mı?",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


# ─────────────────────────────────────────────
#  Inline buton callback'leri
# ─────────────────────────────────────────────

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global _project_thread
    if not _is_allowed(update):
        await _reject(update)
        return

    query = update.callback_query
    await query.answer()
    data  = query.data or ""

    if data.startswith("action:confirm"):
        # Brief'i _pending_briefs'ten al
        user_id = update.effective_user.id
        brief   = _pending_briefs.pop(user_id, "")

        if not brief:
            await query.edit_message_text(
                "❌ Brief bulunamadı. Lütfen tekrar yaz.",
                parse_mode="Markdown",
            )
            return
        if _project_thread and _project_thread.is_alive():
            await query.edit_message_text("⚠️ Zaten çalışan bir proje var!")
            return
        await query.edit_message_text(
            f"🚀 *Proje başlatılıyor!*\n\n📋 _{brief[:200]}_\n\n"
            f"_Her görev bitişinde rapor gelecek_ 📩",
            parse_mode="Markdown",
        )
        def run():
            from crew_manager import run_project
            run_project(brief)
        _project_thread = threading.Thread(target=run, daemon=True)
        _project_thread.start()

    elif data == "action:resume":
        state = load_state()
        brief = state.get("project_brief", "")
        if not brief:
            await query.edit_message_text("❌ Devam edilecek proje yok.")
            return
        if _project_thread and _project_thread.is_alive():
            await query.edit_message_text("⚠️ Proje zaten çalışıyor.")
            return
        completed = state.get("completed_tasks", [])
        await query.edit_message_text(
            f"▶️ *Devam ediyor...*\n✅ {len(completed)} görev atlanıyor.",
            parse_mode="Markdown",
        )
        def run():
            from crew_manager import run_project
            run_project(brief)
        _project_thread = threading.Thread(target=run, daemon=True)
        _project_thread.start()

    elif data == "action:cancel":
        await query.edit_message_text("❌ İptal edildi. Yeni istek için tekrar yaz.")

    elif data == "action:edit":
        await query.edit_message_text(
            "✏️ *Brief'i düzenle*\n\nProje açıklamanı tekrar yaz.",
            parse_mode="Markdown",
        )


async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❓ Bilinmeyen komut. `/help` ile listeye bak.\n\n"
        "💡 Ya da direkt proje isteğini yaz.",
        parse_mode="Markdown",
    )


# ─────────────────────────────────────────────
#  Bot başlatma
# ─────────────────────────────────────────────

def run_bot():
    token = cfg.telegram_token
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN eksik!")
        return

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start",     cmd_start))
    app.add_handler(CommandHandler("status",    cmd_status))
    app.add_handler(CommandHandler("run",       cmd_run))
    app.add_handler(CommandHandler("resume",    cmd_resume))
    app.add_handler(CommandHandler("setkey",    cmd_setkey))
    app.add_handler(CommandHandler("switch",    cmd_switch))
    app.add_handler(CommandHandler("providers", cmd_providers))
    app.add_handler(CommandHandler("setmodel",  cmd_setmodel))
    app.add_handler(CommandHandler("getconfig", cmd_getconfig))
    app.add_handler(CommandHandler("reset",     cmd_reset))
    app.add_handler(CommandHandler("logs",      cmd_logs))
    app.add_handler(CommandHandler("help",      cmd_help))
    app.add_handler(MessageHandler(filters.COMMAND, unknown_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    app.add_handler(CallbackQueryHandler(handle_callback_query, pattern="^action:"))

    logger.info("Telegram bot başlatılıyor...")
    send_message("🤖 *AI Software Company Bot aktif!*\n/help ile komutları gör.")
    app.run_polling(drop_pending_updates=True)
