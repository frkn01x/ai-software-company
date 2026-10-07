# 🏢 AI Software Company

> **Telegram üzerinden yönetilen, Docker'da çalışan, hiyerarşik multi-agent yapay zeka yazılım şirketi.**
> Bir proje isteği yaz → 17 uzman ajan devreye girer → ZIP dosyası Telegram'a teslim edilir.

[![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)](https://python.org)
[![CrewAI](https://img.shields.io/badge/CrewAI-0.80.0-orange)](https://crewai.com)
[![Docker](https://img.shields.io/badge/Docker-compose-blue?logo=docker)](https://docker.com)
[![Telegram](https://img.shields.io/badge/Telegram-Bot-blue?logo=telegram)](https://telegram.org)
[![E2B](https://img.shields.io/badge/E2B-Sandbox-green)](https://e2b.dev)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

## 📋 İçindekiler

1. [Proje Nedir?](#-proje-nedir)
2. [Mimari](#-mimari)
3. [Ajan Kadrosu](#-ajan-kadrosu)
4. [Ön Gereksinimler](#-ön-gereksinimler)
5. [Kurulum — Adım Adım](#-kurulum--adım-adım)
6. [API Key Alma Rehberi](#-api-key-alma-rehberi)
7. [Docker ile Çalıştırma](#-docker-ile-çalıştırma)
8. [Telegram Bot Komutları](#-telegram-bot-komutları)
9. [İlk Projeyi Başlatma](#-i̇lk-projeyi-başlatma)
10. [Çıktılar ve Dosya Yapısı](#-çıktılar-ve-dosya-yapısı)
11. [Obsidian Vault — Ajan Konuşmaları](#-obsidian-vault--ajan-konuşmaları)
12. [API Kota Yönetimi](#-api-kota-yönetimi)
13. [Provider / Model Değiştirme](#-provider--model-değiştirme)
14. [CI/CD Pipeline](#-cicd-pipeline)
15. [Geliştirici Rehberi](#-geliştirici-rehberi)
16. [Sık Sorulan Sorular](#-sık-sorulan-sorular)
17. [Katkı Rehberi](#-katkı-rehberi)

---

## 🎯 Proje Nedir?

**AI Software Company**, [CrewAI](https://crewai.com) framework'ü üzerine inşa edilmiş, gerçek bir yazılım şirketini simüle eden çok-ajanlı (multi-agent) yapay zeka sistemidir.

### Ne Yapar?

1. Telegram'a bir proje isteği yazarsın (komut bile gerekmez, düz metin yeterli)
2. 17 uzman yapay zeka ajanı sıralı olarak çalışmaya başlar
3. Her ajan kendi alanında dosyalar üretir, E2B sandbox'ta test eder, Telegram'a rapor atar
4. Proje bitince tüm kaynak kodları + belgeler ZIP olarak Telegram'a teslim edilir

### Ne Üretir?

| Dosya | Kim Üretir |
|-------|-----------|
| `docs/PRD.md` | Product Manager |
| `docs/ARCHITECTURE.md` | Solution Architect |
| `docs/NFR.md` | Solution Architect |
| `docs/TECH_STACK.md` | Solution Architect |
| `docs/UX_SPEC.md` | UX Designer |
| `index.html` + `styles/main.css` + `js/app.js` | Frontend Developer |
| `backend/main.py` + `backend/models.py` | Backend Python Dev |
| `db/schema.sql` + `migrations/V001.sql` | SQL DB Expert |
| `docs/SECURITY_REPORT.md` | Security Expert |
| `docs/TEST_REPORT.md` | QA Engineer |
| `docs/BUSINESS_LOGIC_SECURITY.md` | Business Analyst |
| `Dockerfile` + `docker-compose.yml` + `ci.yml` | DevOps Engineer |
| `docs/FINAL_REPORT.md` | Engineering Manager |
| `vault/` (Obsidian) | Tüm ajanlar |

---

## 🏗️ Mimari

```
┌─────────────────────────────────────────────────────────┐
│                   Telegram Bot                          │
│  (Yönetim arayüzü — komut + doğal dil girişi)          │
└──────────────────────────┬──────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                   main.py                               │
│              (Giriş noktası)                            │
└──────────────────────────┬──────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│               crew_manager.py                           │
│        CrewAI — Process.SEQUENTIAL                      │
│   state/project_state.json  ← Resume desteği           │
└──────────────────────────┬──────────────────────────────┘
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
    [17 Ajan]        [6 Araç]         [Vault]
   agents/*.py      tools/*.py    obsidian_vault.py
          │                │
          ▼                ▼
   ┌─────────────┐   ┌──────────────────────┐
   │ EvrenLLM /  │   │ E2B Sandbox          │
   │ OpenRouter / │   │ (Kod test ortamı)    │
   │ DeepSeek /  │   └──────────────────────┘
   │ OpenAI      │
   └─────────────┘
```

### Teknoloji Yığını

| Katman | Teknoloji |
|--------|-----------|
| Agent Framework | [CrewAI 0.80](https://crewai.com) |
| LLM Sağlayıcı | [EvrenLLM](https://evren-llmapi.ssyz.org.tr) / OpenRouter / DeepSeek / OpenAI |
| Kod Test Sandbox | [E2B](https://e2b.dev) Hobby (ücretsiz) |
| Bot Altyapısı | [python-telegram-bot 21.6](https://python-telegram-bot.org) |
| Container | Docker + docker-compose |
| Web Arama | DuckDuckGo (ücretsiz) + Serper API (opsiyonel) |
| Notlar/Vault | [Obsidian](https://obsidian.md) uyumlu Markdown |

---

## 👥 Ajan Kadrosu

Sistemde **17 uzman ajan** bulunur. Her ajan ayrı bir Python dosyasıdır (`agents/`).

| # | Ajan | Dosya | Uzmanlık |
|---|------|-------|----------|
| 1 | 📋 Chief Product Manager | `product_manager.py` | PRD, user stories, sprint planı |
| 2 | 🏛️ Solution Architect | `solution_architect.py` | C4 model, ADR, NFR, API contract |
| 3 | 🎨 UX/UI Designer | `ux_designer.py` | Wireframe, design system, WCAG |
| 4 | 🖥️ Frontend Developer | `frontend_dev.py` | HTML/CSS/JS, React, performance |
| 5 | 🐍 Python Backend Dev | `backend_python.py` | FastAPI, SQLAlchemy, async |
| 6 | 🟨 Node.js Backend Dev | `backend_nodejs.py` | NestJS, Prisma, TypeScript |
| 7 | 🐹 Go Backend Dev | `backend_go.py` | Gin, gRPC, concurrency |
| 8 | 🦀 Rust Developer | `backend_rust.py` | Axum, Tokio, memory safety |
| 9 | 💜 .NET Architect | `backend_dotnet.py` | ASP.NET Core, EF Core, Azure |
| 10 | 🗄️ SQL DB Expert | `db_sql_expert.py` | PostgreSQL, MySQL, indexing |
| 11 | 🍃 NoSQL Expert | `db_nosql_expert.py` | MongoDB, Redis, Elasticsearch |
| 12 | 🔒 Security Expert | `security_expert.py` | OWASP Top-10, CVE, pentest |
| 13 | 🧪 QA Engineer | `qa_tester.py` | pytest, E2E, coverage |
| 14 | 📊 Business Analyst | `business_analyst.py` | Logic testing, traceability |
| 15 | 🔍 Code Analyst | `code_analyst.py` | Complexity, tech debt |
| 16 | ⚙️ DevOps Engineer | `devops.py` | Docker, K8s, CI/CD |
| 17 | 🏗️ Engineering Manager | `engineering_manager.py` | Koordinasyon, final ZIP |

---

## 🔧 Ön Gereksinimler

Başlamadan önce bilgisayarında şunlar kurulu olmalı:

### Zorunlu

| Araç | Minimum Versiyon | Kontrol Komutu |
|------|-----------------|----------------|
| [Docker Desktop](https://docker.com/products/docker-desktop) | 24.0+ | `docker --version` |
| [Docker Compose](https://docs.docker.com/compose/) | 2.20+ | `docker compose version` |
| [Git](https://git-scm.com) | 2.40+ | `git --version` |

### Opsiyonel (Geliştirme için)

| Araç | Kullanım |
|------|----------|
| [Python 3.11+](https://python.org) | Docker olmadan çalıştırmak için |
| [Obsidian](https://obsidian.md) | Ajan konuşmalarını görselleştirmek için |

> **Not:** Python'ı sisteme kurman gerekmez — Docker içinde çalışır. Sadece Docker yeterli.

---

## 🚀 Kurulum — Adım Adım

### Adım 1: Repo'yu klonla

```bash
git clone https://github.com/KULLANICI_ADI/ai-software-company.git
cd ai-software-company
```

### Adım 2: `.env` dosyasını oluştur

```bash
cp .env.example .env
```

`.env` dosyasını bir metin editörüyle aç ve doldur (bir sonraki bölüme bak):

```bash
# Windows
notepad .env

# macOS/Linux
nano .env
```

### Adım 3: Docker image'ını build et ve başlat

```bash
docker compose up -d --build
```

İlk build 5-10 dakika sürebilir (Python bağımlılıkları indirilir).

### Adım 4: Başlatıldığını doğrula

```bash
docker compose logs app --tail 20
```

Şunu görmelisin:

```
✅ Tüm konfigürasyonlar tamam.
✅ Aktif LLM: provider=evrenllm, model=mimo-v2.6-pro
✅ Telegram bot başlatılıyor...
✅ Application started
```

### Adım 5: Telegram'da botu bul ve test et

Telegram'da botunu ara (BotFather'dan aldığın isim), `/start` komutunu gönder. Komut listesini görmelisin.

---

## 🔑 API Key Alma Rehberi

`.env` dosyasını doldurmak için 4 API key gerekir. Hepsi **ücretsiz** başlangıç planı sunar.

---

### 1. EvrenLLM API Key (ÖNERİLEN — Tamamen Ücretsiz)

> 10M token/gün, 1 Kasım 2026'ya kadar tüm modeller ücretsiz. Türkiye'de bare-metal H200 kümesinde çalışır.

1. [evren-llmapi.ssyz.org.tr](https://evren-llmapi.ssyz.org.tr) adresine git
2. Kayıt ol / giriş yap
3. **API Keys** sayfasına git → **Yeni Anahtar Oluştur**
4. Key formatı: `evren_llm_...`
5. **Kullanım Şartları:** İlk API çağrısında sistem otomatik olarak kabul eder (`llm_factory.py` halleder)

```env
LLM_PROVIDER=evrenllm
LLM_MODEL=mimo-v2.6-pro
EVRENLLM_API_KEY=evren_llm_buraya_yaz
```

**Mevcut EvrenLLM Modelleri:**

| Model ID | Açıklama | Bağlam |
|----------|----------|--------|
| `mimo-v2.6-pro` | En güçlü, çok-modal (önerilen) | 1M token |
| `deepseek-v4.1-flash` | Kod & ajan uzmanı | 1M token |
| `glm-5.3` | Amiral model, derin reasoning | 512K token |
| `gemma-4-31b` | Hızlı sohbet | 256K token |
| `qwen3.8-flash-next` | Yüksek hacim | 256K token |
| `auto` | Gateway otomatik seçer | — |

---

### 2. E2B API Key (Zorunlu — Ücretsiz Tier Var)

> Ajanların yazdığı kodları güvenli sandbox'ta test eder.

1. [e2b.dev/dashboard](https://e2b.dev/dashboard) adresine git
2. GitHub ile giriş yap
3. **API Keys** → **New API Key**
4. Key formatı: `e2b_...`

```env
E2B_API_KEY=e2b_buraya_yaz
```

---

### 3. Telegram Bot Token (Zorunlu)

> Sistemi yönettiğin ve raporları aldığın bot.

**Bot oluşturma:**
1. Telegram'da [@BotFather](https://t.me/BotFather)'a git
2. `/newbot` komutunu gönder
3. Bot için bir isim gir (örn: `AI Software Company`)
4. Kullanıcı adı gir — `_bot` ile bitmeli (örn: `aisoftwareco_bot`)
5. Token'ı kopyala: `1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ`

**Chat ID öğrenme:**
1. [@userinfobot](https://t.me/userinfobot)'a git
2. `/start` gönder
3. Sana `Your ID: 123456789` şeklinde döner

```env
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ
TELEGRAM_CHAT_ID=123456789
TELEGRAM_ALLOWED_USERS=123456789
```

> `TELEGRAM_ALLOWED_USERS`: Botu kullanabilecek Telegram user ID'leri (virgülle ayır). Boş bırakırsan herkese açık olur — **önerilmez**.

---

### 4. OpenRouter API Key (Opsiyonel)

> EvrenLLM kotası biterse yedek olarak kullanılır.

1. [openrouter.ai/keys](https://openrouter.ai/keys) adresine git
2. Hesap oluştur → **Create Key**
3. Key formatı: `sk-or-v1-...`

```env
OPENROUTER_API_KEY=sk-or-v1-buraya_yaz
```

---

### 5. DeepSeek API Key (Opsiyonel)

1. [platform.deepseek.com/api_keys](https://platform.deepseek.com/api_keys) adresine git
2. Hesap oluştur → **Create API Key**
3. Key formatı: `sk-...`

```env
DEEPSEEK_API_KEY=sk-buraya_yaz
```

---

### 6. Serper API Key (Opsiyonel — Web Arama)

> Research Agent için Google araması. Yoksa DuckDuckGo kullanılır (ücretsiz).

1. [serper.dev](https://serper.dev) adresine git
2. Kayıt ol → 2500 ücretsiz arama/ay
3. Key formatı: `abc123...`

```env
SERPER_API_KEY=buraya_yaz
```

---

### Doldurulmuş `.env` Örneği

```env
# ─── LLM ───────────────────────────────────────────
LLM_PROVIDER=evrenllm
LLM_MODEL=mimo-v2.6-pro

# ─── API Keys ──────────────────────────────────────
OPENAI_API_KEY=sk-dummy-not-used
OPENROUTER_API_KEY=
DEEPSEEK_API_KEY=
EVRENLLM_API_KEY=evren_llm_BURAYA_YAZ

# ─── E2B ───────────────────────────────────────────
E2B_API_KEY=e2b_BURAYA_YAZ

# ─── Telegram ──────────────────────────────────────
TELEGRAM_BOT_TOKEN=BURAYA_YAZ
TELEGRAM_CHAT_ID=BURAYA_YAZ
TELEGRAM_ALLOWED_USERS=BURAYA_YAZ

# ─── Redis ─────────────────────────────────────────
REDIS_URL=redis://redis:6379/0

# ─── Opsiyonel ─────────────────────────────────────
SERPER_API_KEY=
GITHUB_TOKEN=

# ─── Log ───────────────────────────────────────────
LOG_LEVEL=INFO
```

---

## 🐳 Docker ile Çalıştırma

### Başlatma

```bash
# İlk kez veya kod değişikliği sonrası
docker compose up -d --build

# Sonraki başlatmalarda (build gerekmez)
docker compose up -d
```

### Durdurma

```bash
docker compose down
```

### Logları İzleme

```bash
# Canlı log takibi
docker compose logs -f app

# Son 50 satır
docker logs ai_software_company --tail 50
```

### Yeniden Başlatma (kod değişikliği olmadan)

```bash
docker compose restart app
```

### Container içine girme (debug için)

```bash
docker exec -it ai_software_company bash
```

### Durumu Kontrol Etme

```bash
docker compose ps
```

Şunu görmelisin:
```
NAME                    STATUS
ai_software_company     running (healthy)
ai_company_redis        running (healthy)
```

---

## 📱 Telegram Bot Komutları

Bot aktif olunca Telegram'dan şu komutları kullanabilirsin:

### 🚀 Proje Yönetimi

| Komut | Açıklama | Örnek |
|-------|----------|-------|
| `<düz metin>` | Proje başlat (komut gereksiz!) | `Todo listesi yap, Python + SQLite` |
| `/run <brief>` | Proje başlat (komutla) | `/run E-ticaret sitesi, sepet ve ödeme` |
| `/resume` | Kaldığı yerden devam et | `/resume` |
| `/status` | Proje durumu + kota bilgisi | `/status` |
| `/reset` | Proje state'ini sıfırla | `/reset` |

### 🔑 LLM Yönetimi

| Komut | Açıklama | Örnek |
|-------|----------|-------|
| `/switch <provider>` | Aktif LLM'i değiştir | `/switch openrouter` |
| `/setkey <provider> <key>` | API key kaydet | `/setkey evrenllm evren_llm_abc` |
| `/setmodel <provider> <model>` | Model seç | `/setmodel evrenllm glm-5.3` |
| `/providers` | Tüm provider'lar ve kota | `/providers` |
| `/getconfig` | Mevcut ayarları göster | `/getconfig` |

### 📊 İzleme

| Komut | Açıklama |
|-------|----------|
| `/logs` | Son 50 satır log |
| `/help` | Komut listesi |

---

## 💡 İlk Projeyi Başlatma

### Yöntem 1 — Düz Metin (En Kolay)

Telegram'da bota sadece proje isteğini yaz:

```
Bana Python ve SQLite kullanan, Docker'da çalışan 
basit bir not alma uygulaması yap. Responsive arayüz olsun.
```

Bot şu onay ekranını gösterecek:

```
💡 Proje talebini anladım!

📋 Brief: Bana Python ve SQLite kullanan...

🤖 evrenllm / mimo-v2.6-pro
👥 17 ajan hazır

[ ✅ Evet, Başlat! ]  [ ❌ İptal ]  [ ✏️ Düzenle ]
```

**✅ Evet, Başlat!** butonuna bas → sistem çalışmaya başlar.

### Yöntem 2 — `/run` Komutu

```
/run Restoran sipariş yönetimi — masa takibi, ürün listesi, sipariş alma
```

### Proje Süreci

Her ajan bitince Telegram'a detaylı rapor gelir:

```
🐍 [BE-PY] Görev Tamamlandı
🕐 14:32 UTC
⏱️ Süre: 3dk 12sn
📌 Görev: Python/FastAPI backend yazıldı
🧪 E2B Test: ✅ Geçti
📁 Oluşturulan dosyalar:
  • backend/main.py
  • backend/models.py
  • backend/requirements.txt
```

Proje tamamlanınca ZIP Telegram'a gelir:

```
📦 proje_adi.zip hazır!
📁 Proje: 24 dosya
📒 Obsidian vault: 47 dosya
💾 156 KB
```

---

## 📁 Çıktılar ve Dosya Yapısı

ZIP açıldığında şu yapıyı görürsün:

```
proje_adi/
│
├── 📄 index.html              ← Frontend ana sayfa
├── 📄 Dockerfile              ← Production Docker image
├── 📄 docker-compose.yml      ← Tüm servisler
├── 📄 README.md               ← Proje rehberi
├── 📄 .env.example            ← Env şablonu
│
├── styles/
│   └── main.css               ← CSS stilleri
│
├── js/
│   └── app.js                 ← JavaScript
│
├── backend/
│   ├── main.py                ← FastAPI uygulaması
│   ├── models.py              ← Veri modelleri
│   └── requirements.txt       ← Python bağımlılıkları
│
├── db/
│   ├── schema.sql             ← Veritabanı şeması
│   └── migrations/
│       └── V001__init.sql     ← İlk migration
│
├── docs/
│   ├── PRD.md                 ← Ürün gereksinimleri
│   ├── ARCHITECTURE.md        ← Sistem mimarisi (C4, ADR)
│   ├── NFR.md                 ← Non-functional gereksinimler
│   ├── TECH_STACK.md          ← Teknoloji kararları
│   ├── UX_SPEC.md             ← UX/UI spesifikasyonu
│   ├── SECURITY_REPORT.md     ← Güvenlik raporu (OWASP)
│   ├── TEST_REPORT.md         ← Test sonuçları
│   ├── BUSINESS_LOGIC_SECURITY.md
│   ├── REQUIREMENTS_TRACEABILITY.md
│   ├── CODE_QUALITY.md        ← Teknik borç raporu
│   └── FINAL_REPORT.md        ← Sprint özeti
│
├── .github/
│   └── workflows/
│       └── ci.yml             ← GitHub Actions CI/CD
│
└── vault/                     ← Obsidian Vault
    ├── _index.md
    ├── agents/                ← Her ajanın profili
    ├── conversations/         ← Ajanlar arası konuşmalar
    ├── decisions/             ← ADR kayıtları
    ├── tasks/                 ← Görev detayları
    ├── timeline.md            ← Kronolojik olaylar
    └── project_graph.md       ← Mermaid ajan grafiği
```

---

## 🗂️ Obsidian Vault — Ajan Konuşmaları

Her proje bitiminde ZIP içinde `vault/` klasörü gelir. Bu klasör [Obsidian](https://obsidian.md)'da açılabilen bir knowledge base'dir ve **ajanların birbirleriyle ne konuştuğunu, hangi kararları neden aldığını** gösterir.

### Nasıl Açılır?

1. [Obsidian](https://obsidian.md)'ı indir (ücretsiz)
2. ZIP'i aç
3. Obsidian → **Open folder as vault**
4. `vault/` klasörünü seç
5. `_index.md` ana sayfasından başla

### Vault İçeriği

- **`agents/`** — Her ajanın profil sayfası: yaptığı adımlar, kullandığı araçlar
- **`conversations/`** — `05_ARCH→FE.md` gibi dosyalar: kim kime ne iletti
- **`decisions/`** — ADR formatında mimari kararlar
- **`tasks/`** — Her görevin tam çıktısı, E2B test sonuçları
- **`timeline.md`** — Tüm olaylar kronolojik sırada
- **`project_graph.md`** — Mermaid ile ajan bağlantı haritası (Graph View'da görsel)

### Graph View

Obsidian'ın Graph View'ında 17 ajanın birbirine nasıl bağlandığını interaktif olarak görebilirsin.

---

## 💰 API Kota Yönetimi

### EvrenLLM Kota Kontrolü

```
/status
```

Şunu görürsün:
```
🔋 Evren LLM Kota:
  Kalan: 8,234,567 token
  Sıfırlanma: 2026-10-07 00:00 UTC
```

### Kota Dolunca Ne Yaparsın?

**Seçenek 1 — Aynı provider'a yeni key:**
```
/setkey evrenllm evren_llm_YENI_KEY
```
Proje hata durumundaysa otomatik devam eder, `/resume` yazman bile gerekmez.

**Seçenek 2 — Farklı provider'a geç:**
```
/switch openrouter
/resume
```

**Seçenek 3 — Ertesi gün bekle:**
EvrenLLM kotası gece yarısı UTC'de sıfırlanır. Bekleyip `/resume` yazabilirsin — tamamlanan görevler state'de korunur.

### Proje Kaldığı Yerden Devam

State dosyası `state/project_state.json`'da saklanır. Sistem kapansa bile:
- Tamamlanan görevler kayıtlı
- `/resume` yazınca sadece kalan görevler çalışır
- Token israfı olmaz

---

## 🔀 Provider / Model Değiştirme

### Mevcut Provider'ları Gör

```
/providers
```

```
📋 Provider Durumu

▶️ evrenllm ◀ AKTİF
   Key: ✅ evren_...MLM
   Modeller: deepseek-v4.1-flash · glm-5.3 · mimo-v2.6-pro · auto

  openrouter
   Key: ✅ sk-or-...1234
   Modeller: openai/gpt-4o · claude-3.5-sonnet

  deepseek
   Key: ❌ Kayıtlı key yok
   Modeller: deepseek-chat · deepseek-coder
```

### Provider Değiştir

```
/switch openrouter
/switch evrenllm
/switch deepseek
```

### Model Değiştir

```
# EvrenLLM modelleri
/setmodel evrenllm mimo-v2.6-pro       # En güçlü (önerilen)
/setmodel evrenllm deepseek-v4.1-flash # Kod uzmanı
/setmodel evrenllm glm-5.3             # Derin reasoning
/setmodel evrenllm auto                # Otomatik seçim

# OpenRouter modelleri
/setmodel openrouter openai/gpt-4o
/setmodel openrouter anthropic/claude-3.5-sonnet

# DeepSeek modelleri
/setmodel deepseek deepseek-coder
```

---

## 👷 CI/CD Pipeline

`.github/workflows/` altında 4 pipeline bulunur:

### `ci.yml` — Her Push/PR'da Çalışır

```
lint (ruff + black + isort)
    ↓
type-check (mypy)
    ↓
test (pytest + coverage)
    ↓
security (bandit + pip-audit)
```

### `cd.yml` — `main` Branch'e Merge'de Çalışır

```
Docker build + push (Docker Hub)
    ↓
Trivy image scan
    ↓
Staging deploy (SSH)
    ↓
Telegram bildirim
```

### `release.yml` — `v*.*.*` Tag'inde Çalışır

```
git-cliff ile changelog oluştur
    ↓
GitHub Release yayınla
    ↓
Production deploy
    ↓
Telegram bildirim
```

### `dependency-update.yml` — Her Pazartesi 08:00 UTC

```
pip-audit ile CVE taraması
    ↓
Outdated paket kontrolü
    ↓
Telegram haftalık rapor
```

### GitHub Secrets Kurulumu

Repo → Settings → Secrets → Actions → New repository secret:

| Secret | Değer |
|--------|-------|
| `DOCKER_USERNAME` | Docker Hub kullanıcı adı |
| `DOCKER_PASSWORD` | Docker Hub PAT token |
| `TELEGRAM_BOT_TOKEN` | Bot token |
| `TELEGRAM_CHAT_ID` | Chat ID |
| `DEPLOY_HOST` | Sunucu IP (opsiyonel) |
| `DEPLOY_USER` | SSH kullanıcı (opsiyonel) |
| `DEPLOY_SSH_KEY` | SSH private key (opsiyonel) |

---

## 🛠️ Geliştirici Rehberi

### Yerel Geliştirme (Docker Olmadan)

```bash
# Python 3.11+ gerekli
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt

# .env doldur
cp .env.example .env

# Çalıştır
python main.py
```

### Yeni Ajan Ekleme

1. `agents/` klasörüne yeni dosya oluştur:

```python
# agents/my_agent.py
from crewai import Agent
from llm_factory import build_llm

def create_my_agent() -> Agent:
    return Agent(
        role="My Agent Role",
        goal="Ne yapacak",
        backstory="Geçmişi",
        llm=build_llm(temperature=0.2),
        verbose=True,
        allow_delegation=False,
        max_iter=8,
        memory=False,
    )
```

2. `agents/__init__.py`'ye import ekle:

```python
from .my_agent import create_my_agent
```

3. `crew_manager.py`'de `build_crew()` içine ekle:

```python
from agents import create_my_agent

agents["my_agent"] = create_my_agent()
agents["my_agent"].tools = [file_tool, tg_tool]
```

4. `build_tasks()` içine görev ekle.

### Yeni LLM Provider Ekleme

`llm_factory.py`'de `build_llm()` fonksiyonuna yeni elif bloğu ekle:

```python
elif provider == "yeni_provider":
    llm = LLM(
        model=f"openai/{model}",
        api_key=api_key,
        base_url="https://api.yeni-provider.com/v1",
        temperature=temperature,
        max_tokens=4096,
    )
```

`config.py`'de property ekle:

```python
@property
def yeni_provider_api_key(self) -> Optional[str]:
    return self.get("YENI_PROVIDER_API_KEY")
```

### Log Seviyeleri

```env
LOG_LEVEL=DEBUG    # Her şeyi göster (geliştirme)
LOG_LEVEL=INFO     # Normal çalışma (varsayılan)
LOG_LEVEL=WARNING  # Sadece uyarılar
LOG_LEVEL=ERROR    # Sadece hatalar
```

### Proje State'ini Sıfırlama

```bash
# Telegram'dan
/reset

# Veya doğrudan
rm state/project_state.json
```

---

## ❓ Sık Sorulan Sorular

**S: Proje ne kadar sürer?**

Proje karmaşıklığına ve seçilen modele göre değişir:
- Basit proje (todo, blog): 30-90 dakika
- Orta proje (e-ticaret, API): 1-3 saat
- Büyük proje (ERP, mikroservis): 3-6 saat

**S: Kota bitti, proje yarıda kaldı. Ne yapayım?**

```
/setkey evrenllm evren_llm_YENI_KEY
```
Sistem otomatik devam eder. Ya da farklı provider:
```
/switch openrouter
/resume
```

**S: "Received None or empty response" hatası alıyorum?**

LLM'den boş cevap geldi. Genellikle:
- Context çok uzun → Daha kısa brief yaz
- Rate limit → Bekle, sistem otomatik retry yapar
- Model uyumsuzluğu → `/setmodel evrenllm auto` dene

**S: E2B sandbox hatası alıyorum?**

E2B Hobby tier'da bazı kısıtlamalar var. E2B key'ini [e2b.dev/dashboard](https://e2b.dev/dashboard)'dan kontrol et. Kota dolmuş olabilir.

**S: Docker build çok uzun sürüyor?**

İlk build uzun sürer (Python bağımlılıkları). Sonraki build'ler cache'li olur:
```bash
docker compose up -d  # build olmadan, sadece başlat
```

**S: Telegram'da "⛔ Bu bot özel kullanıma aittir" mesajı alıyorum?**

`TELEGRAM_ALLOWED_USERS` değişkeninde kendi user ID'n yok. `/status` komutunu dene, user ID'ni öğrenmek için [@userinfobot](https://t.me/userinfobot)'a yaz.

**S: Obsidian vault'u nerede bulabilirim?**

ZIP dosyasını aç → `vault/` klasörü. Obsidian'da "Open folder as vault" ile aç.

**S: GitHub Actions CI başarısız oluyor?**

Repository secrets'ları kontrol et. `.github/SECRETS.md` dosyasındaki listeye bak.

---

## 🤝 Katkı Rehberi

### Branch Stratejisi

```
main          ← Production (korumalı, PR gerektirir)
develop       ← Geliştirme ana dalı
feature/xyz   ← Yeni özellik
fix/xyz       ← Hata düzeltme
hotfix/xyz    ← Acil production düzeltmesi
```

### Commit Mesajı Formatı (Conventional Commits)

```
feat: yeni NoSQL agent eklendi
fix: Telegram 4096 karakter limiti düzeltildi
docs: README güncellendi
chore: requirements.txt güncellendi
ci: GitHub Actions pipeline iyileştirildi
security: XSS açığı kapatıldı
```

### PR Süreci

1. `develop`'tan branch aç
2. Değişikliklerini yap
3. `develop`'a PR aç
4. CI geçmeli (lint + test + security)
5. Review sonrası merge

### Yeni Issue Açma

Bug raporu veya özellik isteği için GitHub Issues kullan. Template'leri doldur.

---

## 📊 Proje Metrikleri

| Metrik | Değer |
|--------|-------|
| Toplam ajan sayısı | 17 |
| Toplam görev sayısı | 14 |
| Desteklenen LLM provider | 4 |
| Desteklenen programlama dili (E2B) | Python, JavaScript, Bash |
| Obsidian vault dosya türü | agents, conversations, decisions, tasks |
| CI/CD pipeline sayısı | 4 |
| Python bağımlılık sayısı | 16 |

---

## 📜 Lisans

MIT License — Detaylar için [LICENSE](LICENSE) dosyasına bak.

---

## 🙏 Teşekkürler

- [CrewAI](https://crewai.com) — Multi-agent framework
- [EvrenLLM](https://evren-llmapi.ssyz.org.tr) — Ücretsiz Türkiye LLM altyapısı
- [E2B](https://e2b.dev) — Güvenli kod sandbox
- [python-telegram-bot](https://python-telegram-bot.org) — Telegram entegrasyonu
- [Obsidian](https://obsidian.md) — Knowledge base görselleştirme

---

<div align="center">

**⭐ Bu projeyi faydalı bulduysan star'lamayı unutma!**

[🐛 Bug Bildir](../../issues/new?template=bug_report.md) · [💡 Özellik İste](../../issues/new?template=feature_request.md) · [💬 Tartışma](../../discussions)

</div>
