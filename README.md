<div align="center">

# 📋 Klip — AI Clipboard Manager

### *Windows gives you clipboard history. We give it a brain.*

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Tests](https://img.shields.io/badge/tests-26%2F26%20passing-brightgreen)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)
![License](https://img.shields.io/badge/license-MIT-green)
![Status](https://img.shields.io/badge/status-v1.4%20live-success)

Klip watches your clipboard, saves everything, and adds AI superpowers:
summarize an article you copied, fix code from StackOverflow, translate anything — one click away.
Every clip is auto-tagged (🔗 link / ⌨ code / text), searchable, and timestamped.

[Quick Start](#-quick-start) · [Features](#-features) · [Safety](#-safety) · [Roadmap](#-roadmap)

</div>

---

## ✨ Features (v1.4)

- [x] 📋 Clipboard history — every copy auto-saved (duplicates merged), live list refresh
- [x] 🏷 Auto-tagging — clips detected as **link 🔗** / **code ⌨** / text automatically
- [x] 🔍 Search — find anything you copied (Ctrl+F)
- [x] ⏱ Age column — see how old every clip is (2m / 3h / 5d)
- [x] 🤖 AI actions — Summarize / Translate (25 languages) / Explain / Fix Code (Groq)
- [x] 🔌 **AI Connect dialog — paste your API key in the app, no .env editing needed**
- [x] 📦 **Standalone EXE — download, run, done (no Python required)**
- [x] 📌 Pin clips — keep important clips at the top, safe from history limits
- [x] 🗑 Delete single clips — clean up without wiping everything
- [x] ⌨️ Shortcuts — Ctrl+B panel, Ctrl+F search, Ctrl+P pin, Ctrl+C copy, Del delete, Esc reset
- [x] 🖱 Double-click a clip = copy it back instantly
- [x] 💾 Save AI result to a .txt file / 📦 Export full history as JSON backup
- [x] 🪟 GUI panel — dark-mode window with history list + AI buttons
- [x] 🎯 System tray — close to tray, right-click menu (Open / Pause / Settings / Exit)
- [x] ⚙️ Settings — toggle AI actions, translate language, history limit, clear data, start with Windows
- [x] 🛡️ Safety guard — warns before sending passwords/keys to AI

## 🚀 Quick Start

### Option A — Download the EXE (no Python needed)

1. Grab `Klip-v1.4-windows.zip` from [Releases](https://github.com/OfficialTanishSharma/Klip/releases/latest)
2. Unzip anywhere → run `Klip.exe`
3. On first launch, Klip asks for a free Groq API key — paste it in the **Connect AI** dialog (get one at [console.groq.com/keys](https://console.groq.com/keys)) and you're done. No files to edit.

### Option B — Run from source

```bash
git clone https://github.com/OfficialTanishSharma/Klip.git
cd Klip
pip install -r requirements.txt

# GUI app (recommended)
python src/klip_panel.py
# or just double-click Klip.bat

# CLI history engine (dev mode)
python src/klip_history.py

# Run tests
python src/test_klip.py
```

### Setup (AI actions — source install only)

The EXE build asks for the key in-app on first launch. Running from source? Either
paste the key in the app (**Settings → 🔑 Connect AI**) or:

1. Get a **free** API key at [console.groq.com/keys](https://console.groq.com/keys)
2. Create `klip_data/.env` with one line:

```
GROQ_API_KEY=your_key_here
```

⚠️ Never share your API keys. `klip_data/` is gitignored — your key stays local.

## 🖼 Demo

*GIF coming soon — copy → panel → search → Summarize.*

## 🗂 Project Structure

```
Klip/
├── src/
│   ├── app_paths.py       # Source/EXE path resolution (klip_data location)
│   ├── klip_history.py    # Clipboard listener + SQLite storage (the engine)
│   ├── klip_ai.py         # AI actions via Groq + sensitive-content guard
│   ├── klip_panel.py      # Dark-theme GUI panel (Tkinter) + AI Connect dialog
│   ├── klip_settings.py   # Settings load/save (JSON)
│   ├── test_klip.py       # Unit tests (26)
│   ├── test_gui.py        # GUI smoke test
│   ├── test_ai.py         # Live AI call test
│   └── preflight.py       # "safe to run" environment check
├── klip_data/             # Your local data (.env, history DB) — gitignored
├── Klip.bat               # Double-click launcher (source)
├── Klip.spec              # PyInstaller build spec (EXE)
├── SECURITY.md            # Security policy + safety model
├── PROJECT_BRIEF.md       # Full project brief (for AI assistants)
├── LICENSE                # MIT
└── requirements.txt
```

## 🛡 Safety

- 🔒 **Local-first** — history is stored in a local SQLite database on your machine. Nothing is uploaded automatically.
- 🛡️ **Sensitive-content guard** — before an AI action runs, Klip scans the clip for passwords, API keys, tokens, private keys, and card-like numbers. If one is found, you get a warning and **nothing is sent** unless you confirm.
- 🤖 **AI calls only on your click** — Klip never contacts any server by itself. The only network call happens when *you* press an AI action button.
- 🚫 **No telemetry, no accounts, no tracking.**
- ⏸️ **You control listening** — pause/resume from the tray menu anytime.

Full security model: [SECURITY.md](SECURITY.md)

## 📜 Version History

| Version | What shipped |
|---------|-------------|
| **v1.0** | Clipboard history + AI actions + GUI panel |
| **v1.1** | Pin clips, system tray, settings window, sensitive-content guard |
| **v1.2** | Auto-tagging (link/code/text), age column, double-click copy, Esc shortcut, save AI result, JSON export |
| **v1.3** | Project structure cleanup, `app_paths.py` for source/EXE parity |
| **v1.4** | **Standalone EXE**, AI Connect dialog (in-app API key setup), live translate-language switch, single-instance guard, selection/deselect fixes |

## 🛣 Roadmap

- [x] ~~**v1.3** — standalone EXE (PyInstaller) — no Python needed~~ ✅ v1.4
- [ ] **v2.0** — image & file clipboard support + global hotkey
- [ ] Multi-monitor-friendly popup near cursor
- [ ] More AI providers (user's choice)

## 🤝 Contributing

Found a bug or want a feature? Open an issue — feedback is welcome.
PRs are open too: fork → branch → commit → PR. Keep it simple.

## ⭐ Give it a star

If Klip saves you time, drop a ⭐ — it helps more people find it.

---

<div align="center">

Built by [RolBol](https://github.com/OfficialTanishSharma) — also building [Zevion](https://github.com/OfficialTanishSharma/Zevion), a safety-first AI desktop agent.

</div>
