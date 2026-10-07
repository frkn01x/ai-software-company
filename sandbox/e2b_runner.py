"""
E2B Sandbox Runner — Zorunlu Test Sistemi
Kodları E2B Hobby katmanında güvenli şekilde çalıştırır.

YENİLİKLER:
  - run_and_verify()  : kodu çalıştır, başarısız olursa hata raporuyla döner
  - run_file_from_disk: output/ klasöründeki dosyayı doğrudan E2B'ye yükler ve çalıştırır
  - HTML/CSS/JS testi için node / browser-like ortam hazırlama
  - Otomatik paket kurulumu (import hataları yakalanınca)
"""

import logging
import re
from pathlib import Path
from typing import Optional
from config import cfg

logger = logging.getLogger(__name__)

# E2B Hobby: max 60 sn session, sonra yeni sandbox açılır
SANDBOX_TIMEOUT = 60


class E2BRunner:
    """E2B cloud sandbox'ta kod çalıştırır."""

    def __init__(self):
        self._api_key = cfg.e2b_api_key
        self._sb = None

    # ------------------------------------------------------------------ #
    #  Sandbox yönetimi                                                     #
    # ------------------------------------------------------------------ #
    def _get_sandbox(self):
        try:
            from e2b_code_interpreter import Sandbox
            if self._sb is None:
                self._sb = Sandbox(api_key=self._api_key, timeout=SANDBOX_TIMEOUT)
                logger.info("E2B Sandbox oluşturuldu: %s", self._sb.sandbox_id)
            return self._sb
        except Exception as exc:
            logger.error("E2B Sandbox başlatılamadı: %s", exc)
            raise

    def _reset_sandbox(self):
        """Mevcut sandbox'u kapat, bir sonraki çağrıda yeni açılsın."""
        if self._sb:
            try:
                self._sb.close()
            except Exception:
                pass
            self._sb = None

    # ------------------------------------------------------------------ #
    #  Temel çalıştırıcı                                                    #
    # ------------------------------------------------------------------ #
    def _execute(self, code: str, language: str, filename: str) -> dict:
        result = {
            "success":  False,
            "stdout":   "",
            "stderr":   "",
            "exit_code": -1,
            "language": language,
            "filename": filename,
        }
        try:
            sb = self._get_sandbox()
            execution = sb.run_code(code)
            stdout = "\n".join(str(r) for r in execution.logs.stdout) if execution.logs.stdout else ""
            stderr = "\n".join(str(r) for r in execution.logs.stderr) if execution.logs.stderr else ""
            result.update({
                "success":   execution.error is None,
                "stdout":    stdout,
                "stderr":    stderr if not execution.error else str(execution.error),
                "exit_code": 0 if execution.error is None else 1,
            })
            logger.info("E2B sonucu: success=%s lang=%s", result["success"], language)
        except Exception as exc:
            result["stderr"] = str(exc)
            logger.error("E2B execution error: %s", exc)
            self._reset_sandbox()   # Bozuk sandbox'u temizle
        return result

    # ------------------------------------------------------------------ #
    #  Dil bazlı kolay çağrıcılar                                           #
    # ------------------------------------------------------------------ #
    def run_python(self, code: str) -> dict:
        return self._execute(code, "python", "script.py")

    def run_javascript(self, code: str) -> dict:
        return self._execute(code, "javascript", "script.js")

    def run_bash(self, command: str) -> dict:
        return self._execute(command, "bash", "cmd.sh")

    def run_code(self, code: str, language: str, filename: Optional[str] = None) -> dict:
        lang_map = {
            "python": "python", "py": "python",
            "javascript": "javascript", "js": "javascript",
            "typescript": "javascript", "ts": "javascript",
            "bash": "bash", "sh": "bash",
        }
        resolved = lang_map.get(language.lower())
        if not resolved:
            return {
                "success": False, "stdout": "", "exit_code": -1,
                "stderr": f"Desteklenmeyen dil: {language}. Desteklenenler: {', '.join(lang_map)}",
            }
        return self._execute(code, resolved, filename or f"script.{language}")

    # ------------------------------------------------------------------ #
    #  ZORUNLu TEST — başarısız olursa ayrıntılı hata raporu döner         #
    # ------------------------------------------------------------------ #
    def run_and_verify(
        self,
        code: str,
        language: str = "python",
        expected_output: Optional[str] = None,
        auto_install: bool = True,
    ) -> dict:
        """
        Kodu çalıştır ve doğrula.

        - Başarılıysa   → {"passed": True,  ...}
        - Başarısızsa   → {"passed": False, "fix_hint": "...", ...}
        - auto_install  → ModuleNotFoundError yakalanırsa pip install dene, tekrar çalıştır
        """
        result = self.run_code(code, language)

        # Eksik modül otomatik kurulum
        if auto_install and not result["success"]:
            missing = _extract_missing_module(result["stderr"])
            if missing:
                install = self.install_packages([missing])
                logger.info("Auto-install %s: %s", missing, install.get("success"))
                if install.get("success"):
                    result = self.run_code(code, language)

        # Beklenen çıktı kontrolü
        if expected_output and result["success"]:
            if expected_output.strip() not in result["stdout"]:
                result["success"] = False
                result["stderr"] = (
                    f"Çıktı eşleşmedi.\n"
                    f"Beklenen: {expected_output!r}\n"
                    f"Gerçek: {result['stdout'][:300]!r}"
                )

        result["passed"] = result["success"]
        if not result["passed"]:
            result["fix_hint"] = _generate_fix_hint(result["stderr"], language)

        return result

    # ------------------------------------------------------------------ #
    #  Dosyayı diskten oku, E2B'ye yükle, çalıştır                        #
    # ------------------------------------------------------------------ #
    def run_file_from_disk(self, file_path: Path) -> dict:
        """
        output/ klasöründeki bir dosyayı E2B sandbox'a yükler ve çalıştırır.
        HTML/CSS/JS için basit syntax kontrol yapar.
        """
        if not file_path.exists():
            return {"success": False, "stderr": f"Dosya bulunamadı: {file_path}"}

        suffix = file_path.suffix.lower()
        content = file_path.read_text(encoding="utf-8", errors="ignore")

        lang_map = {
            ".py":   "python",
            ".js":   "javascript",
            ".ts":   "javascript",
            ".sh":   "bash",
            ".html": "html_check",   # Özel işlem
            ".css":  "css_check",    # Özel işlem
        }
        lang = lang_map.get(suffix)

        if lang == "html_check":
            return _validate_html(content, str(file_path))
        if lang == "css_check":
            return _validate_css(content, str(file_path))
        if lang:
            return self.run_and_verify(content, lang)

        # Bilinmeyen uzantı — sadece var olduğunu doğrula
        return {
            "success": True,
            "passed":  True,
            "stdout":  f"Dosya mevcut: {file_path.name} ({len(content)} karakter)",
            "stderr":  "",
            "exit_code": 0,
        }

    # ------------------------------------------------------------------ #
    #  Tüm proje dosyalarını test et                                       #
    # ------------------------------------------------------------------ #
    def test_project_files(self, project_dir: Path) -> dict:
        """
        output/<proje>/ altındaki tüm test edilebilir dosyaları çalıştırır.
        Özet rapor döner.
        """
        testable_ext = {".py", ".js", ".ts", ".sh", ".html", ".css"}
        results = {}
        passed = 0
        failed = 0

        for f in sorted(project_dir.rglob("*")):
            if f.is_file() and f.suffix.lower() in testable_ext:
                rel = str(f.relative_to(project_dir))
                r = self.run_file_from_disk(f)
                results[rel] = r
                if r.get("passed", r.get("success", False)):
                    passed += 1
                else:
                    failed += 1

        return {
            "total":   passed + failed,
            "passed":  passed,
            "failed":  failed,
            "results": results,
            "all_passed": failed == 0,
        }

    # ------------------------------------------------------------------ #
    #  Paket kurulum yardımcısı                                             #
    # ------------------------------------------------------------------ #
    def install_packages(self, packages: list, manager: str = "pip") -> dict:
        if manager == "pip":
            cmd = f"pip install {' '.join(packages)} -q"
        elif manager == "npm":
            cmd = f"npm install {' '.join(packages)} --silent"
        else:
            cmd = f"{manager} install {' '.join(packages)}"
        return self.run_bash(cmd)

    def close(self):
        if self._sb:
            try:
                self._sb.close()
                logger.info("E2B Sandbox kapatıldı.")
            except Exception:
                pass
            self._sb = None


