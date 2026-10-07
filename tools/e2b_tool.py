"""
CrewAI Tool: E2B Code Execution — Zorunlu Test Sistemi
Ajanların E2B sandbox'ta kod çalıştırmasını ve dosyaları test etmesini sağlar.
"""

from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Optional
from sandbox.e2b_runner import run_code_in_sandbox, run_and_verify, test_project
from pathlib import Path


# ── 1. Basit kod çalıştırma ───────────────────────────────────────────────────
class E2BInput(BaseModel):
    code: str = Field(description="Çalıştırılacak kaynak kod")
    language: str = Field(
        default="python",
        description="Programlama dili: python, javascript, bash",
    )


class E2BCodeExecutionTool(BaseTool):
    name: str = "e2b_code_executor"
    description: str = (
        "E2B cloud sandbox'ta güvenli şekilde kod çalıştırır. "
        "Python, JavaScript ve Bash desteklenir. "
        "Çalıştırma sonucunu stdout, stderr ve başarı durumu ile döner."
    )
    args_schema: type[BaseModel] = E2BInput

    def _run(self, code: str, language: str = "python") -> str:
        result = run_code_in_sandbox(code, language)
        lines = [f"{'✅' if result['success'] else '❌'} Başarılı: {result['success']}"]
        if result["stdout"]:
            lines.append(f"📤 STDOUT:\n{result['stdout'][:1500]}")
        if result["stderr"]:
            lines.append(f"⚠️ STDERR:\n{result['stderr'][:800]}")
        lines.append(f"🔢 Exit Code: {result['exit_code']}")
        return "\n".join(lines)


# ── 2. Zorunlu test — başarısız olursa fix_hint döner ────────────────────────
class E2BVerifyInput(BaseModel):
    code: str = Field(description="Test edilecek kaynak kod")
    language: str = Field(
        default="python",
        description="Programlama dili: python, javascript, bash",
    )
    expected_output: Optional[str] = Field(
        default=None,
        description="Çıktıda bulunması beklenen metin (opsiyonel).",
    )


class E2BMandatoryTestTool(BaseTool):
    name: str = "e2b_mandatory_test"
    description: str = (
        "Kodu E2B sandbox'ta çalıştırır ve ZORUNLU test yapar. "
        "Başarısız olursa düzeltme ipucu (fix_hint) ile döner; "
        "ajan kodu düzeltip tekrar çağırmalıdır. "
        "Eksik Python paketi varsa otomatik yükler ve tekrar dener. "
        "HTML/CSS dosyaları için sözdizimi doğrulama yapar."
    )
    args_schema: type[BaseModel] = E2BVerifyInput

    def _run(
        self,
        code: str,
        language: str = "python",
        expected_output: Optional[str] = None,
    ) -> str:
        result = run_and_verify(code, language, expected_output)
        status = "✅ TEST GEÇTİ" if result["passed"] else "❌ TEST BAŞARISIZ"
        lines = [status]
        if result["stdout"]:
            lines.append(f"📤 STDOUT:\n{result['stdout'][:1500]}")
        if result["stderr"]:
            lines.append(f"⚠️ HATA:\n{result['stderr'][:800]}")
        if not result["passed"] and result.get("fix_hint"):
            lines.append(f"💡 DÜZELTME İPUCU:\n{result['fix_hint']}")
            lines.append("⚠️ Kodu düzelt ve e2b_mandatory_test'i tekrar çağır!")
        return "\n".join(lines)


# ── 3. Tüm proje dosyalarını test et ─────────────────────────────────────────
class E2BProjectTestInput(BaseModel):
    project_name: str = Field(
        default="project",
        description="Test edilecek proje adı (output/<project_name>/ klasörü).",
    )


class E2BProjectTestTool(BaseTool):
    name: str = "e2b_project_tester"
    description: str = (
        "output/<proje>/ klasöründeki TÜM dosyaları (Python, JS, HTML, CSS) "
        "E2B sandbox'ta test eder. "
        "Zip göndermeden önce son kontrol olarak çağır."
    )
    args_schema: type[BaseModel] = E2BProjectTestInput

    def _run(self, project_name: str = "project") -> str:
        from tools.file_writer_tool import OUTPUT_DIR
        project_dir = OUTPUT_DIR / project_name

        if not project_dir.exists():
            return (
                f"❌ Proje klasörü bulunamadı: `{project_dir}`\n"
                "Önce file_writer ile dosyaları oluştur."
            )

        summary = test_project(project_dir)
        total  = summary["total"]
        passed = summary["passed"]
        failed = summary["failed"]

        icon = "✅" if summary["all_passed"] else "❌"
        lines = [
            f"{icon} PROJE TEST SONUCU",
            f"📊 Toplam: {total} | ✅ Geçti: {passed} | ❌ Başarısız: {failed}",
            "",
        ]

        for filepath, res in summary["results"].items():
            status = "✅" if res.get("passed", res.get("success")) else "❌"
            lines.append(f"  {status} {filepath}")
            if not res.get("passed", res.get("success")):
                hint = res.get("fix_hint") or res.get("stderr", "")[:200]
                if hint:
                    lines.append(f"       💡 {hint}")

        if summary["all_passed"]:
            lines.append("\n🚀 Tüm testler geçti! zip_and_send ile gönderebilirsin.")
        else:
            lines.append(f"\n⚠️ {failed} dosya başarısız. Önce düzelt, sonra zip gönder.")

        return "\n".join(lines)
