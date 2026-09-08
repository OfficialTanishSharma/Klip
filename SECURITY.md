# 🔒 Security Policy — Klip

## Reporting a Vulnerability

If you discover a security vulnerability in Klip, please **do not open a public issue**.

Open a draft security advisory instead (GitHub repo → Security → Advisories → New draft advisory), or contact the maintainer directly.

We aim to respond quickly and publish a fix before public disclosure.

---

## Security Model

Klip is a local clipboard manager. Its design principle is **local-first, zero background networking** — the app should never phone home, and data should never leave the machine unless the user explicitly sends it.

### 1. Local-first storage
All clipboard history lives in a local SQLite database inside `klip_data/` on your machine. Nothing is uploaded automatically — ever.

### 2. AI calls only on explicit click
The **only** network call Klip makes happens when *you* press an AI action button (Summarize / Translate / Explain / Fix Code). Klip never contacts any server by itself, on startup, in the background, or while listening to the clipboard.

### 3. Sensitive-content guard
Before any AI action runs, Klip scans the selected clip for:
- API keys (`gsk_…`, `sk-…`, AWS `AKIA…`, GitHub `ghp_…` tokens)
- Private key blocks (`-----BEGIN … PRIVATE KEY-----`)
- Password lines (`password: …`)
- Credit-card-like 16-digit numbers

If a pattern is found, a warning dialog appears and **nothing is sent to the AI unless you confirm**.

### 4. Secrets stay out of git
`klip_data/` (which holds `.env` with your API key and the history database) is gitignored. There is no code path that writes your key anywhere else.

### 5. No telemetry
No accounts, no analytics, no tracking, no crash reporters. Klip does not know you exist — that's the point.

---

## Data handling summary

| Data | Where it lives | Where it goes |
|---|---|---|
| Clipboard history | Local SQLite (`klip_data/`) | Nowhere — stays on disk |
| API key | Local `.env` (`klip_data/.env`) | Only to the AI provider you configured, on your click |
| Clip sent to AI | — | Only that clip's text, only the selected one |
