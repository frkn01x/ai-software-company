"""
Web Search Tool — Research Agent için çok katmanlı arama sistemi

Öncelik sırası:
  1. SerperDev API (Google arama — SERPER_API_KEY varsa)
  2. DuckDuckGo (ücretsiz, key gerektirmez — fallback)
  3. GitHub API (repo arama — GITHUB_TOKEN varsa daha yüksek limit)

Her araç CrewAI BaseTool olarak sarılmış durumda.
"""

import json
import logging
import requests
from typing import Optional
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from config import cfg

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
#  1. Genel Web Araması (Serper → DuckDuckGo)
# ─────────────────────────────────────────────

class WebSearchInput(BaseModel):
    query: str = Field(description="Arama sorgusu")
    num_results: int = Field(default=5, description="Kaç sonuç dönsün (max 10)")


class WebSearchTool(BaseTool):
    name: str = "web_search"
    description: str = (
        "Web'de genel arama yapar. Google (Serper API) veya DuckDuckGo kullanır. "
        "Teknoloji karşılaştırmaları, best practice'ler, benchmark sonuçları, "
        "güvenlik açıkları (CVE), resmi dokümantasyon ve blog yazıları için kullan."
    )
    args_schema: type[BaseModel] = WebSearchInput

    def _run(self, query: str, num_results: int = 5) -> str:
        # Serper API varsa onu kullan
        serper_key = cfg.get("SERPER_API_KEY")
        if serper_key:
            result = self._serper_search(query, num_results, serper_key)
            if result:
                return result

        # Fallback: DuckDuckGo
        return self._duckduckgo_search(query, num_results)

    def _serper_search(self, query: str, num: int, api_key: str) -> Optional[str]:
        try:
            resp = requests.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
                json={"q": query, "num": num},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            results = []
            for item in data.get("organic", [])[:num]:
                results.append(
                    f"📌 **{item.get('title', '')}**\n"
                    f"   🔗 {item.get('link', '')}\n"
                    f"   📄 {item.get('snippet', '')}\n"
                )
            if not results:
                return None
            return f"🔍 Serper Arama: '{query}'\n\n" + "\n".join(results)
        except Exception as exc:
            logger.warning("Serper arama hatası: %s", exc)
            return None

    def _duckduckgo_search(self, query: str, num: int) -> str:
        try:
            from duckduckgo_search import DDGS
            results = []
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=num):
                    results.append(
                        f"📌 **{r.get('title', '')}**\n"
                        f"   🔗 {r.get('href', '')}\n"
                        f"   📄 {r.get('body', '')[:200]}\n"
                    )
            if results:
                return f"🦆 DuckDuckGo: '{query}'\n\n" + "\n".join(results)
            return f"❌ '{query}' için sonuç bulunamadı."
        except ImportError:
            return (
                f"❌ Web search çalışmıyor. "
                f"'duckduckgo-search' paketi eksik veya SERPER_API_KEY ayarlanmamış.\n"
                f"Kur: pip install duckduckgo-search"
            )
        except Exception as exc:
            logger.warning("DuckDuckGo arama hatası (sessiz geçildi): %s", exc)
            # Hata varsa sessizce boş sonuç dön — ajan kendi bilgisiyle devam eder
            return f"ℹ️ Web araması şu an kullanılamıyor. Bilgi birikimime dayanarak devam ediyorum."


# ─────────────────────────────────────────────
#  2. GitHub Repo Arama
# ─────────────────────────────────────────────

class GitHubSearchInput(BaseModel):
    query: str = Field(description="GitHub arama sorgusu (örn: 'fastapi ecommerce stars:>100')")
    language: str = Field(default="", description="Programlama dili filtresi (python, javascript vb.)")
    sort: str = Field(default="stars", description="Sıralama: stars | forks | updated")
    num_results: int = Field(default=5, description="Kaç repo dönsün (max 10)")


class GitHubSearchTool(BaseTool):
    name: str = "github_search"
    description: str = (
        "GitHub'da benzer açık kaynak projeleri arar. "
        "Mimari fikirler, teknoloji seçimi ve best practice için "
        "benzer projelerin yapısını inceler. "
        "Popüler repo'ların yıldız sayısı, teknoloji stack'i ve "
        "son aktivitesini gösterir."
    )
    args_schema: type[BaseModel] = GitHubSearchInput

    def _run(
        self,
        query: str,
        language: str = "",
        sort: str = "stars",
        num_results: int = 5,
    ) -> str:
        search_q = query
        if language:
            search_q += f" language:{language}"

        github_token = cfg.get("GITHUB_TOKEN")
        headers = {"Accept": "application/vnd.github+json"}
        if github_token:
            headers["Authorization"] = f"Bearer {github_token}"

        try:
            resp = requests.get(
                "https://api.github.com/search/repositories",
                headers=headers,
                params={"q": search_q, "sort": sort, "per_page": num_results},
                timeout=15,
            )
            resp.raise_for_status()
            items = resp.json().get("items", [])

            if not items:
                return f"❌ GitHub'da '{query}' için repo bulunamadı."

            results = [f"🐙 GitHub Arama: '{query}'\n"]
            for repo in items:
                topics = ", ".join(repo.get("topics", [])[:5]) or "—"
                results.append(
                    f"📦 **{repo['full_name']}** "
                    f"⭐{repo['stargazers_count']:,} 🍴{repo['forks_count']:,}\n"
                    f"   🔗 {repo['html_url']}\n"
                    f"   📄 {repo.get('description', 'Açıklama yok')[:150]}\n"
                    f"   🏷️  Topics: {topics}\n"
                    f"   🔧 Dil: {repo.get('language', '?')} | "
                    f"Son güncelleme: {repo.get('updated_at', '?')[:10]}\n"
                )

            return "\n".join(results)

        except requests.HTTPError as exc:
            if exc.response.status_code == 403:
                return (
                    "⚠️ GitHub API rate limit aşıldı. "
                    "GITHUB_TOKEN ekleyerek limiti artır:\n"
                    "`/setkey github ghp_...`"
                )
            return f"❌ GitHub API hatası: {exc}"
        except Exception as exc:
            logger.error("GitHub arama hatası: %s", exc)
            return f"❌ GitHub arama hatası: {exc}"


