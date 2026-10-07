"""
AI Software Company — Ana Giriş Noktası
Telegram botu ve CrewAI sistemini başlatır.

Çalıştırmak için:
  python main.py

Docker ile:
  docker compose up -d
"""

import logging
import sys
import os
from pathlib import Path

# ─── Logging kurulumu ─────────────────────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
Path("logs").mkdir(exist_ok=True)

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/app.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


def check_required_config():
    """Kritik config'lerin varlığını kontrol eder."""
    from config import cfg

    errors = []
    if not cfg.telegram_token:
        errors.append("TELEGRAM_BOT_TOKEN eksik")
    if not cfg.telegram_chat_id:
        errors.append("TELEGRAM_CHAT_ID eksik")
    if not cfg.active_api_key:
        errors.append(
            f"'{cfg.llm_provider}' için API key eksik. "
            f"Beklenen env var: "
            f"OPENAI_API_KEY / OPENROUTER_API_KEY / DEEPSEEK_API_KEY / EVRENLLM_API_KEY"
        )
    if not cfg.e2b_api_key:
        errors.append("E2B_API_KEY eksik (E2B sandbox çalışmaz)")

    if errors:
        logger.warning("Eksik konfigürasyonlar:")
        for err in errors:
            logger.warning("  ⚠️  %s", err)
        if not cfg.telegram_token:
            logger.error("TELEGRAM_BOT_TOKEN olmadan bot başlatılamaz. Çıkılıyor.")
            sys.exit(1)

    return len(errors) == 0


def print_banner():
    banner = r"""
  ___  ___ ___       __ _                           
 / _ \/ _ \_ _|     / _\ |__   ___  _ __  ___  ___ 
/ /_\/ /_)/  /____ / /\| '_ \ / _ \| '_ \/ __|/ _ \
/ /_\/ ___// /_____/ /  | | | | (_) | |_) \__ \  __/
\____\/   /___| \____|  |_| |_|\___/| .__/|___/\___|
                                     |_|             
    AI Software Company — Multi-Agent Crew
    Powered by CrewAI + E2B + Telegram
    """
    print(banner)


def main():
    print_banner()
    logger.info("AI Software Company başlatılıyor...")

    # Config kontrol
    all_ok = check_required_config()
    if all_ok:
        logger.info("✅ Tüm konfigürasyonlar tamam.")
    else:
        logger.info("⚠️  Bazı konfigürasyonlar eksik (yukarıya bak). Bot yine de başlıyor.")

    logger.info("Aktif LLM: provider=%s, model=%s",
                __import__('config').cfg.llm_provider,
                __import__('config').cfg.llm_model)

    # Telegram bot'u başlat (blocking — ana thread'de çalışır)
    from telegram_bot.bot import run_bot
    logger.info("Telegram bot başlatılıyor...")
    run_bot()


if __name__ == "__main__":
    main()
