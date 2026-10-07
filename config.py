"""
Configuration manager - API keys, model selection, state persistence.
API keys are managed via Telegram bot commands too.
"""

import os
import json
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

STATE_DIR = Path(__file__).parent / "state"
STATE_DIR.mkdir(exist_ok=True)

CONFIG_FILE = STATE_DIR / "config.json"


def _load_config() -> dict:
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_config(data: dict):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


class Config:
    """
    Centralized config. Priority: runtime (in-memory) > config.json > .env
    Supports hot-reload of API keys without restarting.
    """

    def __init__(self):
        self._runtime: dict = {}
        self._file_cfg: dict = _load_config()

    def reload(self):
        self._file_cfg = _load_config()

    # ------------------------------------------------------------------ #
    #  Generic getter                                                       #
    # ------------------------------------------------------------------ #
    def get(self, key: str, default=None):
        return (
            self._runtime.get(key)
            or self._file_cfg.get(key)
            or os.getenv(key, default)
        )

    def set(self, key: str, value: str, persist: bool = True):
        """Set a config value; persists to disk by default."""
        self._runtime[key] = value
        if persist:
            self._file_cfg[key] = value
            _save_config(self._file_cfg)

    # ------------------------------------------------------------------ #
    #  Model selection                                                      #
    # ------------------------------------------------------------------ #
    @property
    def llm_provider(self) -> str:
        """openai | openrouter | deepseek | evrenllm"""
        return self.get("LLM_PROVIDER", "openai")

    @property
    def llm_model(self) -> str:
        defaults = {
            "openai":      "gpt-4o",
            "openrouter":  "openai/gpt-4o",
            "deepseek":    "deepseek-chat",
            # Evren LLM model isimleri (api_name formatı):
            # deepseek-v4.1-flash | glm-5.3 | mimo-v2.6-pro
            # gemma-4-31b | qwen3.8-flash-next | auto
            "evrenllm":    "deepseek-v4.1-flash",
        }
        return self.get("LLM_MODEL", defaults.get(self.llm_provider, "gpt-4o"))

    @property
    def openai_api_key(self) -> Optional[str]:
        return self.get("OPENAI_API_KEY")

    @property
    def openrouter_api_key(self) -> Optional[str]:
        return self.get("OPENROUTER_API_KEY")

    @property
    def deepseek_api_key(self) -> Optional[str]:
        return self.get("DEEPSEEK_API_KEY")

    @property
    def evrenllm_api_key(self) -> Optional[str]:
        return self.get("EVRENLLM_API_KEY")

    @property
    def active_api_key(self) -> Optional[str]:
        mapping = {
            "openai":     self.openai_api_key,
            "openrouter": self.openrouter_api_key,
            "deepseek":   self.deepseek_api_key,
            "evrenllm":   self.evrenllm_api_key,
        }
        return mapping.get(self.llm_provider)

    # ------------------------------------------------------------------ #
    #  Telegram                                                             #
    # ------------------------------------------------------------------ #
    @property
    def telegram_token(self) -> Optional[str]:
        return self.get("TELEGRAM_BOT_TOKEN")

    @property
    def telegram_chat_id(self) -> Optional[str]:
        return self.get("TELEGRAM_CHAT_ID")

    # ------------------------------------------------------------------ #
    #  E2B                                                                  #
    # ------------------------------------------------------------------ #
    @property
    def e2b_api_key(self) -> Optional[str]:
        return self.get("E2B_API_KEY")

    # ------------------------------------------------------------------ #
    #  Project state                                                        #
    # ------------------------------------------------------------------ #
    @property
    def project_state_file(self) -> Path:
        return STATE_DIR / "project_state.json"


cfg = Config()