# ─────────────────────────────────────────────
#  Yardımcı fonksiyonlar
# ─────────────────────────────────────────────

def _extract_missing_module(stderr: str) -> Optional[str]:
    """ModuleNotFoundError: No module named 'X' → 'X' döner."""
    m = re.search(r"No module named ['\"]([^'\"]+)['\"]", stderr)
    return m.group(1) if m else None


def _generate_fix_hint(stderr: str, language: str) -> str:
    """Hata mesajına göre düzeltme ipucu üretir."""
    err = stderr.lower()
    if "syntaxerror" in err:
        return "Sözdizimi hatası var. Parantez/tırnak işareti dengesini kontrol et."
    if "nameerror" in err or "is not defined" in err:
        return "Tanımsız değişken. İmport veya tanım eksik olabilir."
    if "typeerror" in err:
        return "Tip hatası. Fonksiyon argümanlarını veya veri tiplerini kontrol et."
    if "importerror" in err or "modulenotfounderror" in err:
        return "Eksik paket. requirements.txt'e eklenip pip install yapılmalı."
    if "indentationerror" in err:
        return "Girinti (indentation) hatası. 4 boşluk kullan, tab karıştırma."
    if language in ("javascript", "typescript"):
        if "referenceerror" in err:
            return "Tanımsız değişken. const/let/var ile tanımlandığından emin ol."
        if "typeerror" in err:
            return "undefined/null değere erişim olabilir. Optional chaining (?.) kullan."
    return f"Hata detayı: {stderr[:200]}"


