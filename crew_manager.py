"""
Crew Manager — Hiyerarşik Multi-Agent Orchestration
CrewAI Process.HIERARCHICAL ile çalışır.

AKIŞ:
  PM → UX → Frontend → Backend → Security → QA → Analyst → DevOps → EM (ZIP)

RESUME MEKANİZMASI:
  - Her görev bitişinde task_callback state dosyasına tamamlandı yazar
  - /resume çağrıldığında tamamlanan görevler atlanır
  - Sadece kalan görevler çalıştırılır → API kota kaybı olmaz
"""

import re
import logging

from crewai import Crew, Task, Process

from agents import (
    create_product_manager,
    create_engineering_manager,
    create_qa_tester,
    create_ux_designer,
    create_security_expert,
    create_frontend_dev,
    create_backend_python,
    create_backend_nodejs,
    create_backend_go,
    create_backend_rust,
    create_backend_dotnet,
    create_db_sql_expert,
    create_db_nosql_expert,
    create_code_analyst,
    create_devops,
    create_solution_architect,
    create_business_analyst,
)
from tools import (
    E2BCodeExecutionTool,
    E2BMandatoryTestTool,
    E2BProjectTestTool,
    TelegramReportTool,
    FileWriterTool,
    ZipAndSendTool,
    WebSearchTool,
    GitHubSearchTool,
    CVESearchTool,
    TechRadarTool,
)
from state import (
    load_state, save_state, record_error,
    get_completed_tasks, bump_iteration, get_resume_summary,
)
from llm_factory import build_llm
from telegram_bot.notifier import send_message
from reporter import (
    task_callback,
    step_callback,
    report_project_start,
    report_project_complete,
)

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
#  Tool instances (shared across agents)
# ─────────────────────────────────────────────
e2b_run_tool     = E2BCodeExecutionTool()
e2b_test_tool    = E2BMandatoryTestTool()
e2b_project_tool = E2BProjectTestTool()
tg_tool          = TelegramReportTool()
file_tool        = FileWriterTool()
zip_tool         = ZipAndSendTool()

# Web search araçları
web_search_tool  = WebSearchTool()
github_tool      = GitHubSearchTool()
cve_tool         = CVESearchTool()
tech_radar_tool  = TechRadarTool()

# Araç grupları
ALL_TOOLS        = [e2b_run_tool, e2b_test_tool, e2b_project_tool, tg_tool, file_tool, zip_tool,
                    web_search_tool, github_tool, cve_tool, tech_radar_tool]
REPORT_TOOLS     = [tg_tool]
CODE_TOOLS       = [e2b_run_tool, e2b_test_tool, file_tool, tg_tool]
RESEARCH_TOOLS   = [web_search_tool, github_tool, cve_tool, tech_radar_tool, file_tool, tg_tool]
ARCH_TOOLS       = [web_search_tool, github_tool, file_tool, tg_tool]
BA_TOOLS         = [web_search_tool, cve_tool, file_tool, tg_tool]


# ─────────────────────────────────────────────
#  Task builders
# ─────────────────────────────────────────────

# Görev ID'leri — state'e kaydedilen ve resume'da kontrol edilen sabit isimler
TASK_IDS = [
    "task_pm",            # 1. Product Manager — PRD
    "task_architect",     # 2. Solution Architect — C4, ADR, NFR
    "task_ux",            # 3. UX Designer — wireframe, design spec
    "task_frontend",      # 4. Frontend — HTML/CSS/JS
    "task_backend_py",    # 5. Backend Python — FastAPI
    "task_db_sql",        # 6. SQL DB — şema, migration, index
    "task_db_nosql",      # 7. NoSQL — Redis, MongoDB
    "task_backend_net",   # 8. .NET — C# servis (opsiyonel)
    "task_security",      # 9. Security — OWASP tarama
    "task_qa",            # 10. QA — E2B testleri
    "task_ba",            # 11. Business Analyst — logic + traceability
    "task_analysis",      # 12. Code Analyst — kalite raporu
    "task_devops",        # 13. DevOps — Docker, CI/CD
    "task_em_final",      # 14. EM — final rapor + ZIP
]


