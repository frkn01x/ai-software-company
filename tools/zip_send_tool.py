"""
ZipAndSendTool — Proje çıktı klasörünü + Obsidian vault'ı zip'ler,
                  Telegram'a dosya olarak gönderir.

ZIP içeriği:
  project_name/          ← ajanların ürettiği kod dosyaları
    index.html
    backend/
    docs/
    ...
  vault/                 ← Obsidian vault (sürükle-bırak ile açılır)
    _index.md
    agents/
    conversations/
    decisions/
    tasks/
    timeline.md
    project_graph.md

Telegram bot limiti: 50 MB
"""

import io
import logging
import zipfile
import requests
from pathlib import Path
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from config import cfg
from tools.file_writer_tool import OUTPUT_DIR

logger = logging.getLogger(__name__)

# Zip'e eklenmeyen dosya/klasörler
EXCLUDE_PARTS = {"__pycache__", ".git", "node_modules"}
EXCLUDE_SUFFIXES = {".pyc", ".pyo", ".log"}
EXCLUDE_NAMES = {".DS_Store", ".env", "Thumbs.db"}


class ZipSendInput(BaseModel):
    project_name: str = Field(
        default="project",
        description="Zip'lenecek projenin adı (output/<project_name>/ klasörü).",
    )
    zip_filename: str = Field(
        default="",
        description="Telegram'a gönderilecek zip adı. Boş → '<project_name>.zip'.",
    )
    caption: str = Field(
        default="",
        description="Zip ile birlikte gönderilecek açıklama mesajı.",
    )
    include_vault: bool = Field(
        default=True,
        description="Obsidian vault'u ZIP'e ekle (vault/ klasörü). Varsayılan: True.",
    )


class ZipAndSendTool(BaseTool):
    name: str = "zip_and_send"
    description: str = (
        "Proje çıktı dosyalarını (HTML, CSS, JS, Python vb.) ve "
        "Obsidian vault'ını (ajan konuşmaları, kararlar, timeline) zip'ler, "
        "Telegram'a dosya olarak gönderir. "
        "Tüm görevler tamamlandıktan sonra çağır."
    )
    args_schema: type[BaseModel] = ZipSendInput

    def _run(
        self,
        project_name: str = "project",
        zip_filename: str = "",
        caption: str = "",
        include_vault: bool = True,
    ) -> str:
        project_dir = OUTPUT_DIR / project_name

        if not project_dir.exists():
            return (
                f"❌ Proje klasörü bulunamadı: `{project_dir}`\n"
                "Önce file_writer ile dosyaları oluştur."
            )

        # ── Proje dosyalarını topla ────────────────────────────────────
        project_files = _collect_files(project_dir)
        if not project_files:
            return f"❌ `{project_dir}` içinde hiç dosya yok."

        # ── Vault dosyalarını topla ────────────────────────────────────
        vault_files: list[tuple[Path, str]] = []
        vault_file_count = 0

        if include_vault:
            vault_dir = _get_vault_dir(project_name)
            if vault_dir and vault_dir.exists():
                vault_raw = _collect_files(vault_dir)
                # Vault dosyaları "vault/" prefix'iyle ZIP'e girer
                vault_files = [
                    (fp, f"vault/{fp.relative_to(vault_dir)}")
                    for fp in vault_raw
                ]
                vault_file_count = len(vault_files)
                logger.info("Vault %d dosya ZIP'e eklenecek.", vault_file_count)
            else:
                logger.info("Vault klasörü bulunamadı, sadece proje dosyaları ekleniyor.")

        # ── ZIP oluştur ────────────────────────────────────────────────
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:

            # 1. Proje dosyaları → project_name/ altına
            for fp in project_files:
                arcname = f"{project_name}/{fp.relative_to(project_dir)}"
                zf.write(fp, arcname)

            # 2. Vault dosyaları → vault/ altına
            for fp, arcname in vault_files:
                zf.write(fp, arcname)

            # 3. Vault README (vault yoksa da bilgi ver)
            if vault_file_count == 0:
                vault_readme = (
                    "# Obsidian Vault\n\n"
                    "Bu projede vault henüz oluşturulmadı veya boş.\n"
                    "Vault sistemi `obsidian_vault.py` ile yönetilir.\n"
                )
                zf.writestr("vault/README.md", vault_readme)

            # 4. ZIP içi README
            zip_readme = _build_zip_readme(
                project_name=project_name,
                project_file_count=len(project_files),
                vault_file_count=vault_file_count,
            )
            zf.writestr("README.md", zip_readme)

        zip_buffer.seek(0)
        zip_bytes = zip_buffer.read()
        size_kb   = round(len(zip_bytes) / 1024, 1)
        size_mb   = round(len(zip_bytes) / 1024 / 1024, 2)

        if len(zip_bytes) > 50 * 1024 * 1024:
            # 50 MB aşıldıysa vault'suz tekrar dene
            if include_vault and vault_file_count > 0:
                logger.warning("ZIP %s MB — vault olmadan tekrar deneniyor.", size_mb)
                return self._run(
                    project_name=project_name,
                    zip_filename=zip_filename,
                    caption=caption,
                    include_vault=False,
                )
            return f"❌ ZIP {size_mb} MB — Telegram limiti (50 MB) aşıldı."

        fname = zip_filename or f"{project_name}.zip"

        # ── Telegram'a gönder ──────────────────────────────────────────
        token   = cfg.telegram_token
        chat_id = cfg.telegram_chat_id

        if not token or not chat_id:
            return "❌ Telegram token veya chat_id eksik. .env kontrol et."

        vault_note = f"\n📒 Obsidian vault: {vault_file_count} dosya" if vault_file_count > 0 else ""
        cap = caption or (
            f"📦 *{fname}* hazır!\n"
            f"📁 Proje: {len(project_files)} dosya\n"
            f"{vault_note}\n"
            f"💾 {size_kb} KB\n\n"
            f"_Vault için: ZIP aç → `vault/` klasörünü Obsidian'a sürükle_ 🗂️"
        )

        url = f"https://api.telegram.org/bot{token}/sendDocument"
        try:
            resp = requests.post(
                url,
                data={"chat_id": chat_id, "caption": cap, "parse_mode": "Markdown"},
                files={"document": (fname, zip_bytes, "application/zip")},
                timeout=90,
            )
            resp.raise_for_status()
            logger.info("ZIP Telegram'a gönderildi: %s (%s KB)", fname, size_kb)
            return (
                f"✅ ZIP Telegram'a gönderildi!\n"
                f"📦 Dosya: `{fname}`\n"
                f"📁 Proje dosyaları: {len(project_files)}\n"
                f"📒 Vault dosyaları: {vault_file_count}\n"
                f"💾 Toplam: {size_kb} KB"
            )
        except requests.HTTPError as exc:
            logger.error("Telegram HTTP hatası: %s — %s", exc, exc.response.text[:200])
            return f"❌ Telegram HTTP hatası: {exc}"
        except Exception as exc:
            logger.error("ZIP gönderme hatası: %s", exc)
            return f"❌ Telegram'a gönderilemedi: {exc}"


