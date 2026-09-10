"""
Klip — main GUI app
Features:
  - History panel with live search + AI action buttons
  - Pin / delete individual clips, keyboard shortcuts
  - System tray icon (close window = minimize to tray, right-click menu)
  - Settings window (AI action toggles, translate language, history limit,
    clear data, hotkey hints, startup)
"""

import ctypes
import sys
import threading
import queue
import time
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# ---- Single-instance guard ----
# A second Klip copies can't see the first one's window (tray-minimized) and
# two clipboard listeners fight each other — the AI queue deadlocks and the
# panel freezes on "Working...". Windows named mutex makes that impossible:
# the second launch just exits silently.
try:
    _mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "Klip_SingleInstance_Mutex")
    _ALREADY_RUNNING = (ctypes.windll.kernel32.GetLastError() == 183)  # ERROR_ALREADY_EXISTS
except Exception:
    _ALREADY_RUNNING = False

if _ALREADY_RUNNING and not getattr(sys, "_klip_child_ok", False):
    # Show the existing window is hard without IPC; a plain message is fine:
    try:
        import tkinter as _tk
        _r = _tk.Tk(); _r.withdraw()
        from tkinter import messagebox as _mb
        _mb.showinfo("Klip", "Klip is already running.\n\nLook for the 📋 icon in your system tray (bottom-right, near the clock) — right-click it → Open panel.")
        _r.destroy()
    except Exception:
        pass
    sys.exit(0)


from klip_history import KlipHistory, ClipboardListener
from klip_ai import ask_ai, is_sensitive, LANGUAGES, has_api_key, save_api_key
from klip_settings import load_settings, save_settings
from app_paths import app_root

try:
    import pystray
    from PIL import Image, ImageDraw
    HAS_TRAY = True
except ImportError:
    HAS_TRAY = False


def make_tray_image(color="#7c6ff0"):
    """Simple 'K' badge icon drawn in code — no image file needed."""
    img = Image.new("RGB", (64, 64), color)
    draw = ImageDraw.Draw(img)
    draw.rectangle([6, 6, 58, 58], outline="white", width=4)
    try:
        from PIL import ImageFont
        font = ImageFont.truetype("seguisb.ttf", 32)  # Segoe UI Semibold
    except Exception:
        font = None
    draw.text((32, 30), "K", fill="white", anchor="mm", font=font)
    return img


AI_ACTIONS = ["Summarize", "Translate", "Explain", "Fix Code"]

# Relative timestamps for the list ("2m ago") — refreshed on every rebuild
AGO_UNITS = [
    (86400, "d"), (3600, "h"), (60, "m"), (0, "s"),
]


def ago_text(ts: float) -> str:
    """Unix timestamp -> short human age like '5m' or '3h'."""
    diff = max(0, int(time.time() - ts))
    for seconds, unit in AGO_UNITS:
        if diff >= seconds and seconds:
            return f"{diff // seconds}{unit}"
        if seconds == 0:
            return f"{diff}s"
    return "?"

# ---- Theme (Catppuccin-inspired dark palette) ----
THEME = {
    "bg":       "#181825",   # window background
    "card":     "#24243a",   # list / boxes
    "card_alt": "#2f2f4a",   # hover / secondary buttons
    "fg":       "#e0e0f0",   # main text
    "muted":    "#8888a0",   # secondary text
    "accent":   "#7c6ff0",   # purple
    "accent2":  "#89b4fa",   # blue highlight
    "danger":   "#8a3a4a",   # delete
    "green":    "#a6e3a1",   # success
}