def _make_skip_description(task_id: str, original_desc: str) -> str:
    """
    Görev zaten tamamlandıysa kısa bir skip description döner.
    Ajan bu görevi alırsa minimum token harcayarak tamamlar.
    """
    return (
        f"[GÖREV ATLANDI — daha önce tamamlandı]\n\n"
        f"Bu görev (ID: {task_id}) önceki çalıştırmada başarıyla tamamlandı.\n"
        f"Sadece şunu yap: telegram_reporter ile şu mesajı gönder:\n"
        f"'✅ [{task_id}] görevi daha önce tamamlandı, atlanıyor.'\n"
        f"Başka hiçbir şey yapma."
    )


def build_tasks(
    project_brief: str,
    agents: dict,
    project_name: str,
    completed_task_ids: list[str] | None = None,
) -> list[Task]:
    """
    Görev listesi oluşturur.
    completed_task_ids içindeki görevler minimal skip görevi olarak eklenir
    (context zinciri bozulmasın diye tamamen kaldırılmaz, sadece basitleştirilir).
    """
    done = set(completed_task_ids or [])

    def is_done(task_id: str) -> bool:
        return task_id in done

    def desc(task_id: str, full_desc: str) -> str:
        return _make_skip_description(task_id, full_desc) if is_done(task_id) else full_desc

    def tools_for(task_id: str, normal_tools: list) -> list:
        return [tg_tool] if is_done(task_id) else normal_tools

    # ── 1. Product Manager: PRD ───────────────────────────────────────────
    full_pm = (
        f"Proje: {project_brief}\n\n"
        f"PRD hazırla (Türkçe):\n"
        f"1. Executive Summary (2-3 cümle)\n"
        f"2. 5 Kullanıcı Hikayesi + kabul kriterleri\n"
        f"3. Teknik Gereksinimler listesi\n"
        f"4. 2 Haftalık Sprint Planı\n"
        f"5. Risk Analizi (5 risk, RAG)\n\n"
        f"file_writer ile kaydet: filepath='docs/PRD.md', project_name='{project_name}'\n"
        f"telegram_reporter ile Telegram'a gönder."
    )
    task_pm = Task(
        name="task_pm",
        description=desc("task_pm", full_pm),
        expected_output="PRD.md kaydedildi. Telegram raporu gönderildi.",
        agent=agents["pm"],
        tools=tools_for("task_pm", [file_tool, tg_tool]),
    )

    # ── 2. Solution Architect ─────────────────────────────────────────────
    full_architect = (
        f"PRD'ye göre sistem mimarisi tasarla.\n"
        f"Mermaid C4 diyagramı, ADR (3 karar), NFR ve teknoloji stack belgele.\n"
        f"file_writer: filepath='docs/ARCHITECTURE.md', project_name='{project_name}'\n"
        f"Telegram'a özet gönder."
    )
    task_architect = Task(
        name="task_architect",
        description=desc("task_architect", full_architect),
        expected_output=(
            "ARCHITECTURE.md, NFR.md, TECH_STACK.md kaydedildi. Telegram raporu."
        ),
        agent=agents["architect"],
        tools=tools_for("task_architect", ARCH_TOOLS),
        context=[task_pm],
    )

    # ── 2. UX Designer ────────────────────────────────────────────────────
    full_ux = (
        "PRD'ye göre UX/UI tasarım spesifikasyonu hazırla ve kaydet.\n\n"
        "İçerik: wireframe açıklamaları, renk paleti (hex), tipografi, "
        "bileşen listesi, responsive breakpoints, WCAG 2.1 AA kontrol listesi.\n\n"
        f"ZORUNLU: file_writer → filepath='docs/UX_SPEC.md', project_name='{project_name}'\n"
        "Telegram'a bildir."
    )
    task_ux = Task(
        name="task_ux",
        description=desc("task_ux", full_ux),
        expected_output="UX_SPEC.md kaydedildi. Telegram raporu gönderildi.",
        agent=agents["ux"],
        tools=tools_for("task_ux", [file_tool, tg_tool]),
        context=[task_pm, task_architect],
    )

    # ── 3. Frontend ───────────────────────────────────────────────────────
    full_fe = (
        f"UX spec'e göre web sitesi oluştur.\n"
        f"index.html, styles/main.css, js/app.js yaz.\n"
        f"Her dosyayı file_writer ile kaydet (project_name='{project_name}').\n"
        f"e2b_mandatory_test ile syntax doğrula. Telegram'a rapor gönder."
    )
    task_frontend = Task(
        name="task_frontend",
        description=desc("task_frontend", full_fe),
        expected_output="index.html, main.css, app.js kaydedildi. E2B testleri geçti.",
        agent=agents["frontend"],
        tools=tools_for("task_frontend", CODE_TOOLS),
        context=[task_ux, task_pm, task_architect],
    )

    # ── Backend Python ─────────────────────────────────────────────────────

    # ── 4. Backend Python ─────────────────────────────────────────────────
    full_be = (
        f"PRD'ye göre Python/FastAPI backend yaz.\n"
        f"backend/main.py, backend/models.py, backend/requirements.txt oluştur.\n"
        f"Her dosyayı file_writer ile kaydet (project_name='{project_name}').\n"
        f"e2b_mandatory_test ile test et. Telegram'a rapor gönder."
    )
    task_backend_py = Task(
        name="task_backend_py",
        description=desc("task_backend_py", full_be),
        expected_output="backend/main.py, models.py, requirements.txt kaydedildi. E2B testleri geçti.",
        agent=agents["backend_py"],
        tools=tools_for("task_backend_py", CODE_TOOLS),
        context=[task_pm, task_architect, task_frontend],
    )

    # ── 5. SQL & İlişkisel Veritabanı ────────────────────────────────────
    full_db_sql = (
        f"SQLite şeması tasarla ve kaydet (project_name='{project_name}').\n"
        f"1. file_writer: filepath='db/schema.sql' — CREATE TABLE tasks (id, title, completed, created_at) + 2 index\n"
        f"2. file_writer: filepath='db/migrations/V001.sql' — versioned migration\n"
        f"3. file_writer: filepath='docs/DB_DESIGN.md' — şema dokümantasyonu\n"
        f"Telegram'a rapor gönder."
    )
    task_db_sql = Task(
        name="task_db_sql",
        description=desc("task_db_sql", full_db_sql),
        expected_output=(
            "schema.sql, migrations/V001.sql, DB_DESIGN.md kaydedildi. "
            "Index stratejisi belgelendi. Telegram raporu."
        ),
        agent=agents["db_sql"],
        tools=tools_for("task_db_sql", CODE_TOOLS),
        context=[task_pm, task_backend_py],
    )

    # ── 6. NoSQL Sistemleri ───────────────────────────────────────────────
    full_db_nosql = (
        f"Cache ve gerçek zamanlı veri için NoSQL stratejisi belirle.\n"
        f"Redis cache yapılandırması ve MongoDB şeması (gerekiyorsa).\n"
        f"file_writer: filepath='docs/NOSQL_DESIGN.md', project_name='{project_name}'\n"
        f"Telegram'a rapor gönder."
    )
    task_db_nosql = Task(
        name="task_db_nosql",
        description=desc("task_db_nosql", full_db_nosql),
        expected_output=(
            "redis_config.md, NOSQL_DESIGN.md kaydedildi. "
            "Cache stratejisi belgelendi. Telegram raporu."
        ),
        agent=agents["db_nosql"],
        tools=tools_for("task_db_nosql", CODE_TOOLS),
        context=[task_pm, task_db_sql],
    )

    # ── 7. .NET Backend (opsiyonel) ───────────────────────────────────────
    full_backend_net = (
        f"Proje .NET gerektiriyorsa C# servisi yaz, gerektirmiyorsa mimari öneri belgesi hazırla.\n"
        f"file_writer: filepath='docs/DOTNET_DESIGN.md', project_name='{project_name}'\n"
        f"Telegram'a rapor gönder."
    )
    task_backend_net = Task(
        name="task_backend_net",
        description=desc("task_backend_net", full_backend_net),
        expected_output="DOTNET_DESIGN.md veya dotnet/ klasörü kaydedildi. Telegram raporu.",
        agent=agents["backend_net"],
        tools=tools_for("task_backend_net", CODE_TOOLS),
        context=[task_pm, task_db_sql, task_db_nosql],
    )

    # ── 8. Security ───────────────────────────────────────────────────────
    full_sec = (
        f"OWASP Top-10 güvenlik taraması yap.\n"
        f"XSS, SQLi, CSRF, hardcoded secret, CORS, auth açıklarını kontrol et.\n"
        f"file_writer: filepath='docs/SECURITY_REPORT.md', project_name='{project_name}'\n"
        f"Kritik bulgular için Telegram'a URGENT uyarı, güvenlik skoru ver."
    )
    task_security = Task(
        name="task_security",
        description=desc("task_security", full_sec),
        expected_output="SECURITY_REPORT.md kaydedildi. Telegram raporu gönderildi.",
        agent=agents["security"],
        tools=tools_for("task_security", [file_tool, tg_tool]),
        context=[task_frontend, task_backend_py, task_db_sql, task_db_nosql, task_backend_net],
    )

    # ── 6. QA ─────────────────────────────────────────────────────────────
    full_qa = (
        f"e2b_project_tester ile tüm proje dosyalarını test et (project_name='{project_name}').\n"
        f"Unit testler yaz ve çalıştır. Coverage >= %70 hedef.\n"
        f"file_writer: filepath='docs/TEST_REPORT.md', project_name='{project_name}'\n"
        f"Telegram'a sonuç raporu gönder."
    )
    task_qa = Task(
        name="task_qa",
        description=desc("task_qa", full_qa),
        expected_output="TEST_REPORT.md kaydedildi. E2B testleri tamamlandı. Telegram raporu.",
        agent=agents["qa"],
        tools=tools_for("task_qa", [e2b_run_tool, e2b_test_tool, e2b_project_tool, file_tool, tg_tool]),
        context=[task_frontend, task_backend_py, task_db_sql, task_db_nosql, task_backend_net, task_security],
    )

    # ── 12. Business Analyst: Logic doğrulama + PRD traceability ──────────
    full_ba = (
        "İki kritik görevi yerine getir:\n\n"
        "━━━ GÖREV A: BUSINESS LOGIC GÜVENLİK TESTİ ━━━\n"
        "Burp Suite/OWASP yaklaşımıyla business logic açıklarını test et:\n"
        "- Negatif değer manipülasyonu (qty=-1, price=0)\n"
        "- Race condition senaryoları (çift sipariş, çift ödeme)\n"
        "- Workflow bypass (adım atlama, durum geçiş ihlali)\n"
        "- IDOR kontrolleri (başkasının verisine erişim)\n"
        "- Boundary value testleri (0, -1, MAX_INT)\n"
        "- Regulatory uyum kontrolü (KVKK, GDPR)\n"
        f"file_writer → filepath='docs/BUSINESS_LOGIC_SECURITY.md', project_name='{project_name}'\n\n"
        "━━━ GÖREV B: İSTEK-TESLİM UYUM KONTROLÜ ━━━\n"
        "PRD'deki her gereksinimi teslim edilen kodla karşılaştır:\n"
        "- Her user story için: ✅ Tam / ⚠️ Kısmi / ❌ Eksik\n"
        "- Gereksinim karşılama oranını hesapla (%)\n"
        "- Eksikler için önceliklendirilmiş backlog oluştur\n"
        f"file_writer → filepath='docs/REQUIREMENTS_TRACEABILITY.md', project_name='{project_name}'\n\n"
        "Kritik bulgular için Telegram'a URGENT uyarı gönder.\n"
        "Genel uyum skoru ver (0-100)."
    )
    task_ba = Task(
        name="task_ba",
        description=desc("task_ba", full_ba),
        expected_output=(
            "BUSINESS_LOGIC_SECURITY.md ve REQUIREMENTS_TRACEABILITY.md kaydedildi. "
            "Gereksinim karşılama oranı hesaplandı. Telegram raporu gönderildi."
        ),
        agent=agents["ba"],
        tools=tools_for("task_ba", BA_TOOLS),
        context=[task_pm, task_frontend, task_backend_py, task_db_sql, task_qa],
    )

    # ── 12. Business Analyst ───────────────────────────────────────────────
    full_ba = (
        f"Business logic güvenlik testi yap (negatif miktar, race condition, IDOR vb.).\n"
        f"PRD gereksinimlerini teslim edilen kodla karşılaştır, uyum oranını hesapla.\n"
        f"3 rapor yaz ve kaydet (project_name='{project_name}'):\n"
        f"  docs/BUSINESS_LOGIC_SECURITY.md\n"
        f"  docs/REQUIREMENTS_TRACEABILITY.md\n"
        f"  docs/BUSINESS_RULES_VALIDATION.md\n"
        f"Telegram'a rapor gönder."
    )
    task_ba = Task(
        name="task_ba",
        description=desc("task_ba", full_ba),
        expected_output=(
            "BUSINESS_LOGIC_SECURITY.md, REQUIREMENTS_TRACEABILITY.md, "
            "BUSINESS_RULES_VALIDATION.md kaydedildi. "
            "Gereksinim karşılama oranı % belirtildi. Telegram raporu."
        ),
        agent=agents["ba"],
        tools=tools_for("task_ba", BA_TOOLS),
        context=[task_pm, task_frontend, task_backend_py,
                 task_db_sql, task_db_nosql, task_backend_net,
                 task_security, task_qa],
    )

    # ── 13. Code Analyst ───────────────────────────────────────────────────
    full_ana = (
        f"Kod kalitesini analiz et: complexity, DRY, dead code, hardcoded değerler.\n"
        f"Teknik borç skoru (1-10) ve top 5 iyileştirme önerisi ver.\n"
        f"file_writer: filepath='docs/CODE_QUALITY.md', project_name='{project_name}'\n"
        f"Telegram'a rapor gönder."
    )
    task_analysis = Task(
        name="task_analysis",
        description=desc("task_analysis", full_ana),
        expected_output="CODE_QUALITY.md kaydedildi. Teknik borç skoru belirlendi.",
        agent=agents["analyst"],
        tools=tools_for("task_analysis", [file_tool, tg_tool]),
        context=[task_frontend, task_backend_py, task_db_sql, task_db_nosql, task_backend_net, task_qa, task_ba],
    )
    # ── 8. DevOps ─────────────────────────────────────────────────────────
    full_do = (
        f"Projeyi production'a hazırla.\n"
        f"Dockerfile (multi-stage), docker-compose.yml, .github/workflows/ci.yml, README.md yaz.\n"
        f"Hepsini file_writer ile kaydet (project_name='{project_name}').\n"
        f"Telegram'a rapor gönder."
    )
    task_devops = Task(
        name="task_devops",
        description=desc("task_devops", full_do),
        expected_output="Dockerfile, docker-compose.yml, ci.yml, README.md kaydedildi.",
        agent=agents["devops"],
        tools=tools_for("task_devops", CODE_TOOLS),
        context=[task_backend_py, task_frontend, task_db_sql, task_db_nosql, task_architect, task_qa, task_ba],
    )

    # ── 9. EM: Final + ZIP ────────────────────────────────────────────────
    full_em = (
        f"Tüm ajan çıktılarını topla, FINAL_REPORT.md yaz, projeyi test et ve zip'le.\n"
        f"file_writer: filepath='docs/FINAL_REPORT.md', project_name='{project_name}'\n"
        f"e2b_project_tester → project_name='{project_name}'\n"
        f"zip_and_send → project_name='{project_name}', zip_filename='{project_name}.zip'\n"
        f"telegram_reporter ile final raporu gönder."
    )
    task_em_final = Task(
        name="task_em_final",
        description=desc("task_em_final", full_em),
        expected_output=(
            f"FINAL_REPORT.md kaydedildi. "
            f"{project_name}.zip Telegram'a gönderildi."
        ),
        agent=agents["em"],
        tools=tools_for("task_em_final", [file_tool, tg_tool, zip_tool, e2b_project_tool]),
        context=[
            task_pm, task_architect,
            task_ux, task_frontend, task_backend_py,
            task_db_sql, task_db_nosql, task_backend_net,
            task_security, task_qa, task_ba, task_analysis, task_devops,
        ],
    )

    return [
        task_pm, task_architect,
        task_ux, task_frontend, task_backend_py,
        task_db_sql, task_db_nosql, task_backend_net,
        task_security, task_qa, task_ba, task_analysis, task_devops,
        task_em_final,
    ]


