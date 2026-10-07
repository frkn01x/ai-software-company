"""
Obsidian Vault Builder
======================
Ajanların her adımını, kararını ve birbirleriyle olan etkileşimini
Obsidian-uyumlu Markdown dosyalarına kaydeder.

Vault Yapısı:
  vault/
    📁 agents/
        🔭 Research Agent.md       ← ajanın profili + tüm yaptıkları
        🏛️ Solution Architect.md
        🐍 Backend Python.md
        ... (18 ajan)
    📁 conversations/
        01_research→architect.md   ← kim kime ne iletti
        02_architect→pm.md
        ...
    📁 decisions/
        ADR-001_tech_stack.md      ← mimari kararlar
        ADR-002_database.md
    📁 tasks/
        task_research.md           ← her görevin tam çıktısı
        task_pm.md
        ...
    timeline.md                    ← kronolojik tüm olaylar
    project_graph.md               ← Mermaid: kim kiminle konuştu
    _index.md                      ← vault ana sayfası

Her .md dosyası Obsidian wikilink [[syntax]] ile birbirine bağlıdır.
Properties (YAML frontmatter) ile filtrelenebilir.
"""

import re
import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

# Vault ana dizini — proje output klasöründen bağımsız
VAULT_BASE = Path(__file__).parent / "vault"

# Thread-safe yazma kilidi
_lock = threading.Lock()

# Konuşma sırası sayacı
_conv_counter = 0

# ──────────────────────────────────────────────────────────────────────────────
#  Yardımcı sabitler
# ──────────────────────────────────────────────────────────────────────────────

AGENT_EMOJIS = {
    "Chief Product Manager":                   "📋",
    "VP of Engineering":                       "🏗️",
    "Principal QA Engineer":                   "🧪",
    "Principal UX/UI Designer":                "🎨",
    "Principal Security Engineer":             "🔒",
    "Principal Frontend Engineer":             "🖥️",
    "Principal Python Backend Engineer":       "🐍",
    "Principal Node.js Backend Engineer":      "🟨",
    "Principal Go Engineer":                   "🐹",
    "Principal Rust Engineer":                 "🦀",
    "Principal .NET / ASP.NET Core Architect": "💜",
    "Principal Database Engineer":             "🗄️",
    "Principal NoSQL":                         "🍃",
    "Principal Code Quality Analyst":          "🔍",
    "Principal DevOps Engineer":               "⚙️",
    "Principal Solution Architect":            "🏛️",
    "Principal Research Engineer":             "🔭",
    "Principal Business Analyst":              "📊",
}

AGENT_SHORT = {
    "Chief Product Manager":                   "PM",
    "VP of Engineering":                       "EM",
    "Principal QA Engineer":                   "QA",
    "Principal UX/UI Designer":                "UX",
    "Principal Security Engineer":             "SEC",
    "Principal Frontend Engineer":             "FE",
    "Principal Python Backend Engineer":       "BE-PY",
    "Principal Node.js Backend Engineer":      "BE-JS",
    "Principal Go Engineer":                   "BE-GO",
    "Principal Rust Engineer":                 "BE-RS",
    "Principal .NET / ASP.NET Core Architect": "BE-NET",
    "Principal Database Engineer":             "DB-SQL",
    "Principal NoSQL":                         "DB-NOSQL",
    "Principal Code Quality Analyst":          "ANALYST",
    "Principal DevOps Engineer":               "DEVOPS",
    "Principal Solution Architect":            "ARCH",
    "Principal Research Engineer":             "RESEARCH",
    "Principal Business Analyst":              "BA",
}


def _now_ts() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")


def _now_date() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")


def _safe_filename(name: str) -> str:
    """Dosya adı için güvenli string."""
    return re.sub(r'[<>:"/\\|?*]', "_", name)[:80]


def _get_emoji(role: str) -> str:
    for key, emoji in AGENT_EMOJIS.items():
        if key.lower() in role.lower():
            return emoji
    return "🤖"


def _get_short(role: str) -> str:
    for key, short in AGENT_SHORT.items():
        if key.lower() in role.lower():
            return short
    return "AGENT"


def _write(path: Path, content: str):
    """Thread-safe dosya yazma."""
    with _lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def _append(path: Path, content: str):
    """Thread-safe dosyaya ekleme."""
    with _lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(content)