# ─────────────────────────────────────────────
#  3. CVE / Güvenlik Açığı Araması
# ─────────────────────────────────────────────

class CVESearchInput(BaseModel):
    keyword: str = Field(description="Aranacak teknoloji/kütüphane adı (örn: 'fastapi', 'log4j')")
    severity: str = Field(
        default="",
        description="Önem filtresi: CRITICAL | HIGH | MEDIUM | LOW (boş = hepsi)",
    )
    num_results: int = Field(default=5, description="Kaç CVE gösterilsin")


class CVESearchTool(BaseTool):
    name: str = "cve_search"
    description: str = (
        "NVD (National Vulnerability Database) üzerinde belirtilen teknoloji için "
        "bilinen güvenlik açıklarını (CVE) arar. "
        "Seçilen kütüphane/framework'ün kritik açıklarını kontrol etmek için kullan."
    )
    args_schema: type[BaseModel] = CVESearchInput

    def _run(self, keyword: str, severity: str = "", num_results: int = 5) -> str:
        try:
            params: dict = {"keywordSearch": keyword, "resultsPerPage": num_results}
            if severity:
                params["cvssV3Severity"] = severity.upper()

            resp = requests.get(
                "https://services.nvd.nist.gov/rest/json/cves/2.0",
                params=params,
                timeout=20,
            )
            resp.raise_for_status()
            data = resp.json()
            vulns = data.get("vulnerabilities", [])

            if not vulns:
                return f"✅ '{keyword}' için bilinen CVE bulunamadı."

            lines = [f"🔐 CVE Arama: '{keyword}' — {len(vulns)} sonuç\n"]
            for v in vulns:
                cve  = v.get("cve", {})
                cve_id = cve.get("id", "?")
                desc = next(
                    (d["value"] for d in cve.get("descriptions", []) if d["lang"] == "en"),
                    "Açıklama yok",
                )
                metrics = cve.get("metrics", {})
                score = "?"
                sev   = "?"
                for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
                    if key in metrics and metrics[key]:
                        m = metrics[key][0].get("cvssData", {})
                        score = m.get("baseScore", "?")
                        sev   = m.get("baseSeverity", "?")
                        break

                sev_emoji = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}.get(str(sev), "⚪")
                lines.append(
                    f"{sev_emoji} **{cve_id}** — Score: {score} ({sev})\n"
                    f"   📄 {desc[:200]}\n"
                    f"   🔗 https://nvd.nist.gov/vuln/detail/{cve_id}\n"
                )

            return "\n".join(lines)

        except Exception as exc:
            logger.error("CVE arama hatası: %s", exc)
            return f"❌ CVE arama hatası: {exc}"


# ─────────────────────────────────────────────
#  4. Tech Radar / Trend Araması
# ─────────────────────────────────────────────

class TechRadarInput(BaseModel):
    technology: str = Field(description="Araştırılacak teknoloji (örn: 'htmx', 'bun', 'deno')")


class TechRadarTool(BaseTool):
    name: str = "tech_radar_search"
    description: str = (
        "Bir teknolojinin güncel trendi, benimseme durumu ve "
        "topluluk yorumlarını web'de arar. "
        "ThoughtWorks Tech Radar, State of JS/Python/DB gibi kaynakları tarar. "
        "Yeni bir kütüphane/framework seçmeden önce kullan."
    )
    args_schema: type[BaseModel] = TechRadarInput

    def _run(self, technology: str) -> str:
        # Web search ile ThoughtWorks radar + npm/pypi trends araması
        queries = [
            f"{technology} ThoughtWorks technology radar",
            f"{technology} github stars trend 2024 2025",
            f"should I use {technology} production pros cons",
        ]

        web_tool = WebSearchTool()
        results = [f"📡 Tech Radar: '{technology}'\n"]
        for q in queries:
            r = web_tool._run(q, num_results=2)
            results.append(r)
            results.append("─" * 40)

        return "\n".join(results)