# ─────────────────────────────────────────────
#  Proje adı türet
# ─────────────────────────────────────────────

def _slugify(text: str) -> str:
    """Brief'ten güvenli bir klasör adı türetir."""
    import re
    slug = re.sub(r"[^\w\s-]", "", text.lower())
    slug = re.sub(r"[\s_-]+", "_", slug).strip("_")
    return slug[:30] or "project"


# ─────────────────────────────────────────────
#  Ana Crew builder
# ─────────────────────────────────────────────

def build_crew(project_brief: str, project_name: str, completed_task_ids: list[str] | None = None) -> Crew:
    """Hiyerarşik crew'u oluşturur. Tamamlanan görevler skip edilir."""

    agents = {
        "pm":           create_product_manager(),
        "em":           create_engineering_manager(),
        "qa":           create_qa_tester(),
        "ux":           create_ux_designer(),
        "security":     create_security_expert(),
        "frontend":     create_frontend_dev(),
        "backend_py":   create_backend_python(),
        "backend_js":   create_backend_nodejs(),
        "backend_go":   create_backend_go(),
        "backend_rs":   create_backend_rust(),
        "backend_net":  create_backend_dotnet(),
        "db_sql":       create_db_sql_expert(),
        "db_nosql":     create_db_nosql_expert(),
        "analyst":      create_code_analyst(),
        "devops":       create_devops(),
        "architect":    create_solution_architect(),
        "ba":           create_business_analyst(),
    }

    agents["pm"].tools          = [file_tool, tg_tool]
    agents["em"].tools          = []           # manager_agent tool'suz olmalı
    agents["qa"].tools          = [e2b_run_tool, e2b_test_tool, e2b_project_tool, file_tool, tg_tool]
    agents["security"].tools    = [file_tool, tg_tool, cve_tool, web_search_tool]
    agents["frontend"].tools    = CODE_TOOLS
    agents["backend_py"].tools  = CODE_TOOLS
    agents["backend_js"].tools  = CODE_TOOLS
    agents["backend_go"].tools  = CODE_TOOLS
    agents["backend_rs"].tools  = CODE_TOOLS
    agents["backend_net"].tools = CODE_TOOLS
    agents["db_sql"].tools      = CODE_TOOLS
    agents["db_nosql"].tools    = CODE_TOOLS
    agents["devops"].tools      = CODE_TOOLS
    agents["analyst"].tools     = [file_tool, tg_tool]
    agents["ux"].tools          = [file_tool, tg_tool]
    agents["architect"].tools   = ARCH_TOOLS
    agents["ba"].tools          = BA_TOOLS

    # Tamamlanan görevleri skip et
    tasks = build_tasks(project_brief, agents, project_name, completed_task_ids)

    # Manager agent (em) agents listesine dahil edilmez — ayrıca manager_agent olarak verilir
    agent_list = [a for key, a in agents.items() if key != "em"]

    crew = Crew(
        agents=agent_list,
        tasks=tasks,
        process=Process.hierarchical,
        manager_agent=agents["em"],
        verbose=True,
        memory=False,
        full_output=True,
        output_log_file="logs/crew_output.log",
        max_rpm=10,              # Evren rate limit koruması
        share_crew=False,
        task_callback=task_callback,
        step_callback=step_callback,
    )
    return crew