class ApiKeyWindow:
    """First-run dialog: asks for the Groq API key when none is configured.

    Saves straight into klip_data/.env via save_api_key() — the user never
    opens the .env file by hand. Key stays local, nothing is sent anywhere
    except the AI call itself.
    """

    def __init__(self, app):
        self.app = app
        self.win = tk.Toplevel(app.root)
        self.win.title("Klip — Connect AI")
        self.win.geometry("460x430")
        self.win.configure(bg=THEME["bg"])
        self.win.resizable(False, False)
        self.win.grab_set()  # modal — panel blocked until key is handled
        self.win.protocol("WM_DELETE_WINDOW", self._skip)
        self.win.after(150, lambda: self.win.lift() or self.key_entry.focus_set()
                       if hasattr(self, "key_entry") else None)
        self._build()

    def _build(self):
        dark, card, fg, accent = THEME["bg"], THEME["card"], THEME["fg"], THEME["accent"]
        muted, green = THEME["muted"], THEME["green"]

        tk.Label(self.win, text="🔌 Connect your AI", font=("Segoe UI", 15, "bold"),
                 bg=dark, fg=accent).pack(anchor="w", padx=18, pady=(18, 2))
        tk.Label(self.win, text="Klip needs a FREE Groq API key to power its\n"
                                "AI actions (Summarize / Translate / Explain / Fix).",
                 bg=dark, fg=fg, justify="left").pack(anchor="w", padx=18, pady=(0, 10))

        steps = tk.LabelFrame(self.win, text=" How to get it (2 min, no card) ",
                              bg=dark, fg=muted, bd=0, font=("Segoe UI", 9, "bold"))
        steps.pack(fill="x", padx=18, pady=4)
        for text in ("1. Open  console.groq.com/keys  in your browser",
                     "2. Sign up / log in (free)",
                     "3. Create API Key → copy it",
                     "4. Paste it below 👇"):
            tk.Label(steps, text=text, bg=dark, fg=fg, anchor="w",
                     justify="left").pack(anchor="w", padx=10, pady=2)

        tk.Label(self.win, text="Paste your key here:", bg=dark, fg=fg
                 ).pack(anchor="w", padx=18, pady=(12, 3))
        holder = tk.Frame(self.win, bg=accent, padx=1, pady=1)
        holder.pack(fill="x", padx=18)
        self.key_entry = tk.Entry(holder, show="•", bg=card, fg=fg,
                                  insertbackground=fg, relief="flat",
                                  font=("Segoe UI", 10))
        self.key_entry.pack(fill="x", ipady=7, padx=1, pady=1)

        self.msg_label = tk.Label(self.win, text="", bg=dark, fg=green,
                                  font=("Segoe UI", 9), wraplength=410,
                                  justify="left")
        self.msg_label.pack(anchor="w", padx=18, pady=(4, 0))

        btns = tk.Frame(self.win, bg=dark)
        btns.pack(fill="x", padx=18, pady=(10, 16))

        tk.Button(btns, text="✅ Connect", command=self._connect,
                  bg=accent, fg="white", activebackground=THEME["accent2"],
                  relief="flat", padx=16, pady=7, cursor="hand2",
                  font=("Segoe UI", 10, "bold")).pack(side="left")
        tk.Button(btns, text="Skip for now", command=self._skip,
                  bg=THEME["card_alt"], fg=muted, relief="flat",
                  padx=12, pady=7, cursor="hand2",
                  font=("Segoe UI", 9)).pack(side="right")

        tk.Label(self.win, text="🔒 Key stays in klip_data/.env on your PC — "
                                "never uploaded, never shared.",
                 bg=dark, fg=muted, font=("Segoe UI", 8),
                 wraplength=410, justify="left").pack(anchor="w", padx=18, pady=(0, 12))

        self.key_entry.bind("<Return>", lambda e: self._connect())

    def _connect(self):
        key = self.key_entry.get().strip()
        if not key:
            self.msg_label.config(text="Paste the key first 🙂", fg=THEME["danger"])
            return
        if save_api_key(key):
            self.win.grab_release()
            self.win.destroy()
            self.app.set_status("AI connected — key saved to klip_data/.env ✅")
            self.app.notify_ai_connected()
        else:
            self.msg_label.config(text="Key was empty — try again.", fg=THEME["danger"])

    def _skip(self):
        self.win.grab_release()
        self.win.destroy()
        self.app.settings["ai_setup_skipped"] = True
        save_settings(self.app.settings)
        self.app.set_status("Skipped AI setup — set a key anytime in Settings.")