# ──────────────────────────────────────────────────────────────────────────────
#  Yardımcı fonksiyonlar
# ──────────────────────────────────────────────────────────────────────────────

def _collect_files(directory: Path) -> list[Path]:
    """Dizindeki tüm geçerli dosyaları toplar."""
    result = []
    for fp in directory.rglob("*"):
        if not fp.is_file():
            continue
        # Exclude kontrolleri
        if any(part in EXCLUDE_PARTS for part in fp.parts):
            continue
        if fp.suffix in EXCLUDE_SUFFIXES:
            continue
        if fp.name in EXCLUDE_NAMES:
            continue
        result.append(fp)
    return result


def _get_vault_dir(project_name: str) -> Path | None:
    """Aktif vault dizinini bul."""
    try:
        # Önce aktif vault singleton'dan dene
        from obsidian_vault import get_vault
        vault = get_vault()
        if vault and vault.vault_dir.exists():
            return vault.vault_dir
    except Exception:
        pass

    # Fallback: bilinen konuma bak
    from pathlib import Path as P
    vault_base = P(__file__).parent.parent / "vault"
    candidate  = vault_base / project_name
    if candidate.exists():
        return candidate

    # Herhangi bir vault klasörü var mı?
    if vault_base.exists():
        subdirs = [d for d in vault_base.iterdir() if d.is_dir()]
        if subdirs:
            # En son değiştirilenini al
            return max(subdirs, key=lambda d: d.stat().st_mtime)

    return None


def _build_zip_readme(project_name: str, project_file_count: int, vault_file_count: int) -> str:
    """ZIP içine eklenen README.md içeriğini üretir."""
    from datetime import datetime
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    return f"""# {project_name} — AI Software Company Çıktısı

**Oluşturuldu:** {ts}
**Proje dosyaları:** {project_file_count}
**Obsidian vault dosyaları:** {vault_file_count}

---

## 📁 ZIP İçeriği

```
{project_name}/          ← Ajanların ürettiği kod ve dökümanlar
  index.html             ← Frontend
  styles/main.css
  js/app.js
  backend/               ← Python API
  db/                    ← Veritabanı şemaları
  docs/                  ← Tüm raporlar (PRD, ADR, security, test...)
  Dockerfile
  docker-compose.yml
  README.md

vault/                   ← Obsidian Vault (ajan konuşmaları)
  _index.md              ← Ana sayfa
  agents/                ← 18 ajan profili
  conversations/         ← Ajanlar arası bilgi akışı
  decisions/             ← ADR (Architecture Decision Records)
  tasks/                 ← Her görevin detaylı kaydı
  timeline.md            ← Kronolojik tüm olaylar
  project_graph.md       ← Mermaid bağlantı grafiği
```

---

## 🗂️ Obsidian Vault Nasıl Açılır?

1. [Obsidian](https://obsidian.md)'ı indir (ücretsiz)
2. ZIP'i aç
3. Obsidian → "Open folder as vault"
4. `vault/` klasörünü seç
5. `_index.md` ana sayfasından başla
6. **Graph View** ile ajan bağlantılarını görselleştir

---

## 🚀 Projeyi Çalıştır

```bash
cd {project_name}
cp .env.example .env
docker compose up -d
```

---
*AI Software Company — 18 ajan, CrewAI hiyerarşik süreç*
"""


def zip_project_to_bytes(project_name: str = "project", include_vault: bool = True) -> tuple[bytes, int]:
    """
    Harici kullanım için zip bytes + dosya sayısı döner.
    Returns: (zip_bytes, total_file_count)
    """
    project_dir = OUTPUT_DIR / project_name
    if not project_dir.exists():
        return b"", 0

    buf   = io.BytesIO()
    count = 0

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for fp in _collect_files(project_dir):
            zf.write(fp, f"{project_name}/{fp.relative_to(project_dir)}")
            count += 1

        if include_vault:
            vault_dir = _get_vault_dir(project_name)
            if vault_dir:
                for fp in _collect_files(vault_dir):
                    zf.write(fp, f"vault/{fp.relative_to(vault_dir)}")
                    count += 1

    buf.seek(0)
    return buf.read(), count