# ─────────────────────────────────────────────
#  Çalıştırıcı — state-aware
# ─────────────────────────────────────────────

def run_project(project_brief: str) -> dict:
    """
    Projeyi çalıştırır.
    Resume durumunda tamamlanan görevler atlanır, sadece kalanlar çalışır.
    """
    project_name = _slugify(project_brief)

    # State yükle — önceki run'dan tamamlanan görevleri al
    state = load_state()
    completed = get_completed_tasks()
    is_resume = len(completed) > 0

    state["status"]        = "running"
    state["project_brief"] = project_brief
    state["project_name"]  = project_name
    save_state(state)

    if is_resume:
        bump_iteration()
        skipped = [t for t in TASK_IDS if t in completed]
        remaining = [t for t in TASK_IDS if t not in completed]
        send_message(
            f"▶️ *Proje Devam Ediyor*\n\n"
            f"📁 Proje: `{project_name}`\n"
            f"✅ Atlanan görevler ({len(skipped)}): {', '.join(f'`{t}`' for t in skipped)}\n"
            f"⏳ Çalışacak görevler ({len(remaining)}): {', '.join(f'`{t}`' for t in remaining)}"
        )
    else:
        report_project_start(project_brief, project_name, agent_count=17)

    try:
        crew = build_crew(project_brief, project_name, completed_task_ids=completed)
        result = crew.kickoff()

        from tools.file_writer_tool import OUTPUT_DIR
        project_dir = OUTPUT_DIR / project_name
        total_files = sum(1 for f in project_dir.rglob("*") if f.is_file()) if project_dir.exists() else 0

        state = load_state()
        state["status"]       = "completed"
        state["final_result"] = str(result)[:3000]
        save_state(state)

        report_project_complete(project_name, total_files, zip_sent=True)
        return {"success": True, "result": result, "project_name": project_name}

    except Exception as exc:
        error_msg = str(exc)
        record_error(error_msg)
        logger.error("Crew execution error: %s", exc, exc_info=True)

        quota_keywords = [
            "quota", "rate_limit", "429", "503",
            "insufficient_quota", "RateLimitError",
            "daily", "token limit", "context_length_exceeded",
        ]
        is_quota = any(kw.lower() in error_msg.lower() for kw in quota_keywords)

        # Tamamlanan görevler state'de kalıyor — resume'da atlanacak
        completed_now = get_completed_tasks()
        done_count  = len(completed_now)
        total_count = len(TASK_IDS)

        if is_quota:
            send_message(
                f"⚠️ *API Kota Limiti Doldu!*\n\n"
                f"✅ Tamamlanan: {done_count}/{total_count} görev (korunuyor)\n\n"
                f"Seçenekler:\n"
                f"1️⃣ Aynı provider'a yeni key:\n"
                f"   `/setkey {state.get('LLM_PROVIDER', 'evrenllm')} <yeni-key>`\n"
                f"   _(proje otomatik devam eder)_\n\n"
                f"2️⃣ Farklı provider'a geç:\n"
                f"   `/switch openrouter` veya `/switch deepseek`\n"
                f"   Sonra: `/resume`\n\n"
                f"3️⃣ Mevcut keylerini gör: `/providers`"
            )
        else:
            send_message(
                f"❌ *Hata Oluştu*\n\n"
                f"✅ Tamamlanan: {done_count}/{total_count} görev (korunuyor)\n"
                f"```\n{error_msg[:400]}\n```\n\n"
                f"Devam için: `/resume`"
            )

        return {"success": False, "error": error_msg, "quota_exceeded": is_quota}
