# Klip — Complete Project Brief (for GitHub Copilot / AI)

You are helping with **Klip**, an AI clipboard manager for Windows. Use this brief to understand the entire project. Do not remove, rewrite, or break existing functionality.

---

## 1. What is Klip?

Klip is a **clipboard manager with a brain**. It silently watches the Windows clipboard, saves every copy into a searchable local history, and adds AI superpowers on top:

- **History** — every copy auto-saved to SQLite, duplicates merged, live list refresh
- **Auto-tagging** — clips are detected as `link` (URL), `code` (code keywords), or `text` via regex
- **AI actions** — Summarize / Translate (25 languages) / Explain / Fix Code, powered by Groq
- **Pin & search** — keep important clips on top, find anything instantly
- **Export** — full history as JSON backup; save AI results to `.txt`
- **Safety guard** — clips that look like passwords/keys are never sent to AI without confirmation

It has a **local-first, safety-first** architecture: no telemetry, no background networking, AI calls only on user click.

---

## 2. Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.10+ |
| GUI | Tkinter (dark theme, DPI-aware) |
| Clipboard | pyperclip |
| Storage | SQLite (`klip_data/klip_history.db`), `threading.Lock` + `check_same_thread=False` |
| Tray | pystray + Pillow |
| AI | Groq API via `urllib` (no SDK), model chain with fallback |
| Config | `klip_data/settings.json` + `klip_data/.env` (API key) |

---

## 3. Architecture

```
ClipboardListener (thread, 0.5s poll)
        │  new clip
        ▼
KlipHistory (SQLite)  ──add()──►  auto-tag (link/code/text)
        │
        ▼ on_change callback
KlipPanel (Tkinter GUI, main thread)
        │  user clicks AI button
        ▼
klip_ai (Groq call)  ──answer──►  queue.Queue  ──_poll_ai_results()──►  GUI
```

Key design decisions:
- Clipboard polling runs in a **daemon thread**; all DB access goes through `threading.Lock`
- AI calls run in a **worker thread**; results come back via `queue.Queue` polled every 200ms (thread-safe GUI updates)
- Clips longer than 100,000 chars are **skipped** (tagged, not saved) to protect the DB and the AI prompt
- Clips longer than 12,000 chars are **head+tail truncated** before building the AI prompt
- Sensitive-content check runs **before** any AI request leaves the machine

---

## 4. Files

| File | Role |
|---|---|
| `src/klip_history.py` | Clipboard listener thread + SQLite storage + auto-tagging + export |
| `src/klip_ai.py` | AI actions (Groq), prompt templates, sensitive-content guard, .env loader |
| `src/klip_panel.py` | Dark-theme GUI panel: list, search, AI buttons, settings window |
| `src/klip_settings.py` | Settings load/save (JSON) with defaults |
| `src/test_klip.py` | Unit tests (26) — history, guard, settings, pin, tags, export |
| `src/test_gui.py` | GUI smoke test — boots panel, exercises actions, auto-closes |
| `src/test_ai.py` | Live AI call test (needs API key) |
| `src/preflight.py` | Environment check before running the app |
| `Klip.bat` | Double-click launcher for the GUI |
| `klip_data/` | Local data: `.env`, `klip.db`, `settings.json` — **gitignored** |

---

## 5. Safety rules (do not break)

1. **Never** send clipboard data anywhere automatically. Network = user click only.
2. **Never** remove or weaken `is_sensitive()` — it runs before every AI call.
3. **Never** write the API key anywhere except `klip_data/.env` (gitignored).
4. Keep all storage inside `klip_data/` — no scattered files.
5. No telemetry, no accounts, no analytics.

---

## 6. Version history

- **v1.0** — clipboard history + AI actions + GUI panel
- **v1.1** — pin clips, system tray, settings window, sensitive-content guard
- **v1.2** — auto-tagging (link/code/text), age column, double-click copy, Esc shortcut, save AI result, JSON export
- **v1.3 (planned)** — standalone EXE (PyInstaller)
- **v2.0 (planned)** — image & file clipboard support, global hotkey

---

## 7. Coding conventions

- Comments and console messages in **English**
- Dark theme colors come from the `THEME` dict in `klip_panel.py` — don't hardcode colors
- Every DB operation must be lock-wrapped (`self._lock`)
- New features need a test in `test_klip.py`
