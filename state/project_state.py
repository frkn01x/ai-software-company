"""
Project State Persistence
Crew'un tamamladığı görevleri kalıcı olarak saklar.
API kota hatası → yeni key → /resume → kaldığı yerden devam.

State dosyası: state/project_state.json
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)
STATE_FILE = Path(__file__).parent / "project_state.json"


def _now() -> str:
    return datetime.utcnow().isoformat()


# ─────────────────────────────────────────────
#  Temel okuma / yazma
# ─────────────────────────────────────────────

def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning("State dosyası okunamadı, sıfırlanıyor: %s", e)
    return _empty_state()


def _empty_state() -> dict:
    return {
        "created_at":      _now(),
        "updated_at":      _now(),
        "project_brief":   "",
        "project_name":    "",
        "current_task":    None,
        "completed_tasks": [],      # tamamlanan görev ID listesi
        "task_results":    {},      # görev ID → çıktı özeti
        "failed_tasks":    [],      # başarısız görev ID listesi
        "iteration":       0,
        "status":          "idle",  # idle | running | completed | error
        "last_error":      None,
    }


def save_state(state: dict):
    state["updated_at"] = _now()
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


# ─────────────────────────────────────────────
#  Görev durumu güncelleme
# ─────────────────────────────────────────────

def mark_task_complete(task_id: str, result: Any):
    """Görevi tamamlandı olarak işaretle, çıktısını kaydet."""
    state = load_state()
    if task_id not in state["completed_tasks"]:
        state["completed_tasks"].append(task_id)
    # Başarısız listesinden çıkar (retry durumu)
    if task_id in state.get("failed_tasks", []):
        state["failed_tasks"].remove(task_id)
    # Çıktıyı kaydet (max 2000 karakter)
    state["task_results"][task_id] = str(result)[:2000]
    state["current_task"] = None
    logger.info("Görev tamamlandı ve state'e kaydedildi: %s", task_id)
    save_state(state)


def mark_task_started(task_id: str):
    """Görev başladı olarak işaretle."""
    state = load_state()
    state["current_task"] = task_id
    state["status"]       = "running"
    save_state(state)


def mark_task_failed(task_id: str, error: str):
    """Görevi başarısız olarak işaretle."""
    state = load_state()
    if task_id not in state.get("failed_tasks", []):
        state.setdefault("failed_tasks", []).append(task_id)
    state["last_error"] = error
    save_state(state)


def record_error(error: str):
    """Genel hata kaydet (crew seviyesi)."""
    state = load_state()
    state["last_error"] = error
    state["status"]     = "error"
    save_state(state)


# ─────────────────────────────────────────────
#  Görev sorgu fonksiyonları
# ─────────────────────────────────────────────

def is_task_done(task_id: str) -> bool:
    """Bu görev daha önce tamamlandı mı?"""
    return task_id in load_state()["completed_tasks"]


def get_last_result(task_id: str) -> Optional[str]:
    """Tamamlanmış görevin kaydedilmiş çıktısını döner."""
    return load_state()["task_results"].get(task_id)


def get_completed_tasks() -> list[str]:
    """Tamamlanan tüm görev ID'lerini döner."""
    return load_state()["completed_tasks"]


def get_resume_summary() -> dict:
    """
    /resume için özet bilgi döner:
      - completed : tamamlanan görev sayısı
      - skipped   : atlanacak görev listesi
      - remaining : kalan (çalışacak) görev sayısı
    """
    state = load_state()
    completed = state["completed_tasks"]
    return {
        "brief":     state.get("project_brief", ""),
        "name":      state.get("project_name",  ""),
        "status":    state.get("status",         "idle"),
        "completed": completed,
        "count":     len(completed),
        "last_error": state.get("last_error"),
    }


# ─────────────────────────────────────────────
#  State yönetimi
# ─────────────────────────────────────────────

def reset_state():
    """State'i tamamen sıfırla (yeni proje için)."""
    if STATE_FILE.exists():
        STATE_FILE.unlink()
    logger.info("Proje state'i sıfırlandı.")


def bump_iteration():
    """Her resume'da iterasyon sayacını artır."""
    state = load_state()
    state["iteration"] = state.get("iteration", 0) + 1
    save_state(state)
