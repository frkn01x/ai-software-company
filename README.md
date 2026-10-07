# 🏢 AI Software Company

> **Telegram üzerinden yönetilen, Docker'da çalışan hiyerarşik multi-agent yapay zeka yazılım şirketi.**
> Bir proje isteği yaz → 17 uzman ajan devreye girer → kaynak kodlar + belgeler ZIP olarak Telegram'a teslim edilir.


---

## 📋 İçindekiler

1. [Ne Yapar?](#-ne-yapar)
2. [Teknik Mimari](#-teknik-mimari)
3. [Ajan Kadrosu](#-ajan-kadrosu)
4. [Araçlar ve Entegrasyonlar](#-araçlar-ve-entegrasyonlar)
5. [Proje Akışı](#-proje-akışı)
6. [Çıktı Yapısı](#-çıktı-yapısı)
7. [Obsidian Vault](#-obsidian-vault)
8. [Kurulum](#-kurulum)
9. [Telegram Bot Komutları](#-telegram-bot-komutları)
10. [LLM Provider Yönetimi](#-llm-provider-yönetimi)
11. [CI/CD Pipeline](#-cicd-pipeline)

---

## 🎯 Ne Yapar?

**AI Software Company**, [CrewAI](https://crewai.com) framework'ü üzerine inşa edilmiş tam otonom bir yazılım geliştirme sistemidir. Gerçek bir yazılım şirketinin tüm rollerini yapay zeka ajanlarıyla simüle eder.

### Temel Akış

```
Kullanıcı → Telegram'a proje isteği yazar (düz metin, komut gerekmez)
    ↓
Bot onay butonu gösterir → ✅ Evet, Başlat!
    ↓
17 ajan sıralı olarak çalışır:
  PRD → Mimari → UX → Frontend → Backend → Veritabanı → Güvenlik → Test → DevOps
    ↓
Her ajan bitince Telegram'a detaylı rapor atar
    ↓
ZIP (kaynak kod + belgeler + Obsidian vault) → Telegram'a teslim
```

### Ne Üretir?

Bir proje sonunda teslim edilen dosyalar:

| Kategori | Dosyalar |
|----------|----------|
| **Belgeler** | PRD, Mimari (C4+ADR), NFR, UX Spec, Tech Stack, Güvenlik Raporu, Test Raporu, Kod Kalite Raporu, Final Rapor |
| **Frontend** | `index.html`, `styles/main.css`, `js/app.js` |
| **Backend** | `backend/main.py`, `backend/models.py`, `backend/requirements.txt` |
| **Veritabanı** | `db/schema.sql`, `migrations/V001.sql`, `docs/DB_DESIGN.md` |
| **DevOps** | `Dockerfile`, `docker-compose.yml`, `.github/workflows/ci.yml`, `README.md` |
| **Vault** | Obsidian uyumlu `vault/` klasörü (ajan konuşmaları, kararlar, timeline) |

---

## 🏗️ Teknik Mimari

### Sistem Diyagramı

```
┌──────────────────────────────────────────────────────────┐
│                    Telegram Bot                          │
│         (Doğal dil girişi + komut yönetimi)             │
└─────────────────────────┬────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────┐
│                   crew_manager.py                        │
│   CrewAI — Process.SEQUENTIAL                           │
│   state/project_state.json  ←→  Resume desteği         │
└─────────────────────────┬────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
  [17 Ajan]          [6 Araç]         [Vault]
  agents/*.py        tools/*.py    obsidian_vault.py
        │                 │
        ▼                 ▼
  ┌───────────┐    ┌─────────────────┐
  │ EvrenLLM  │    │   E2B Sandbox   │
  │ OpenRouter│    │  (kod test)     │
  │ DeepSeek  │    └─────────────────┘
  │ OpenAI    │
  └───────────┘
```

### Teknoloji Yığını

| Katman | Teknoloji | Versiyon |
|--------|-----------|---------|
| Agent Framework | [CrewAI](https://crewai.com) | 0.80.0 |
| LLM Çalışma Zamanı | LiteLLM (CrewAI dahili) | — |
| LLM Sağlayıcı | EvrenLLM / OpenRouter / DeepSeek / OpenAI | — |
| Kod Test Sandbox | [E2B](https://e2b.dev) Hobby | 1.0.3 |
| Telegram Bot | [python-telegram-bot](https://python-telegram-bot.org) | 21.6 |
| HTTP İstemci | httpx | 0.27.2 |
| Web Arama | DuckDuckGo (ücretsiz) + Serper API (opsiyonel) | 6.3.7 |
| Mesaj Kuyruğu | Redis | 7.2 |
| Container | Docker + Docker Compose | — |
| Vault | Obsidian uyumlu Markdown | — |

### Proje Yapısı

```
ai_software_company/
│
├── main.py                    # Giriş noktası
├── config.py                  # Merkezi konfigürasyon (hot-reload API key)
├── llm_factory.py             # LLM instance builder (4 provider)
├── crew_manager.py            # CrewAI orchestration + resume mekanizması
├── reporter.py                # Garantili raporlama (task_callback + step_callback)
├── obsidian_vault.py          # Obsidian vault builder (thread-safe)
│
├── agents/                    # 17 ajan — her biri ayrı dosyada
│   ├── product_manager.py
│   ├── solution_architect.py
│   ├── engineering_manager.py
│   ├── ux_designer.py
│   ├── frontend_dev.py
│   ├── backend_python.py
│   ├── backend_nodejs.py
│   ├── backend_go.py
│   ├── backend_rust.py
│   ├── backend_dotnet.py
│   ├── db_sql_expert.py
│   ├── db_nosql_expert.py
│   ├── security_expert.py
│   ├── qa_tester.py
│   ├── business_analyst.py
│   ├── code_analyst.py
│   └── devops.py
│
├── tools/                     # CrewAI araçları
│   ├── e2b_tool.py            # E2B kod çalıştırma (3 araç)
│   ├── file_writer_tool.py    # Dosyaya yazma
│   ├── zip_send_tool.py       # ZIP + Telegram gönderme
│   ├── telegram_report_tool.py
│   └── web_search_tool.py     # Web + GitHub + CVE + TechRadar arama
│
├── sandbox/
│   └── e2b_runner.py          # E2B runner (HTML/CSS validator, auto-install)
│
├── telegram_bot/
│   ├── bot.py                 # Bot handler'ları + inline butonlar
│   └── notifier.py            # Sync HTTP Telegram gönderici
│
├── state/
│   └── project_state.py       # Proje state kalıcılığı (resume için)
│
├── Dockerfile                 # Multi-stage, non-root user
├── docker-compose.yml         # app + redis
├── requirements.txt
└── .github/workflows/         # CI + CD + Release + Dependency pipelines
```

---

## 👥 Ajan Kadrosu

Sistemde **17 uzman ajan** bulunur. Her ajan; sertifikalar, gerçekçi kariyer geçmişi ve sektörde aranan uzmanlık profiliyle tanımlanmıştır.

| # | Ajan | Rol | Uzmanlık |
|---|------|-----|----------|
| 1 | 📋 Chief Product Manager | Strateji | PRD, user story, OKR, sprint planı |
| 2 | 🏛️ Solution Architect | Mimari | C4 model, ADR, NFR, API contract, DDD |
| 3 | 🎨 UX/UI Designer | Tasarım | Wireframe, design system, WCAG 2.1 AA |
| 4 | 🖥️ Frontend Developer | Geliştirme | HTML/CSS/JS, Core Web Vitals, erişilebilirlik |
| 5 | 🐍 Python Backend Dev | Geliştirme | FastAPI, SQLAlchemy 2.0, async, Pydantic v2 |
| 6 | 🟨 Node.js Backend Dev | Geliştirme | NestJS, Prisma, TypeScript strict, BullMQ |
| 7 | 🐹 Go Backend Dev | Geliştirme | Gin, gRPC, Protobuf, goroutine patterns |
| 8 | 🦀 Rust Developer | Geliştirme | Axum, Tokio, ownership, zero-copy |
| 9 | 💜 .NET Architect | Geliştirme | ASP.NET Core 8, EF Core, Clean Architecture |
| 10 | 🗄️ SQL DB Expert | Veritabanı | PostgreSQL, MySQL, index stratejisi, migration |
| 11 | 🍃 NoSQL Expert | Veritabanı | MongoDB, Redis, Cassandra, Elasticsearch |
| 12 | 🔒 Security Expert | Güvenlik | OWASP Top-10, CVE, SAST/DAST, CVSS |
| 13 | 🧪 QA Engineer | Test | pytest, Playwright, coverage, E2B sandbox |
| 14 | 📊 Business Analyst | Doğrulama | Business logic testi, traceability matrix |
| 15 | 🔍 Code Analyst | Kalite | Cyclomatic complexity, teknik borç, refactoring |
| 16 | ⚙️ DevOps Engineer | Altyapı | Docker multi-stage, K8s, CI/CD, SRE |
| 17 | 🏗️ Engineering Manager | Koordinasyon | Final rapor, ZIP, Telegram teslimi |

---

## 🔧 Araçlar ve Entegrasyonlar

### CrewAI Araçları (tools/)

| Araç | Sınıf | Ne Yapar |
|------|-------|---------|
| `e2b_code_executor` | `E2BCodeExecutionTool` | Kodu E2B sandbox'ta çalıştırır |
| `e2b_mandatory_test` | `E2BMandatoryTestTool` | Zorunlu test — başarısız olursa fix_hint döner |
| `e2b_project_tester` | `E2BProjectTestTool` | Tüm proje dosyalarını otomatik test eder |
| `file_writer` | `FileWriterTool` | Üretilen kodu `output/<proje>/` altına yazar |
| `zip_and_send` | `ZipAndSendTool` | Proje + vault ZIP'ler, Telegram'a gönderir |
| `telegram_reporter` | `TelegramReportTool` | Ajan raporlarını Telegram'a iletir |
| `web_search` | `WebSearchTool` | Serper API → DuckDuckGo fallback |
| `github_search` | `GitHubSearchTool` | GitHub repo araması (opsiyonel token) |
| `cve_search` | `CVESearchTool` | NVD API üzerinden CVE taraması |
| `tech_radar_search` | `TechRadarTool` | Teknoloji trend araştırması |

### E2B Sandbox Özellikleri

- Python, JavaScript ve Bash çalıştırır
- HTML syntax validator (etiket dengesi kontrolü)
- CSS syntax validator (blok dengesi)
- Eksik Python paketi varsa otomatik `pip install`
- Başarısız test sonucunda `fix_hint` üretir
- Tüm proje dosyalarını toplu test eder

### Obsidian Vault Sistemi

Her proje sonunda ZIP içine `vault/` klasörü eklenir:

```
vault/
├── _index.md              ← Ana sayfa (tüm ajanlara link)
├── timeline.md            ← Kronolojik tüm olaylar
├── project_graph.md       ← Mermaid ajan bağlantı haritası
├── agents/                ← 17 ajan profili (adım adım ne yaptığı)
├── conversations/         ← Ajanlar arası bilgi aktarımları
├── decisions/             ← ADR formatında mimari kararlar
└── tasks/                 ← Her görevin tam çıktısı + E2B sonuçları
```

Obsidian'da Graph View ile tüm ajan bağlantılarını görselleştirebilirsin.

---

## 🔄 Proje Akışı

### Görev Sırası (14 Görev)

```
1.  task_pm          → PRD.md
2.  task_architect   → ARCHITECTURE.md + NFR.md + TECH_STACK.md
3.  task_ux          → UX_SPEC.md
4.  task_frontend    → index.html + main.css + app.js
5.  task_backend_py  → backend/main.py + models.py
6.  task_db_sql      → db/schema.sql + migrations/
7.  task_db_nosql    → docs/NOSQL_DESIGN.md
8.  task_backend_net → docs/DOTNET_DESIGN.md (veya C# servis)
9.  task_security    → docs/SECURITY_REPORT.md
10. task_qa          → docs/TEST_REPORT.md
11. task_ba          → docs/BUSINESS_LOGIC_SECURITY.md + TRACEABILITY.md
12. task_analysis    → docs/CODE_QUALITY.md
13. task_devops      → Dockerfile + docker-compose.yml + ci.yml + README.md
14. task_em_final    → FINAL_REPORT.md + ZIP → Telegram
```

### Resume Mekanizması

API kota bittiğinde veya sistem kapandığında:

```
state/project_state.json ← tamamlanan görevler burada saklanır

/setkey evrenllm evren_llm_yeni_key  → otomatik resume
/resume                               → manuel resume

Tamamlanan görevler atlanır, sadece kalanlar çalışır.
```

### Garantili Raporlama

`reporter.py` iki katmanlı raporlama uygular:

- **task_callback** — her görev bitişinde otomatik Telegram raporu + state kayıt
- **step_callback** — her ajan adımı (tool kullanımı, düşünce) Obsidian vault'a yazılır

---

## 📁 Çıktı Yapısı

ZIP açıldığında şu yapı gelir:

```
proje_adi/
├── index.html
├── Dockerfile
├── docker-compose.yml
├── README.md
├── .env.example
├── styles/main.css
├── js/app.js
├── backend/
│   ├── main.py
│   ├── models.py
│   └── requirements.txt
├── db/
│   ├── schema.sql
│   └── migrations/V001__init.sql
├── docs/
│   ├── PRD.md
│   ├── ARCHITECTURE.md
│   ├── NFR.md
│   ├── TECH_STACK.md
│   ├── UX_SPEC.md
│   ├── SECURITY_REPORT.md
│   ├── TEST_REPORT.md
│   ├── CODE_QUALITY.md
│   └── FINAL_REPORT.md
├── .github/workflows/ci.yml
└── vault/          ← Obsidian vault
```

---

## 🗂️ Obsidian Vault

ZIP → `vault/` → Obsidian'da "Open folder as vault":

1. [Obsidian](https://obsidian.md) indir (ücretsiz)
2. ZIP aç
3. **Open folder as vault** → `vault/` seç
4. `_index.md` ana sayfasından başla
5. **Graph View** ile ajan bağlantılarını görselleştir

---

## 🚀 Kurulum

### Gereksinimler

- [Docker Desktop](https://docker.com/products/docker-desktop) 24.0+
- [Git](https://git-scm.com)

### Adımlar

```bash
# 1. Klonla
git clone https://github.com/KULLANICI_ADIN/ai-software-company.git
cd ai-software-company

# 2. .env oluştur
cp .env.example .env
# .env içini doldur (aşağıya bak)

# 3. Başlat
docker compose up -d --build

# 4. Logları izle
docker compose logs -f app
```

Şunu görmelisin:
```
✅ Tüm konfigürasyonlar tamam.
✅ Aktif LLM: provider=evrenllm, model=mimo-v2.6-pro
✅ Application started
```

### .env Doldurma

```env
# LLM
LLM_PROVIDER=evrenllm
LLM_MODEL=mimo-v2.6-pro
EVRENLLM_API_KEY=evren_llm_...     # evren-llmapi.ssyz.org.tr — ÜCRETSİZ

# Kod testi
E2B_API_KEY=e2b_...                # e2b.dev/dashboard — ÜCRETSİZ

# Telegram
TELEGRAM_BOT_TOKEN=...             # @BotFather → /newbot
TELEGRAM_CHAT_ID=...               # @userinfobot
TELEGRAM_ALLOWED_USERS=...         # Senin user ID'n

# Yedek LLM (opsiyonel)
OPENROUTER_API_KEY=sk-or-...
DEEPSEEK_API_KEY=sk-...

# Redis (docker-compose ile otomatik gelir)
REDIS_URL=redis://redis:6379/0
```

### API Key Kaynakları

| Key | Kaynak | Ücret |
|-----|--------|-------|
| `EVRENLLM_API_KEY` | [evren-llmapi.ssyz.org.tr](https://evren-llmapi.ssyz.org.tr) | **Ücretsiz** (10M token/gün) |
| `E2B_API_KEY` | [e2b.dev/dashboard](https://e2b.dev/dashboard) | Ücretsiz tier |
| `TELEGRAM_BOT_TOKEN` | [@BotFather](https://t.me/BotFather) → `/newbot` | Ücretsiz |
| `TELEGRAM_CHAT_ID` | [@userinfobot](https://t.me/userinfobot) | Ücretsiz |
| `OPENROUTER_API_KEY` | [openrouter.ai/keys](https://openrouter.ai/keys) | Opsiyonel |

---

## 📱 Telegram Bot Komutları

### Proje Başlatma

```
# En kolay yol — düz metin yaz, bot onay butonu gösterir:
Todo listesi yap, Python + SQLite + Docker

# Veya komutla:
/run E-ticaret sitesi, sepet ve ödeme sistemi
```

### Yönetim Komutları

| Komut | Açıklama |
|-------|----------|
| `/status` | Proje durumu + kota bilgisi |
| `/resume` | Kaldığı yerden devam et |
| `/reset` | Proje state'ini sıfırla |
| `/logs` | Son 50 satır log |
| `/providers` | Provider'lar ve key durumu |
| `/switch <provider>` | LLM değiştir |
| `/setkey <provider> <key>` | API key kaydet |
| `/setmodel <provider> <model>` | Model seç |
| `/getconfig` | Mevcut ayarlar |

---

## 🔀 LLM Provider Yönetimi

### Desteklenen Sağlayıcılar

| Provider | Key Formatı | Durum |
|----------|-------------|-------|
| **EvrenLLM** | `evren_llm_...` | **Önerilen** (10M token/gün ücretsiz) |
| OpenRouter | `sk-or-v1-...` | Yedek |
| DeepSeek | `sk-...` | Yedek |
| OpenAI | `sk-...` | Yedek |

### EvrenLLM Modelleri

| Model | Güç | Bağlam |
|-------|-----|--------|
| `mimo-v2.6-pro` | ⭐⭐⭐⭐⭐ (en güçlü) | 1M |
| `deepseek-v4.1-flash` | ⭐⭐⭐⭐ (kod uzmanı) | 1M |
| `glm-5.3` | ⭐⭐⭐⭐ (derin reasoning) | 512K |
| `gemma-4-31b` | ⭐⭐⭐ (hızlı) | 256K |
| `auto` | — (otomatik seçim) | — |

### Kota Bitince

```
# Yeni key gir → otomatik devam
/setkey evrenllm evren_llm_YENI_KEY

# Veya farklı provider'a geç
/switch openrouter
/resume
```

---

## 👷 CI/CD Pipeline

`.github/workflows/` içinde 4 pipeline:

| Dosya | Tetikleyici | Adımlar |
|-------|-------------|---------|
| `ci.yml` | Her push/PR | lint → type-check → test → security scan |
| `cd.yml` | `main` merge | docker build → trivy scan → staging → production |
| `release.yml` | `v*.*.*` tag | changelog → GitHub Release → production |
| `dependency-update.yml` | Her Pazartesi | pip-audit → CVE raporu → Telegram |



