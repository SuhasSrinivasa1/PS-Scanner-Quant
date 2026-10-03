# Dedicated repository migration

This repository is the clean standalone PS Scanner Quant baseline, extracted from the audited PS Scanner source previously maintained under `ps-scanner/` in `SuhasSrinivasa1/Suhas-Private-AI-Trader`.

Baseline version: **6.8.2**.

The old monorepo remains a historical/remote backup. Going forward, PS Scanner development should use this dedicated repository only.

The dedicated repository intentionally excludes runtime state and unrelated projects. Do not commit:
- Groww credentials, access tokens, TOTP secrets, API secrets or broker session material;
- `data/`, SQLite ledgers/backups or runtime caches;
- `logs/`, `.runtime/`, `.venv/`, `.env`, `local.runtime.json`;
- generated signing material or machine-specific state.

The release carries forward all audited v6.7.x/v6.8.x integrity contracts and the production-validated v6.8.1 performance fix, plus the v6.8.2 bounded-health execution snapshot hardening.