# ──────────────────────────────────────────────────────────────────────────────
#  Ana Sınıf
# ──────────────────────────────────────────────────────────────────────────────

class ObsidianVaultBuilder:
    """
    Projenin tüm ajan aktivitesini Obsidian vault formatında kaydeder.
    Thread-safe, proje bazında ayrı vault klasörü kullanır.
    """

    def __init__(self, project_name: str, project_brief: str = ""):
        self.project_name  = project_name
        self.project_brief = project_brief
        self.vault_dir     = VAULT_BASE / _safe_filename(project_name)
        self._step_count: dict[str, int] = {}   # ajan → adım sayısı
        self._task_order: list[str] = []         # görev sırası
        self._decisions: list[dict] = []         # ADR'ler
        self._conv_counter = 0
        self._init_vault()

    # ── Vault başlatma ────────────────────────────────────────────────────

    def _init_vault(self):
        """Vault klasör yapısını oluşturur ve index sayfasını yazar."""
        for folder in ["agents", "conversations", "decisions", "tasks"]:
            (self.vault_dir / folder).mkdir(parents=True, exist_ok=True)

        # Ana index sayfası
        index = f"""---
project: {self.project_name}
created: {_now_date()}
type: project-vault
tags: [ai-company, crewai, project]
---

# 🏢 {self.project_name}

> {self.project_brief[:300] if self.project_brief else "AI Software Company projesi"}

## 📍 Hızlı Erişim

| Bölüm | Link |
|-------|------|
| 📅 Zaman Çizelgesi | [[timeline]] |
| 🗺️ Ajan Grafiği | [[project_graph]] |
| 📋 Görev Listesi | [[tasks/_index]] |

## 👥 Ajanlar

"""
        for role, emoji in AGENT_EMOJIS.items():
            short = AGENT_SHORT[role]
            index += f"- {emoji} [[agents/{short}|{role}]]\n"

        index += f"\n---\n*Vault oluşturuldu: {_now_ts()}*\n"
        _write(self.vault_dir / "_index.md", index)

        # Timeline başlat
        timeline_header = f"""---
project: {self.project_name}
type: timeline
tags: [timeline, activity]
---

# 📅 Proje Zaman Çizelgesi — {self.project_name}

"""
        _write(self.vault_dir / "timeline.md", timeline_header)

        # Tasks index başlat
        tasks_index = f"""---
project: {self.project_name}
type: task-index
---

# 📋 Görevler

| # | Görev | Ajan | Durum |
|---|-------|------|-------|
"""
        _write(self.vault_dir / "tasks" / "_index.md", tasks_index)

    # ── Ajan profil sayfası ───────────────────────────────────────────────

    def init_agent_page(self, agent_role: str):
        """Ajan için profil sayfası oluşturur (yoksa)."""
        short   = _get_short(agent_role)
        emoji   = _get_emoji(agent_role)
        ag_path = self.vault_dir / "agents" / f"{short}.md"

        if ag_path.exists():
            return  # Zaten var

        content = f"""---
agent: {agent_role}
short: {short}
emoji: {emoji}
project: {self.project_name}
type: agent-profile
tags: [agent, {short.lower()}]
---

# {emoji} {agent_role}

**Proje:** [[_index|{self.project_name}]]
**Kısa Ad:** `{short}`

## 📌 Görevler

## 💬 Konuşmalar

## 🔧 Kullandığı Araçlar

## 📝 Notlar ve Kararlar

---
*Sayfa oluşturuldu: {_now_ts()}*
"""
        _write(ag_path, content)

    # ── Ajan adımı kaydet ─────────────────────────────────────────────────

    def record_step(
        self,
        agent_role: str,
        action_type: str,          # "tool_use" | "thought" | "observation" | "decision"
        content: str,
        tool_name: Optional[str] = None,
        tool_result: Optional[str] = None,
    ):
        """
        Bir ajan adımını vault'a kaydeder:
          1. Timeline'a ekler
          2. Ajan sayfasına ekler
          3. Tool kullanımı ise araç bölümüne ekler
        """
        short   = _get_short(agent_role)
        emoji   = _get_emoji(agent_role)
        ts      = _now_ts()
        self._step_count[short] = self._step_count.get(short, 0) + 1
        step_no = self._step_count[short]

        # ─── Adım türüne göre ikon ─────────────────────────────────────
        type_icons = {
            "tool_use":    "🔧",
            "thought":     "💭",
            "observation": "👁️",
            "decision":    "⚡",
            "error":       "❌",
            "info":        "ℹ️",
        }
        t_icon = type_icons.get(action_type, "📝")

        # ─── Timeline'a ekle ───────────────────────────────────────────
        tl_entry = f"""
### {ts} — {emoji} [[agents/{short}|{short}]] {t_icon} {action_type.upper()}

"""
        if tool_name:
            tl_entry += f"**Araç:** `{tool_name}`\n\n"
        tl_entry += f"{content[:500]}\n"
        if tool_result:
            tl_entry += f"\n> **Sonuç:** {tool_result[:300]}\n"
        tl_entry += "\n---\n"
        _append(self.vault_dir / "timeline.md", tl_entry)

        # ─── Ajan sayfasına ekle ───────────────────────────────────────
        self.init_agent_page(agent_role)
        ag_path = self.vault_dir / "agents" / f"{short}.md"

        ag_entry = f"\n### Adım {step_no} — {ts}\n\n"
        ag_entry += f"**Tür:** {t_icon} `{action_type}`\n\n"
        if tool_name:
            ag_entry += f"**Araç:** `{tool_name}`\n\n"
        ag_entry += f"{content[:800]}\n"
        if tool_result:
            ag_entry += f"\n```\n{tool_result[:500]}\n```\n"

        # Ajan sayfasında "📌 Görevler" bölümünden önce "Adımlar" bölümüne ekle
        with _lock:
            existing = ag_path.read_text(encoding="utf-8")
            if "## 🏃 Adımlar" not in existing:
                existing = existing.replace(
                    "## 📌 Görevler",
                    "## 🏃 Adımlar\n\n## 📌 Görevler"
                )
            # Adımlar bölümünün sonuna ekle
            existing += ag_entry
            ag_path.write_text(existing, encoding="utf-8")

    # ── Görev başlangıç ───────────────────────────────────────────────────

    def record_task_start(self, task_name: str, agent_role: str, description: str):
        """Görev başladığında vault'a bildirir."""
        short = _get_short(agent_role)
        emoji = _get_emoji(agent_role)
        ts    = _now_ts()

        self._task_order.append(task_name)
        self.init_agent_page(agent_role)

        # Görev dosyası oluştur
        task_path = self.vault_dir / "tasks" / f"{task_name}.md"
        content = f"""---
task: {task_name}
agent: {agent_role}
agent_short: {short}
status: in_progress
started: {ts}
project: {self.project_name}
type: task
tags: [task, {short.lower()}, in-progress]
---

# {emoji} {task_name}

**Ajan:** [[agents/{short}|{agent_role}]]
**Başlangıç:** `{ts}`
**Durum:** 🔄 Devam Ediyor

## 📋 Görev Tanımı

{description[:1000]}

## 💬 Adımlar ve Düşünceler

## ✅ Çıktı

## 🔗 Bağlantılar

---
"""
        _write(task_path, content)

        # Timeline'a ekle
        _append(
            self.vault_dir / "timeline.md",
            f"\n### {ts} — 🚀 GÖREV BAŞLADI: `{task_name}`\n"
            f"**Ajan:** {emoji} [[agents/{short}|{short}]]\n\n---\n"
        )

        # Ajan sayfasına görev bağlantısı ekle
        ag_path = self.vault_dir / "agents" / f"{short}.md"
        _append(ag_path, f"\n- 🔄 [[tasks/{task_name}|{task_name}]] — {ts}\n")

        # Tasks index güncelle
        idx_path = self.vault_dir / "tasks" / "_index.md"
        order = len(self._task_order)
        _append(idx_path, f"| {order} | [[tasks/{task_name}\\|{task_name}]] | [[agents/{short}\\|{short}]] | 🔄 |\n")

    # ── Görev tamamlama ───────────────────────────────────────────────────

    def record_task_complete(
        self,
        task_name: str,
        agent_role: str,
        output: str,
        duration_secs: int = 0,
        files_created: Optional[list[str]] = None,
        e2b_passed: Optional[bool] = None,
    ):
        """Görev tamamlandığında vault'a yazar."""
        short = _get_short(agent_role)
        emoji = _get_emoji(agent_role)
        ts    = _now_ts()

        task_path = self.vault_dir / "tasks" / f"{task_name}.md"

        # Dosya oluşturulmamışsa minimal versiyon yaz
        if not task_path.exists():
            self.record_task_start(task_name, agent_role, "")

        # Görev dosyasına çıktı ekle
        completion_block = f"""

## ✅ Çıktı

```
{output[:2000]}
```

## 📊 Özet

| Metrik | Değer |
|--------|-------|
| ⏱️ Süre | {duration_secs // 60}dk {duration_secs % 60}sn |
| 🧪 E2B Test | {"✅ Geçti" if e2b_passed else "❌ Başarısız" if e2b_passed is False else "➖ Test yok"} |
| 📁 Dosya sayısı | {len(files_created) if files_created else 0} |

"""
        if files_created:
            completion_block += "## 📁 Oluşturulan Dosyalar\n\n"
            for f in files_created[:20]:
                completion_block += f"- `{f}`\n"

        completion_block += f"\n---\n*Tamamlandı: {ts}*\n"

        # Frontmatter'daki status'u güncelle
        with _lock:
            if task_path.exists():
                existing = task_path.read_text(encoding="utf-8")
                existing = existing.replace("status: in_progress", "status: completed")
                existing = existing.replace("🔄 Devam Ediyor", "✅ Tamamlandı")
                existing = existing.replace("tags: [task,", "tags: [task, completed,")
                existing += completion_block
                task_path.write_text(existing, encoding="utf-8")

        # Timeline'a ekle
        dur_str = f"{duration_secs // 60}dk {duration_secs % 60}sn" if duration_secs else "?"
        _append(
            self.vault_dir / "timeline.md",
            f"\n### {ts} — ✅ GÖREV TAMAMLANDI: `{task_name}`\n"
            f"**Ajan:** {emoji} [[agents/{short}|{short}]] | **Süre:** {dur_str}\n\n---\n"
        )

        # Tasks index'te durumu güncelle (append ile yeni satır)
        _append(
            self.vault_dir / "tasks" / "_index.md",
            f"<!-- {task_name} tamamlandı: {ts} -->\n"
        )

    # ── Konuşma/context aktarımı ──────────────────────────────────────────

    def record_conversation(
        self,
        from_agent: str,
        to_agent: str,
        subject: str,
        content: str,
        task_context: Optional[str] = None,
    ):
        """
        Bir ajandan diğerine bilgi aktarımını belgeler.
        Context chain'deki bağlantıları görünür kılar.
        """
        self._conv_counter += 1
        from_short = _get_short(from_agent)
        to_short   = _get_short(to_agent)
        from_emoji = _get_emoji(from_agent)
        to_emoji   = _get_emoji(to_agent)
        ts         = _now_ts()

        filename = f"{self._conv_counter:02d}_{from_short}→{to_short}.md"
        conv_path = self.vault_dir / "conversations" / filename

        content_md = f"""---
from: {from_agent}
to: {to_agent}
subject: "{subject}"
timestamp: {ts}
project: {self.project_name}
type: conversation
tags: [conversation, {from_short.lower()}, {to_short.lower()}]
---

# {from_emoji} → {to_emoji} {subject}

**Kimden:** [[agents/{from_short}|{from_agent}]]
**Kime:** [[agents/{to_short}|{to_agent}]]
**Zaman:** `{ts}`
{"**Görev Bağlamı:** `" + task_context + "`" if task_context else ""}

## 📨 İletilen Bilgi

{content[:3000]}

## 🔗 İlgili

- [[agents/{from_short}|{from_agent}]]
- [[agents/{to_short}|{to_agent}]]

---
"""
        _write(conv_path, content_md)

        # Her iki ajanın sayfasına da bağlantı ekle
        self.init_agent_page(from_agent)
        self.init_agent_page(to_agent)

        _append(
            self.vault_dir / "agents" / f"{from_short}.md",
            f"\n- 📤 [[conversations/{filename.replace('.md','')}|→ {to_short}: {subject}]] — {ts}\n"
        )
        _append(
            self.vault_dir / "agents" / f"{to_short}.md",
            f"\n- 📥 [[conversations/{filename.replace('.md','')}|← {from_short}: {subject}]] — {ts}\n"
        )

        # Timeline
        _append(
            self.vault_dir / "timeline.md",
            f"\n### {ts} — 💬 KONUŞMA: {from_emoji}{from_short} → {to_emoji}{to_short}\n"
            f"**Konu:** {subject}\n\n---\n"
        )

    # ── Karar kaydet (ADR) ────────────────────────────────────────────────

    def record_decision(
        self,
        agent_role: str,
        title: str,
        context: str,
        decision: str,
        alternatives: Optional[list[str]] = None,
        consequences: Optional[str] = None,
    ):
        """Önemli bir mimari veya teknik kararı ADR formatında kaydeder."""
        short = _get_short(agent_role)
        emoji = _get_emoji(agent_role)
        ts    = _now_ts()
        idx   = len(self._decisions) + 1

        self._decisions.append({"title": title, "agent": short, "ts": ts})
        filename = f"ADR-{idx:03d}_{_safe_filename(title)}.md"
        dec_path = self.vault_dir / "decisions" / filename

        alts_md = ""
        if alternatives:
            alts_md = "## 🔄 Değerlendirilen Alternatifler\n\n"
            for i, alt in enumerate(alternatives, 1):
                alts_md += f"{i}. {alt}\n"

        content_md = f"""---
adr: {idx:03d}
title: "{title}"
status: accepted
decider: {agent_role}
date: {_now_date()}
project: {self.project_name}
type: decision
tags: [adr, decision, {short.lower()}]
---

# ADR-{idx:03d}: {title}

**Karar Veren:** {emoji} [[agents/{short}|{agent_role}]]
**Tarih:** `{ts}`
**Durum:** ✅ Kabul Edildi

## 📋 Bağlam ve Problem

{context}

## ✅ Karar

{decision}

{alts_md}

## 📊 Sonuçlar

{consequences or "Belirtilmedi."}

---
"""
        _write(dec_path, content_md)

        # Timeline
        _append(
            self.vault_dir / "timeline.md",
            f"\n### {ts} — ⚡ KARAR: {emoji}{short} → `{title}`\n\n---\n"
        )

        return filename

    # ── Proje grafiği üret ────────────────────────────────────────────────

    def generate_project_graph(self):
        """
        Mermaid grafiği ile tüm ajan bağlantılarını görselleştirir.
        Obsidian'da Graph View ile görülebilir, ayrıca
        project_graph.md'de Mermaid kodu da bulunur.
        """
        ts = _now_ts()

        # Görev sırasından bağlantı al
        task_agents = {
            "task_research":     "RESEARCH",
            "task_pm":           "PM",
            "task_architect":    "ARCH",
            "task_ux":           "UX",
            "task_frontend":     "FE",
            "task_backend_py":   "BE-PY",
            "task_db_sql":       "DB-SQL",
            "task_db_nosql":     "DB-NOSQL",
            "task_backend_net":  "BE-NET",
            "task_security":     "SEC",
            "task_qa":           "QA",
            "task_ba":           "BA",
            "task_analysis":     "ANALYST",
            "task_devops":       "DEVOPS",
            "task_em_final":     "EM",
        }

        # Context zincirine göre bağlantılar
        links = [
            ("RESEARCH", "ARCH",     "araştırma bulgular"),
            ("RESEARCH", "PM",       "teknoloji önerileri"),
            ("PM",       "ARCH",     "PRD gereksinimleri"),
            ("PM",       "UX",       "kullanıcı hikayeleri"),
            ("ARCH",     "FE",       "frontend spec"),
            ("ARCH",     "BE-PY",    "backend spec"),
            ("ARCH",     "DB-SQL",   "veri modeli"),
            ("ARCH",     "DB-NOSQL", "cache stratejisi"),
            ("FE",       "BE-PY",    "API contract"),
            ("DB-SQL",   "DB-NOSQL", "veri akışı"),
            ("DB-SQL",   "BE-NET",   "ORM konfigürasyonu"),
            ("BE-PY",    "SEC",      "kod inceleme"),
            ("FE",       "SEC",      "XSS/CSRF analizi"),
            ("DB-SQL",   "SEC",      "SQLi analizi"),
            ("SEC",      "QA",       "güvenlik testleri"),
            ("BE-PY",    "QA",       "unit testler"),
            ("FE",       "QA",       "E2E testler"),
            ("QA",       "BA",       "test sonuçları"),
            ("PM",       "BA",       "PRD doğrulama"),
            ("BE-PY",    "BA",       "business logic"),
            ("QA",       "ANALYST",  "coverage raporu"),
            ("BE-PY",    "ANALYST",  "kod kalitesi"),
            ("ANALYST",  "DEVOPS",   "kalite raporu"),
            ("QA",       "DEVOPS",   "test geçişleri"),
            ("ARCH",     "DEVOPS",   "infra gereksinimleri"),
            ("DEVOPS",   "EM",       "deployment planı"),
            ("BA",       "EM",       "uyum raporu"),
            ("ANALYST",  "EM",       "kalite raporu"),
            ("SEC",      "EM",       "güvenlik raporu"),
            ("QA",       "EM",       "test raporu"),
        ]

        # Mermaid graph
        mermaid_lines = ["```mermaid", "graph TD"]
        for from_a, to_a, label in links:
            mermaid_lines.append(f'    {from_a}(["{from_a}"]) -->|"{label}"| {to_a}(["{to_a}"])')

        # Stil
        mermaid_lines += [
            "",
            "    style EM fill:#ff9900,stroke:#333,color:#000",
            "    style ARCH fill:#4a90d9,stroke:#333,color:#fff",
            "    style RESEARCH fill:#9b59b6,stroke:#333,color:#fff",
            "    style BA fill:#27ae60,stroke:#333,color:#fff",
            "    style SEC fill:#e74c3c,stroke:#333,color:#fff",
            "```",
        ]

        # Konuşma istatistikleri
        conv_stats = ""
        if self._decisions:
            conv_stats += "\n## ⚡ Alınan Kararlar\n\n"
            for d in self._decisions:
                conv_stats += (
                    f"- [[decisions/ADR-{len(self._decisions):03d}_"
                    f"{_safe_filename(d['title'])}|{d['title']}]] "
                    f"← {d['agent']}\n"
                )

        graph_content = f"""---
project: {self.project_name}
type: graph
tags: [graph, overview]
---

# 🗺️ {self.project_name} — Ajan Etkileşim Grafiği

**Oluşturuldu:** `{ts}`
**Toplam Ajan:** {len(AGENT_EMOJIS)}
**Toplam Konuşma:** {self._conv_counter}

## 🔗 Bağlantı Grafiği

{chr(10).join(mermaid_lines)}

## 📊 Ajan Aktivite Özeti

| Ajan | Adım Sayısı |
|------|-------------|
"""
        for short, count in sorted(self._step_count.items(), key=lambda x: -x[1]):
            emoji = next((e for k, e in AGENT_EMOJIS.items() if AGENT_SHORT.get(k) == short), "🤖")
            graph_content += f"| {emoji} [[agents/{short}\\|{short}]] | {count} |\n"

        graph_content += conv_stats
        graph_content += f"\n---\n*Son güncelleme: {ts}*\n"

        _write(self.vault_dir / "project_graph.md", graph_content)

    # ── Vault ZIP'e hazırla ───────────────────────────────────────────────

    def finalize(self):
        """
        Vault'u tamamlar:
        1. Proje grafiğini üretir
        2. Timeline'ı kapatır
        3. Vault dizinini döner (ZIP'e eklenecek)
        """
        self.generate_project_graph()

        _append(
            self.vault_dir / "timeline.md",
            f"\n---\n\n## 🏁 Proje Tamamlandı\n\n"
            f"**Zaman:** `{_now_ts()}`\n"
            f"**Toplam Adım:** {sum(self._step_count.values())}\n"
            f"**Toplam Konuşma:** {self._conv_counter}\n"
            f"**Alınan Karar:** {len(self._decisions)}\n"
        )

        return self.vault_dir


# ──────────────────────────────────────────────────────────────────────────────
#  Modül düzeyinde singleton
# ──────────────────────────────────────────────────────────────────────────────

_current_vault: Optional[ObsidianVaultBuilder] = None


def init_vault(project_name: str, project_brief: str = "") -> ObsidianVaultBuilder:
    """Yeni proje için vault başlatır."""
    global _current_vault
    _current_vault = ObsidianVaultBuilder(project_name, project_brief)
    return _current_vault


def get_vault() -> Optional[ObsidianVaultBuilder]:
    """Aktif vault'u döner."""
    return _current_vault


def finalize_vault() -> Optional[Path]:
    """Vault'u kapatır ve dizin yolunu döner."""
    if _current_vault:
        return _current_vault.finalize()
    return None
