"""Smoke test: boot the full GUI for 6 seconds without interaction,
then auto-close. Catches widget-construction / tray / thread crashes
that unit tests miss. Exits 0 on success."""
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import klip_panel

result = {"ok": False, "error": None}


def run():
    try:
        panel = klip_panel.KlipPanel()
        # Simulate the user pressing an AI button with nothing selected
        panel.run_ai_action("Summarize")
        # Simulate pin/del with nothing selected (should not crash)
        panel.toggle_pin()
        panel.delete_selected_confirm = True
        # Simulate an AI result arriving through the queue (label, answer)
        panel.ai_queue.put(("Summarize", "test answer **bold**"))
        panel._poll_ai_results()
        # Simulate Save-to-file with empty result guard (filedialog must NOT open)
        panel.set_result("")
        panel.save_result()
        # Escape handler + ago_text helper + export (no crash on any input)
        panel._on_escape(None)
        klip_panel.ago_text(panel.history.search("")[:1][0][4] if panel.history.search("") else 0)
        export_path = Path(__file__).parent.parent / "klip_data" / "_smoke_export.json"
        panel.history.export_all(export_path)
        export_path.unlink(missing_ok=True)
        # Schedule auto-close, then start the mainloop
        panel.root.after(6000, lambda: (setattr(panel, "really_quit", True), panel._quit_app()))
        panel.root.mainloop()
        result["ok"] = True
    except Exception as e:
        result["error"] = repr(e)


t = threading.Thread(target=run, daemon=True)
t.start()
t.join(timeout=20)

if result["ok"]:
    print("SMOKE TEST PASS — GUI booted, no-crash actions OK, clean exit")
    sys.exit(0)
else:
    print(f"SMOKE TEST FAIL — {result['error']}")
    sys.exit(1)
