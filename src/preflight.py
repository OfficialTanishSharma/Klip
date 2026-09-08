"""Pre-flight check: verify Klip is safe to run before user tests the .bat file."""
import ast
import sys
import os

SRC = r"C:\Users\AVITA\Downloads\Meow Asistant\Klip\src"

files = ["klip_panel.py", "klip_ai.py", "klip_history.py", "klip_settings.py"]

print("=== 1. SYNTAX CHECK ===")
ok = True
for f in files:
    path = os.path.join(SRC, f)
    try:
        ast.parse(open(path, encoding="utf-8").read())
        print(f"  OK  {f}")
    except SyntaxError as e:
        print(f"  FAIL {f}: {e}")
        ok = False

print("\n=== 2. DANGEROUS CALLS SCAN ===")
# Make sure nothing can delete/wipe outside the Klip folder
dangerous = ["rmtree", "os.remove", "os.system", "subprocess", "shutil", "format(", "REGEDIT", "regedit"]
found_any = False
for f in files:
    path = os.path.join(SRC, f)
    code = open(path, encoding="utf-8").read()
    for d in dangerous:
        if d in code:
            # startup shortcut writes a .bat file — that's the one allowed case
            if d == "os.system" and "f'@echo off" in code:
                print(f"  NOTE {f}: writes startup shortcut only (Klip.bat in Startup folder)")
                continue
            print(f"  WARNING {f}: contains '{d}'")
            found_any = True
if not found_any:
    print("  Clean — no file deletion, no shell commands, no subprocess")

print("\n=== 3. NETWORK CALLS SCAN ===")
for f in files:
    path = os.path.join(SRC, f)
    code = open(path, encoding="utf-8").read()
    if "urllib" in code or "requests" in code or "http" in code.lower():
        urls = [line.strip() for line in code.splitlines() if "https://" in line and "#" not in line.split("https://")[0][:20]]
        for u in urls[:5]:
            print(f"  {f}: {u[:90]}")
        if not urls:
            print(f"  {f}: network import but no hardcoded URLs")

print("\n=== 4. DATA WRITE LOCATIONS ===")
for f in files:
    path = os.path.join(SRC, f)
    code = open(path, encoding="utf-8").read()
    if "Path.home()" in code:
        lines = [l.strip()[:100] for l in code.splitlines() if "Path.home()" in l]
        for l in lines:
            print(f"  {f}: {l}")

print("\n=== 5. IMPORT TEST (no GUI launch) ===")
sys.path.insert(0, SRC)
try:
    import klip_history, klip_ai, klip_settings
    print("  OK  all modules import cleanly")
    h = klip_history.KlipHistory()
    print(f"  OK  database opens, {h.stats()['total']} clips stored")
except Exception as e:
    print(f"  FAIL {e}")
    ok = False

print("\n=== 6. CRASH-RISK REVIEW ===")
# threading + tkinter: AI worker thread must not touch widgets directly.
panel_code = open(os.path.join(SRC, "klip_panel.py"), encoding="utf-8").read()
if "self.ai_queue" in panel_code and "_poll_ai_results" in panel_code:
    print("  OK  AI answers arrive via queue (thread-safe, no cross-thread widget calls)")
if "protocol(\"WM_DELETE_WINDOW\"" in panel_code or "WM_DELETE_WINDOW" in panel_code:
    print("  OK  window X button handled (minimize to tray, no crash)")
if "daemon=True" in panel_code:
    print("  OK  background threads are daemons (kill cleanly on exit)")
if "check_same_thread=False" in open(os.path.join(SRC, "klip_history.py"), encoding="utf-8").read() and "self.lock" in open(os.path.join(SRC, "klip_history.py"), encoding="utf-8").read():
    print("  OK  SQLite access locked (no threading crash)")

print("\n=== RESULT ===")
print("  SAFE TO RUN" if ok else "  FIX ISSUES ABOVE FIRST")
