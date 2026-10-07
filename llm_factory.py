"""
LLM Factory — CrewAI için LLM instance üretir.

CrewAI'nin kendi LLM sınıfını kullanır (crewai.LLM).
Bu sınıf litellm üzerinden çalışır ve OpenAI-uyumlu
tüm API'lerle direkt entegre olur.

Desteklenen sağlayıcılar:
  evrenllm   → https://evren-llmapi.ssyz.org.tr/v1
  openrouter → https://openrouter.ai/api/v1
  deepseek   → https://api.deepseek.com/v1
  openai     → https://api.openai.com/v1
"""

import os
import logging
import requests
from config import cfg

logger = logging.getLogger(__name__)

EVREN_BASE_URL = "https://evren-llmapi.ssyz.org.tr/v1"

EVREN_REASONING_MODELS = {
    "deepseek-v4.1-flash",
    "deepseek-v4-flash",
    "glm-5.3",
    "mimo-v2.6-pro",
    "qwen3.8-flash-next",
    "gemma-4-31b",
    "auto",
}


def accept_evren_terms(api_key: str) -> bool:
    """Evren LLM kullanım şartlarını otomatik kabul eder."""
    headers = {"X-API-Key": api_key}
    try:
        resp = requests.get(f"{EVREN_BASE_URL}/terms/status", headers=headers, timeout=15)
        data = resp.json()
        if data.get("accepted"):
            logger.info("Evren LLM terms already accepted.")
            return True
        version = data.get("current_version")
        if version is None:
            return False
    except Exception as exc:
        logger.error("Evren terms/status hatası: %s", exc)
        return False

    try:
        resp = requests.post(
            f"{EVREN_BASE_URL}/terms/accept",
            headers={**headers, "Content-Type": "application/json"},
            json={"version": version},
            timeout=15,
        )
        if resp.status_code == 200:
            logger.info("Evren LLM terms accepted: v%s", version)
            return True
        logger.error("Evren terms/accept başarısız: %s", resp.status_code)
        return False
    except Exception as exc:
        logger.error("Evren terms/accept hatası: %s", exc)
        return False


def check_evren_quota(api_key: str) -> dict:
    """Evren LLM günlük kota durumunu sorgular."""
    try:
        resp = requests.get(
            f"{EVREN_BASE_URL}/quota",
            headers={"X-API-Key": api_key},
            timeout=10,
        )
        if resp.status_code == 200:
            return resp.json()
        return {"error": f"HTTP {resp.status_code}"}
    except Exception as exc:
        return {"error": str(exc)}


def build_llm(temperature: float = 0.3):
    """
    CrewAI'nin LLM sınıfını döner.
    crewai.LLM litellm üzerinden çalışır — OpenAI uyumlu tüm API'lerle çalışır.
    """
    from crewai import LLM

    provider = cfg.llm_provider.lower()
    model    = cfg.llm_model
    api_key  = cfg.active_api_key

    if not api_key:
        raise ValueError(
            f"'{provider}' için API key bulunamadı. "
            "/setkey ile ekle."
        )

    # Evren LLM şartlar kontrolü
    if provider == "evrenllm":
        accept_evren_terms(api_key)

        # Kota logla
        quota = check_evren_quota(api_key)
        if "remaining" in quota:
            logger.info("Evren kota: %s token kaldı", quota.get("remaining"))

        is_reasoning = model in EVREN_REASONING_MODELS
        max_tokens   = 8192 if is_reasoning else 4096

        llm = LLM(
            model=f"openai/{model}",
            api_key=api_key,
            base_url=EVREN_BASE_URL,
            temperature=temperature,
            max_tokens=max_tokens,
            extra_headers={"X-API-Key": api_key},
            timeout=300,
        )
        logger.info("CrewAI LLM hazır: evrenllm/%s", model)
        return llm

    elif provider == "openrouter":
        llm = LLM(
            model=f"openrouter/{model}",
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
            temperature=temperature,
            max_tokens=4096,
        )
        logger.info("CrewAI LLM hazır: openrouter/%s", model)
        return llm

    elif provider == "deepseek":
        llm = LLM(
            model=f"openai/{model}",
            api_key=api_key,
            base_url="https://api.deepseek.com/v1",
            temperature=temperature,
            max_tokens=4096,
        )
        logger.info("CrewAI LLM hazır: deepseek/%s", model)
        return llm

    else:
        # OpenAI varsayılan
        llm = LLM(
            model=model,
            api_key=api_key,
            temperature=temperature,
            max_tokens=4096,
        )
        logger.info("CrewAI LLM hazır: openai/%s", model)
        return llm