def _validate_html(content: str, filename: str) -> dict:
    """HTML dosyasını temel kural kontrolünden geçirir (E2B'ye gönderilmez)."""
    errors = []

    # Temel HTML yapısı
    if "<!DOCTYPE html>" not in content and "<!doctype html>" not in content.lower():
        errors.append("<!DOCTYPE html> eksik")
    if "<html" not in content.lower():
        errors.append("<html> etiketi eksik")
    if "<head>" not in content.lower() and "<head " not in content.lower():
        errors.append("<head> etiketi eksik")
    if "<body>" not in content.lower() and "<body " not in content.lower():
        errors.append("<body> etiketi eksik")

    # Etiket dengesi kontrolü (basit)
    for tag in ["div", "section", "article", "nav", "header", "footer", "main"]:
        opens  = content.lower().count(f"<{tag}")
        closes = content.lower().count(f"</{tag}>")
        if opens != closes:
            errors.append(f"<{tag}> açma/kapama sayısı eşleşmiyor ({opens} açık, {closes} kapalı)")

    passed = len(errors) == 0
    return {
        "success":   passed,
        "passed":    passed,
        "stdout":    f"HTML doğrulandı: {filename}" if passed else "",
        "stderr":    "\n".join(errors) if errors else "",
        "exit_code": 0 if passed else 1,
        "fix_hint":  "Eksik HTML yapı etiketlerini ekle." if errors else "",
    }


def _validate_css(content: str, filename: str) -> dict:
    """CSS dosyasını temel kural kontrolünden geçirir."""
    errors = []

    # Açık kalan blok kontrolü
    opens  = content.count("{")
    closes = content.count("}")
    if opens != closes:
        errors.append(f"CSS blok dengesi bozuk: {opens} açık {{}} vs {closes} kapalı {{}}")

    # Boş dosya kontrolü
    stripped = content.strip()
    if not stripped:
        errors.append("CSS dosyası boş")

    passed = len(errors) == 0
    return {
        "success":   passed,
        "passed":    passed,
        "stdout":    f"CSS doğrulandı: {filename}" if passed else "",
        "stderr":    "\n".join(errors) if errors else "",
        "exit_code": 0 if passed else 1,
        "fix_hint":  "CSS blok açma/kapama parantezlerini dengele." if errors else "",
    }


# ─────────────────────────────────────────────
#  Modül düzeyinde singleton
# ─────────────────────────────────────────────
_runner: Optional[E2BRunner] = None


def get_runner() -> E2BRunner:
    global _runner
    if _runner is None:
        _runner = E2BRunner()
    return _runner


def run_code_in_sandbox(code: str, language: str = "python") -> dict:
    """Convenience wrapper — tools tarafından doğrudan çağrılır."""
    return get_runner().run_code(code, language)


def run_and_verify(code: str, language: str = "python", expected_output: Optional[str] = None) -> dict:
    """Zorunlu test wrapper — başarısız olursa fix_hint ile döner."""
    return get_runner().run_and_verify(code, language, expected_output)


def test_project(project_dir: Path) -> dict:
    """Tüm proje dosyalarını test eder."""
    return get_runner().test_project_files(project_dir)
