"""
FileWriterTool — Ajanın ürettiği kodu gerçek dosyaya yazar.

Ajan "index.html yaz" dedi mi dosya diske düşer.
Tüm çıktılar  output/<proje-adı>/  klasörüne kaydedilir.
"""

import logging
from pathlib import Path
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Tüm proje çıktıları buraya
OUTPUT_DIR = Path(__file__).parent.parent / "output"


class FileWriterInput(BaseModel):
    filepath: str = Field(
        description=(
            "Kaydedilecek dosyanın yolu. "
            "Örn: 'index.html', 'src/app.py', 'styles/main.css'. "
            "Klasörler otomatik oluşturulur."
        )
    )
    content: str = Field(description="Dosyaya yazılacak tam içerik.")
    project_name: str = Field(
        default="project",
        description="Proje adı — output/<project_name>/ altına kaydedilir.",
    )


class FileWriterTool(BaseTool):
    name: str = "file_writer"
    description: str = (
        "Üretilen kodu veya içeriği gerçek bir dosyaya yazar. "
        "HTML, CSS, JS, Python, Go, Rust, YAML, JSON vb. her türlü dosya desteklenir. "
        "Dosyalar output/<proje_adı>/ klasörüne kaydedilir ve daha sonra "
        "zip_and_send aracıyla paketlenip Telegram'a gönderilebilir."
    )
    args_schema: type[BaseModel] = FileWriterInput

    def _run(self, filepath: str, content: str, project_name: str = "project") -> str:
        try:
            # Güvenlik: path traversal engelle
            safe_path = Path(filepath).as_posix().lstrip("/").lstrip("../")
            full_path  = OUTPUT_DIR / project_name / safe_path
            full_path.parent.mkdir(parents=True, exist_ok=True)

            full_path.write_text(content, encoding="utf-8", errors="replace")
            size_kb = round(full_path.stat().st_size / 1024, 2)

            logger.info("Dosya yazıldı: %s (%s KB)", full_path, size_kb)
            return (
                f"✅ Dosya kaydedildi: `{safe_path}`\n"
                f"📁 Tam yol: `{full_path}`\n"
                f"📦 Boyut: {size_kb} KB"
            )
        except Exception as exc:
            logger.error("Dosya yazma hatası: %s", exc)
            return f"❌ Dosya yazılamadı: {exc}"


def get_project_output_dir(project_name: str = "project") -> Path:
    """Proje çıktı klasörünü döner (yoksa oluşturur)."""
    d = OUTPUT_DIR / project_name
    d.mkdir(parents=True, exist_ok=True)
    return d


def list_output_files(project_name: str = "project") -> list[Path]:
    """Projenin ürettiği tüm dosyaları listeler."""
    d = OUTPUT_DIR / project_name
    if not d.exists():
        return []
    return sorted(d.rglob("*") if d.exists() else [])