class SettingsWindow:
    """Separate small window for user preferences."""

    def __init__(self, app):
        self.app = app
        self.win = tk.Toplevel(app.root)
        self.win.title("Klip — Settings")
        self.win.geometry("460x540")
        self.win.configure(bg=THEME["bg"])
        self.win.resizable(False, False)
        self._build()

    def _build(self):
        s = self.app.settings
        dark, card, fg, accent = THEME["bg"], THEME["card"], THEME["fg"], THEME["accent"]
        muted = THEME["muted"]

        tk.Label(self.win, text="⚙️ Settings", font=("Segoe UI", 14, "bold"),
                 bg=dark, fg=accent).pack(anchor="w", padx=16, pady=(14, 8))

        # --- AI connection status + key management ---
        connected = has_api_key()
        conn_color = THEME["green"] if connected else THEME["danger"]
        conn_text = ("🟢 AI connected" if connected
                     else "🔴 AI not connected — no key found")
        tk.Label(self.win, text=conn_text, bg=dark, fg=conn_color,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=16, pady=(0, 4))
        tk.Button(self.win, text="🔑 " + ("Change / update API key" if connected
                                         else "Connect AI (free Groq key)"),
                  command=self.open_api_key_window, bg=THEME["card_alt"], fg=fg,
                  activebackground=accent, activeforeground="white",
                  relief="flat", padx=12, pady=6, cursor="hand2",
                  font=("Segoe UI", 10)).pack(anchor="w", padx=16, pady=(0, 6))

        # --- AI actions section ---
        box = tk.LabelFrame(self.win, text=" AI Actions ", bg=dark, fg=muted,
                            bd=0, font=("Segoe UI", 9, "bold"))
        box.pack(fill="x", padx=16, pady=6)
        self.action_vars = {}
        for action in AI_ACTIONS:
            var = tk.BooleanVar(value=s["ai_actions"].get(action, True))
            self.action_vars[action] = var
            tk.Checkbutton(box, text=action, variable=var, bg=dark, fg=fg,
                           activebackground=dark, activeforeground=accent,
                           selectcolor=card).pack(anchor="w", padx=10, pady=2)

        # --- Translate language dropdown ---
        lang_row = tk.Frame(box, bg=dark)
        lang_row.pack(anchor="w", padx=10, pady=(2, 6))
        tk.Label(lang_row, text="Translate language:", bg=dark, fg=fg
                 ).pack(side="left")
        self.lang_var = tk.StringVar(
            value=s.get("translate_language", "Hindi"))
        tk.OptionMenu(lang_row, self.lang_var, *LANGUAGES).pack(
            side="left", padx=6)
        # Live-apply: picking a language saves it instantly (same as the
        # Pause checkbox) — no Save click needed for Translate to use it
        self.lang_var.trace_add("write", self._apply_language)

        # --- History section ---
        box2 = tk.LabelFrame(self.win, text=" History ", bg=dark, fg=muted,
                             bd=0, font=("Segoe UI", 9, "bold"))
        box2.pack(fill="x", padx=16, pady=6)

        row = tk.Frame(box2, bg=dark)
        row.pack(anchor="w", padx=10, pady=4)
        tk.Label(row, text="Keep last", bg=dark, fg=fg).pack(side="left")
        self.limit_var = tk.StringVar(value=str(s["history_limit"]))
        tk.OptionMenu(row, self.limit_var, "100", "300", "500", "1000", "0"
                      ).pack(side="left", padx=6)
        tk.Label(row, text="clips (0 = unlimited)", bg=dark, fg=fg).pack(side="left")

        tk.Button(box2, text="🗑 Clear ALL history", command=self.clear_all,
                  bg="#4a2430", fg=THEME["fg"], activebackground=THEME["danger"],
                  activeforeground="white",
                  relief="flat", padx=10, pady=5, cursor="hand2"
                  ).pack(anchor="w", padx=10, pady=(4, 8))

        # --- Behaviour section ---
        box3 = tk.LabelFrame(self.win, text=" Behaviour ", bg=dark, fg=muted,
                             bd=0, font=("Segoe UI", 9, "bold"))
        box3.pack(fill="x", padx=16, pady=6)

        self.pause_var = tk.BooleanVar(value=s["pause_listening"])
        tk.Checkbutton(box3, text="Pause clipboard listening",
                       variable=self.pause_var, bg=dark, fg=fg,
                       activebackground=dark, activeforeground=accent,
                       selectcolor=card, command=self.apply_pause
                       ).pack(anchor="w", padx=10, pady=2)

        self.startup_var = tk.BooleanVar(value=s["start_with_windows"])
        tk.Checkbutton(box3, text="Start with Windows",
                       variable=self.startup_var, bg=dark, fg=fg,
                       activebackground=dark, activeforeground=accent,
                       selectcolor=card).pack(anchor="w", padx=10, pady=2)

        self.hotkey_var = tk.BooleanVar(value=s.get("show_hotkeys", True))
        tk.Checkbutton(box3, text="Show hotkey hints (Ctrl+B, Ctrl+F, Ctrl+P, Del)",
                       variable=self.hotkey_var, bg=dark, fg=fg,
                       activebackground=dark, activeforeground=accent,
                       selectcolor=card).pack(anchor="w", padx=10, pady=2)

        # --- Save button ---
        tk.Button(self.win, text="💾  Save settings", command=self.save,
                  bg=accent, fg="white", activebackground=THEME["accent2"],
                  relief="flat", padx=20, pady=7, cursor="hand2",
                  font=("Segoe UI", 10, "bold")
                  ).pack(pady=(10, 2))

        # --- Export button ---
        tk.Button(self.win, text="📦  Export history (JSON backup)",
                  command=self.export_history,
                  bg=THEME["card_alt"], fg=THEME["fg"],
                  activebackground=THEME["accent"],
                  relief="flat", padx=14, pady=5, cursor="hand2",
                  ).pack(pady=(2, 12))

    def export_history(self):
        """Dump full history to a JSON file the user picks."""
        path = filedialog.asksaveasfilename(
            title="Export Klip history",
            defaultextension=".json",
            initialfile="klip_backup.json",
            filetypes=[("JSON", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            count = self.app.history.export_all(Path(path))
            messagebox.showinfo("Klip", f"Exported {count} clips to:\n{path}")
        except OSError as e:
            messagebox.showerror("Klip", f"Export failed: {e}")

    def apply_pause(self):
        """Pause toggle applies immediately (don't wait for Save)."""
        self.app.listener.paused = self.pause_var.get()
        state = "paused" if self.pause_var.get() else "listening"
        self.app.set_status(f"Clipboard {state}.")

    def _apply_language(self, *_):
        """Translate language applies instantly — saved + used by next request."""
        lang = self.lang_var.get()
        self.app.settings["translate_language"] = lang
        save_settings(self.app.settings)

    def clear_all(self):
        if messagebox.askyesno("Klip", "Delete ALL saved clips? This cannot be undone."):
            self.app.history.clear_all()
            self.app.refresh_list()
            self.app.set_status("History cleared.")

    def open_api_key_window(self):
        self.win.destroy()
        self.app.settings["ai_setup_skipped"] = False
        save_settings(self.app.settings)
        ApiKeyWindow(self.app)

    def save(self):
        s = self.app.settings
        s["ai_actions"] = {a: v.get() for a, v in self.action_vars.items()}
        s["history_limit"] = int(self.limit_var.get())
        s["pause_listening"] = self.pause_var.get()
        s["start_with_windows"] = self.startup_var.get()
        s["translate_language"] = self.lang_var.get()
        s["show_hotkeys"] = self.hotkey_var.get()
        save_settings(s)
        self.app.history.enforce_limit(s["history_limit"])
        self.app.apply_action_visibility()
        self.app.refresh_list()
        self.app.set_startup(s["start_with_windows"])
        messagebox.showinfo("Klip", "Settings saved.")
        self.win.destroy()


class KlipPanel:
    """Main application window + tray."""

    def __init__(self):
        self.settings = load_settings()
        self.history = KlipHistory()
        self.history.enforce_limit(self.settings["history_limit"])
        self.listener = ClipboardListener(self.history)
        self.listener.paused = self.settings["pause_listening"]
        self.listener.start()

        self.ai_queue = queue.Queue()
        self.selected_id = None
        self.tray_icon = None
        self.really_quit = False
        self._ai_busy = False

        self.root = tk.Tk()
        self.root.title("Klip — AI Clipboard Manager")
        self.root.geometry("820x600")
        self.root.minsize(680, 500)
        self.root.configure(bg=THEME["bg"])
        # Sharper text on high-DPI displays (Windows scaling)
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
        self.root.option_add("*Font", ("Segoe UI", 10))
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self._build_ui()
        self._poll_ai_results()
        self.refresh_list()
        self._bind_hotkeys()

        # Any new copy (panel open or closed, selected or not) refreshes the list
        self.listener.on_change = self._on_clipboard_change

        if HAS_TRAY:
            self._start_tray()

        # First-run AI setup: no key configured -> offer the connect dialog
        self.root.after(400, self._maybe_show_api_setup)

    def _maybe_show_api_setup(self):
        """Open the API key dialog once per session when no key is present."""
        if has_api_key():
            return
        if self.settings.get("ai_setup_skipped"):
            # User skipped before — don't nag every start; Settings has a button
            return
        ApiKeyWindow(self)

    def notify_ai_connected(self):
        """Called after a key is saved — refresh status + open settings hint."""
        self.set_status("AI connected ✅ — try Summarize on any clip!")

    def _on_clipboard_change(self, _is_new):
        """Called from the listener thread — hop back to the Tk thread."""
        self.root.after(0, self.refresh_list)

    def _bind_hotkeys(self):
        """Keyboard shortcuts inside the panel window."""
        self.root.bind("<Control-b>", lambda e: self._show_window())
        self.root.bind("<Control-f>", lambda e: self._focus_search())
        self.root.bind("<Control-p>", lambda e: self.toggle_pin())
        self.root.bind("<Delete>", lambda e: self.delete_selected())
        # Ctrl+C must keep its normal behaviour when text is selected inside
        # the search box or the result box — only copy a clip when neither
        # widget has a selection.
        self.root.bind("<Control-c>", self._on_ctrl_c)
        # Escape = clear search + deselect (quick reset)
        self.root.bind("<Escape>", self._on_escape)

    def _on_ctrl_c(self, _event):
        focused = self.root.focus_get()
        if isinstance(focused, (tk.Entry, tk.Text)):
            try:
                if focused.selection_present():
                    return  # let the widget copy its own text
            except tk.TclError:
                pass
        self.copy_selected()
        return "break"

    def _focus_search(self, *_):
        self.search_entry.focus_set()
        self.search_entry.select_range(0, "end")

    def _on_escape(self, _event):
        """Escape: clear the search box and drop the row selection."""
        if self.search_var.get():
            self.search_var.set("")
            self._search_focus_out(_event)
            self.set_status("Search cleared.")
        if self.selected_id is not None:
            self.tree.selection_remove(*self.tree.selection())
            self.selected_id = None

    def _search_focus_in(self, _event):
        """Remove the placeholder when the user clicks into the search box."""
        if self.search_var.get() == self._search_placeholder:
            self.search_var.set("")
            self.search_entry.config(fg=THEME["fg"])

    def _search_focus_out(self, _event):
        """Restore the placeholder when the search box is empty and unfocused."""
        if not self.search_var.get():
            self.search_entry.config(fg=THEME["muted"])
            # Bypass the StringVar so the write-trace doesn't filter the list,
            # and the widget shows the placeholder while the query stays empty.
            self.search_entry.delete(0, "end")
            self.search_entry.insert(0, self._search_placeholder)

    # ---------- UI construction ----------

    def _build_ui(self):
        dark = THEME["bg"]
        card = THEME["card"]
        fg = THEME["fg"]
        accent = THEME["accent"]
        muted = THEME["muted"]

        # Make the title bar dark too (Windows 10 1809+)
        try:
            hwnd = self.root.winfo_id()
            # attribute 20 = DWMWA_USE_IMMERSIVE_DARK_MODE on Win10 20H1+/Win11
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 20, ctypes.byref(ctypes.c_int(1)), ctypes.sizeof(ctypes.c_int)
            )
        except Exception:
            pass

        # Top bar: brand + search + settings
        top = tk.Frame(self.root, bg=dark)
        top.pack(fill="x", padx=14, pady=(12, 4))

        tk.Label(top, text="📋", font=("Segoe UI Emoji", 15),
                 bg=dark, fg=fg).pack(side="left", padx=(0, 4))
        tk.Label(top, text="Klip", font=("Segoe UI", 17, "bold"),
                 bg=dark, fg=accent).pack(side="left", padx=(0, 2))
        tk.Label(top, text="AI Clipboard", font=("Segoe UI", 10),
                 bg=dark, fg=muted).pack(side="left", pady=(6, 0))

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self.refresh_list())
        search_holder = tk.Frame(top, bg=THEME["accent"], padx=1, pady=1)
        search_holder.pack(side="left", padx=(12, 0))
        self.search_entry = tk.Entry(search_holder, textvariable=self.search_var,
                                     bg=card, fg=fg, insertbackground=fg,
                                     relief="flat", width=30,
                                     font=("Segoe UI", 10))
        self.search_entry.pack(ipady=6)
        # Placeholder text inside the search box
        self._search_placeholder = "Search clips…  (Ctrl+F)"
        self.search_entry.insert(0, self._search_placeholder)
        self.search_entry.config(fg=muted)
        self.search_entry.bind("<FocusIn>", self._search_focus_in)
        self.search_entry.bind("<FocusOut>", self._search_focus_out)

        self.stats_label = tk.Label(top, text="", bg=dark, fg=muted,
                                    font=("Segoe UI", 10))
        self.stats_label.pack(side="right")

        settings_btn = tk.Button(top, text="⚙️", command=self.open_settings,
                                 bg=card, fg=fg, activebackground=accent,
                                 activeforeground="white",
                                 relief="flat", padx=10, pady=4, cursor="hand2",
                                 font=("Segoe UI", 11))
        settings_btn.pack(side="right", padx=(6, 0))

        # Middle: history list
        list_frame = tk.Frame(self.root, bg=dark)
        list_frame.pack(fill="both", expand=True, padx=14, pady=5)

        columns = ("id", "preview", "copies", "when")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=10)
        self.tree.heading("id", text="#")
        self.tree.heading("preview", text="Clipboard content")
        self.tree.heading("copies", text="×")
        self.tree.heading("when", text="Age")
        self.tree.column("id", width=44, anchor="center", stretch=False)
        self.tree.column("preview", width=520, stretch=True)
        self.tree.column("copies", width=44, anchor="center", stretch=False)
        self.tree.column("when", width=56, anchor="e", stretch=False)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background=card, foreground=fg,
                        fieldbackground=card, rowheight=32, borderwidth=0,
                        font=("Segoe UI", 10))
        style.configure("Treeview.Heading", background=THEME["bg"],
                        foreground=muted, borderwidth=0,
                        font=("Segoe UI", 9, "bold"))
        style.map("Treeview",
                  background=[("selected", accent)],
                  foreground=[("selected", "white")])

        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        # Double-click a row = copy that clip straight back to the clipboard
        self.tree.bind("<Double-1>", lambda e: self.copy_selected())
        # Clicking an already-selected row deselects it (runs after Tk's own
        # selection handling); clicking empty space below rows also deselects
        self.tree.bind("<Button-1>", self._on_tree_click, add="+")
        self.tree.bind("<Button-1>", self._on_tree_press, add="+")

        # Bottom: AI action buttons + result box
        actions = tk.Frame(self.root, bg=dark)
        actions.pack(fill="x", padx=14, pady=(5, 0))

        self.action_buttons = {}
        for label in AI_ACTIONS:
            btn = tk.Button(actions, text=label, command=lambda l=label: self.run_ai_action(l),
                            bg=accent, fg="white", activebackground=THEME["accent2"],
                            activeforeground="white",
                            relief="flat", padx=14, pady=7, cursor="hand2",
                            font=("Segoe UI", 10, "bold"))
            btn.pack(side="left", padx=(0, 6))
            self.action_buttons[label] = btn

        copy_btn = tk.Button(actions, text="📋 Copy", command=self.copy_selected,
                             bg=THEME["card_alt"], fg=fg, activebackground=accent,
                             activeforeground="white",
                             relief="flat", padx=12, pady=7, cursor="hand2",
                             font=("Segoe UI", 10))
        copy_btn.pack(side="right")

        pin_btn = tk.Button(actions, text="📌 Pin", command=self.toggle_pin,
                            bg=THEME["card_alt"], fg=fg, activebackground=accent,
                            activeforeground="white",
                            relief="flat", padx=12, pady=7, cursor="hand2",
                            font=("Segoe UI", 10))
        pin_btn.pack(side="right", padx=(0, 6))

        del_btn = tk.Button(actions, text="🗑", command=self.delete_selected,
                            bg=THEME["card_alt"], fg=fg, activebackground=THEME["danger"],
                            activeforeground="white",
                            relief="flat", padx=11, pady=7, cursor="hand2",
                            font=("Segoe UI", 10))
        del_btn.pack(side="right", padx=(0, 6))

        # Result panel with its own header
        result_frame = tk.Frame(self.root, bg=dark)
        result_frame.pack(fill="x", padx=14, pady=(6, 0))

        tk.Label(result_frame, text="✨ AI RESULT", font=("Segoe UI", 9, "bold"),
                 bg=dark, fg=muted).pack(side="left")

        clear_res_btn = tk.Button(result_frame, text="Clear", font=("Segoe UI", 8),
                                  bg=dark, fg=muted, relief="flat",
                                  activebackground=dark, activeforeground=fg,
                                  cursor="hand2", bd=0,
                                  command=self.clear_result)
        clear_res_btn.pack(side="right")

        save_res_btn = tk.Button(result_frame, text="Save to file", font=("Segoe UI", 8),
                                 bg=dark, fg=muted, relief="flat",
                                 activebackground=dark, activeforeground=fg,
                                 cursor="hand2", bd=0,
                                 command=self.save_result)
        save_res_btn.pack(side="right", padx=(0, 10))

        self.result_box = tk.Text(self.root, height=8, bg=card, fg=fg,
                                  insertbackground=fg, relief="flat",
                                  wrap="word", padx=10, pady=8, spacing1=2,
                                  font=("Segoe UI", 10), state="disabled")
        self.result_box.pack(fill="both", expand=True, padx=14, pady=(4, 8))

        self.status_label = tk.Label(self.root, text="Ready.", anchor="w",
                                     bg=dark, fg=muted,
                                     font=("Segoe UI", 9))
        self.status_label.pack(fill="x", padx=16, pady=(0, 8))

        self.apply_action_visibility()

    def clear_result(self):
        self.result_box.config(state="normal")
        self.result_box.delete("1.0", "end")
        self.result_box.config(state="disabled")
        self.set_status("Result cleared.")

    def save_result(self):
        """Save the current AI result to a .txt file the user picks."""
        self.result_box.config(state="normal")
        text = self.result_box.get("1.0", "end").strip()
        self.result_box.config(state="disabled")
        if not text or text == "Working...":
            self.set_status("Nothing to save yet — run an AI action first.")
            return
        path = filedialog.asksaveasfilename(
            title="Save AI result",
            defaultextension=".txt",
            initialfile="klip_result.txt",
            filetypes=[("Text file", "*.txt"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            Path(path).write_text(text, encoding="utf-8")
            self.set_status(f"Result saved: {Path(path).name}")
        except OSError as e:
            self.set_status(f"Could not save: {e}")

    def apply_action_visibility(self):
        """Show/hide AI buttons based on settings."""
        enabled = self.settings["ai_actions"]
        for label, btn in self.action_buttons.items():
            if enabled.get(label, True):
                btn.pack(side="left", padx=(0, 6))
            else:
                btn.pack_forget()

    # ---------- Tray ----------

    def _start_tray(self):
        menu = pystray.Menu(
            pystray.MenuItem("Open panel", self._tray_open, default=True),
            pystray.MenuItem(
                "Listening",
                pystray.Menu(
                    pystray.MenuItem("Pause", self._tray_pause),
                    pystray.MenuItem("Resume", self._tray_resume),
                ),
            ),
            pystray.MenuItem("Settings", self._tray_settings),
            pystray.MenuItem("Exit", self._tray_exit),
        )
        self.tray_icon = pystray.Icon(
            "Klip", make_tray_image(), "Klip — AI Clipboard Manager", menu
        )
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def _tray_open(self, *_):
        self.root.after(0, self._show_window)

    def _tray_settings(self, *_):
        self.root.after(0, self.open_settings)

    def _tray_pause(self, *_):
        self.root.after(0, lambda: self._set_pause(True))

    def _tray_resume(self, *_):
        self.root.after(0, lambda: self._set_pause(False))

    def _set_pause(self, paused):
        self.listener.paused = paused
        self.settings["pause_listening"] = paused
        save_settings(self.settings)
        self.set_status("Clipboard paused." if paused else "Clipboard listening again.")

    def _tray_exit(self, *_):
        self.really_quit = True
        self.root.after(0, self._quit_app)

    def _show_window(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def _quit_app(self):
        if self.tray_icon:
            self.tray_icon.stop()
        self.listener.running = False
        try:
            self.root.destroy()
        except tk.TclError:
            pass  # window already gone

    def on_close(self):
        """X button = minimize to tray (app keeps running)."""
        if self.really_quit:
            self._quit_app()
            return
        self.root.withdraw()
        self.set_status("Minimized to tray — still saving copies.")

    # ---------- History list ----------

    def refresh_list(self):
        # The search placeholder insert fires the write-trace before the
        # tree exists (during _build_ui) — safe-guard until UI is built.
        if not hasattr(self, "tree"):
            return
        query = self.search_var.get()
        if query == getattr(self, "_search_placeholder", None):
            query = ""  # placeholder text must not filter the list
        rows = self.history.search(query, limit=100)

        self.tree.tag_configure("pinned", foreground=THEME["accent2"])
        self.tree.tag_configure("code", foreground=THEME["green"])
        self.tree.tag_configure("link", foreground=THEME["accent2"])
        self.tree.delete(*self.tree.get_children())
        for row in rows:
            item_id, content, kind, copies, created, pinned = row
            # Flatten newlines + trim so long clips don't break row rendering
            preview = content.replace("\r", " ").replace("\n", " ↵ ")
            preview = " ".join(preview.split())[:120]
            tag = "pinned" if pinned else ""
            if not pinned and kind in ("code", "link"):
                tag = kind
            if pinned:
                preview = "📌 " + preview
            elif kind == "link":
                preview = "🔗 " + preview
            elif kind == "code":
                preview = "⌨ " + preview
            self.tree.insert("", "end", iid=str(item_id),
                             values=(item_id, preview, f"{copies}x",
                                     ago_text(created)),
                             tags=(tag,) if tag else ("",))

        # Keep the user's selection highlight after a refresh (new copies
        # rebuild the list, but the selection must survive)
        if self.selected_id is not None:
            try:
                self.tree.selection_set(str(self.selected_id))
            except tk.TclError:
                self.selected_id = None  # clip was deleted/limited away

        stats = self.history.stats()
        state = " (paused)" if self.listener.paused else ""
        self.stats_label.config(
            text=f"{stats['total']} clips · 🔗 {stats['links']} · ⌨ {stats['code']}{state}"
        )

    def _on_select(self, _event):
        selection = self.tree.selection()
        self.selected_id = int(selection[0]) if selection else None

    def _on_tree_click(self, event):
        """Toggle selection: clicking the selected row again deselects it.

        Widget bindings fire BEFORE Tk's class binding (which selects the
        row under the cursor), so we must capture whether the row was
        already selected at press time. The actual deselect then runs one
        tick later (after_idle), after Tk has finished its own handling —
        otherwise Tk's re-select would fight us.
        """
        item = self.tree.identify_row(event.y)
        was_selected = bool(item) and item in self.tree.selection()

        def _toggle():
            if was_selected:
                self.tree.selection_remove(item)
                self.selected_id = None
                self.clear_result()
        if was_selected:
            self.tree.after_idle(_toggle)

    def _on_tree_press(self, event):
        """Press on empty space below the rows = deselect (click-to-toggle)."""
        if not self.tree.identify_row(event.y):
            self.tree.selection_remove(*self.tree.selection())
            self.selected_id = None
            self.clear_result()

    def _pinned_clip_id(self):
        """Get the full text of the selected clip (via history, not the list)."""
        if not self.selected_id:
            return None
        return self.history.get_content(self.selected_id)

    def toggle_pin(self):
        if not self.selected_id:
            self.set_status("Select a clip first, then pin it.")
            return
        try:
            tags = self.tree.item(str(self.selected_id), "tags")
        except tk.TclError:
            tags = ()
        is_pinned = "pinned" in tags
        self.history.set_pinned(self.selected_id, not is_pinned)
        self.refresh_list()
        state = "pinned — stays at top" if not is_pinned else "unpinned"
        self.set_status(f"Clip {state}.")

    def copy_selected(self):
        if not self.selected_id:
            self.set_status("Select a clip first.")
            return
        content = self.history.get_content(self.selected_id)
        if content is not None:
            import pyperclip
            pyperclip.copy(content)
            # Re-sync the listener so Klip doesn't log its own copy as a new clip
            self.listener.last_text = content
            self.set_status("Copied to clipboard.")

    def delete_selected(self):
        if not self.selected_id:
            self.set_status("Select a clip first.")
            return
        if not messagebox.askyesno("Klip", "Delete this clip?"):
            return
        self.history.delete(self.selected_id)
        self.selected_id = None
        self.clear_result()
        self.refresh_list()
        self.set_status("Clip deleted.")

    # ---------- AI actions ----------

    def run_ai_action(self, label):
        if not self.selected_id:
            self.set_status("Select a clip first, then press an AI action.")
            return

        # No API key yet -> open the connect dialog instead of failing silently
        if not has_api_key():
            self.set_status("No AI key — connect Groq first.")
            ApiKeyWindow(self)
            return

        action = label.lower().replace(" ", "_")  # "Fix Code" -> "fix_code"
        if action == "fix_code":
            action = "fix"

        content = self.history.get_content(self.selected_id)
        if not content:
            self.set_status("Could not load the selected clip.")
            return

        # One AI request at a time — double-clicks must not fire two calls
        if getattr(self, "_ai_busy", False):
            self.set_status("AI is already working — one moment.")
            return
        self._ai_busy = True
        try:
            self._start_ai_request(label, action, content)
        finally:
            pass

    def _start_ai_request(self, label, action, content):
        # Safety guard: warn before sending anything that looks like a secret
        sensitive, reason = is_sensitive(content)
        if sensitive:
            confirm = messagebox.askyesno(
                "Klip — Sensitive content warning",
                f"This clip looks like it contains a {reason}.\n\n"
                "Sending it to an AI service means it leaves your computer.\n\n"
                "Send anyway?",
            )
            if not confirm:
                self._ai_busy = False
                self.set_status("Cancelled — nothing was sent to AI.")
                return

        self.set_status(f"AI is thinking ({label})...")
        self.set_result("Working...")

        # Read the language at request time (not cached) — a language picked
        # in Settings moments ago must be used by this very request
        translate_lang = self.settings.get("translate_language", "Hindi")

        threading.Thread(
            target=self._ai_worker,
            args=(action, content, translate_lang, label),
            daemon=True,
        ).start()

    def _ai_worker(self, action, content, translate_lang, label="AI"):
        try:
            answer = ask_ai(action, content, translate_lang=translate_lang)
        except Exception as e:  # never let the worker thread die silently
            answer = f"AI request failed: {e}"
        self.ai_queue.put((label, answer))
    def _poll_ai_results(self):
        try:
            while True:
                label, answer = self.ai_queue.get_nowait()
                self.set_result(answer)
                self.set_status(f"{label} done.")
                self._ai_busy = False
        except queue.Empty:
            pass
        self.root.after(200, self._poll_ai_results)
    # ---------- Settings + startup ----------

    def open_settings(self):
        SettingsWindow(self)

    def set_startup(self, enabled):
        """Add/remove a shortcut in the user's Startup folder."""
        try:
            startup_dir = Path.home() / "AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Startup"
            link = startup_dir / "Klip.bat"
            if enabled:
                if getattr(sys, "frozen", False):
                    # EXE build: point startup directly at Klip.exe (no .bat)
                    exe_path = Path(sys.executable)
                    link = startup_dir / "Klip.exe.bat"
                    link.write_text(f'@echo off\r\nstart "" "{exe_path}"\r\n', encoding="ascii")
                else:
                    bat_path = app_root() / "Klip.bat"
                    link.write_text(f'@echo off\r\nstart "" "{bat_path}"\r\n', encoding="ascii")
            else:
                (startup_dir / "Klip.bat").unlink(missing_ok=True)
                (startup_dir / "Klip.exe.bat").unlink(missing_ok=True)
        except OSError:
            pass  # non-fatal — settings still saved

    # ---------- Helpers ----------

    def set_status(self, text):
        """Status bar text; hotkey hints appended when enabled in settings."""
        if self.settings.get("show_hotkeys", True):
            text = f"{text}   |   Ctrl+B open panel · Ctrl+F search · Ctrl+P pin · Del delete"
        self.status_label.config(text=text)

    def set_result(self, text):
        """Show AI output. Strips markdown bold/italic markers the model adds."""
        clean = text.replace("**", "").replace("*", "")
        self.result_box.config(state="normal")
        self.result_box.delete("1.0", "end")
        self.result_box.insert("1.0", clean)
        self.result_box.config(state="disabled")
        self.result_box.yview_moveto(0)  # always show the start of the answer

    def run(self):
        self.root.mainloop()
        # After mainloop ends (window closed without tray or via Exit)
        if not HAS_TRAY and not self.really_quit:
            # No tray support: closing the window should really quit
            self.listener.running = False


def main():
    panel = KlipPanel()
    panel.run()


if __name__ == "__main__":
    main()
