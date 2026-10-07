# GitHub Secrets Kurulum Rehberi

Repo → Settings → Secrets and variables → Actions → New repository secret

## Zorunlu Secrets

| Secret Adı | Değer | Nereden Alınır |
|-----------|-------|----------------|
| `DOCKER_USERNAME` | Docker Hub kullanıcı adı | hub.docker.com |
| `DOCKER_PASSWORD` | Docker Hub Access Token | Hub → Account Settings → Security → PAT |
| `TELEGRAM_BOT_TOKEN` | Bot token | @BotFather → /newbot |
| `TELEGRAM_CHAT_ID` | Chat ID | @userinfobot |

## Deploy Secrets (Sunucu varsa)

| Secret Adı | Değer |
|-----------|-------|
| `DEPLOY_HOST` | Sunucu IP veya hostname |
| `DEPLOY_USER` | SSH kullanıcı adı (örn: `ubuntu`) |
| `DEPLOY_SSH_KEY` | SSH private key (PEM formatı, `-----BEGIN...-----END` dahil) |

## SSH Key Oluşturma

```bash
# Sunucuda:
ssh-keygen -t ed25519 -C "github-actions" -f ~/.ssh/github_deploy
cat ~/.ssh/github_deploy.pub >> ~/.ssh/authorized_keys

# GitHub Secret'a ekle:
cat ~/.ssh/github_deploy   # Bu çıktıyı DEPLOY_SSH_KEY secret'ına yapıştır
```

## Pipeline Akışı

```
Push to branch
    │
    ▼
CI (ci.yml)
  ├── lint (ruff + black + isort)
  ├── type-check (mypy)
  ├── test (pytest + coverage)
  └── security (bandit + pip-audit)
    │
    ▼ (main branch veya tag)
CD (cd.yml)
  ├── Docker build & push
  ├── Trivy image scan
  ├── Deploy → Staging
  └── Deploy → Production (sadece v* tag)
    │
    ▼ (v* tag)
Release (release.yml)
  ├── Changelog oluştur (git-cliff)
  └── GitHub Release yayınla
```

## GitHub Environments Ayarı

Production ortamı için manuel onay kuralı:
Repo → Settings → Environments → production → Required reviewers → Kendinizi ekle

Bu sayede production deploy'dan önce GitHub'dan onay istenir.
