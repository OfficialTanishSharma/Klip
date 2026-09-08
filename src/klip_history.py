"""
Klip — AI Clipboard Manager
Feature 1: Clipboard listener + SQLite history
Copy anything -> it gets saved automatically, searchable later.
"""

import sqlite3
import json
import time
import threading
from pathlib import Path

import pyperclip

# Database file lives in klip_data/ next to the project root
DB_DIR = Path(__file__).parent.parent / "klip_data"
DB_DIR.mkdir(exist_ok=True)
DB_PATH = DB_DIR / "klip.db"


class KlipHistory:
    """Stores every copied item in SQLite, searchable."""

    def __init__(self):
        # check_same_thread=False: the listener thread and main thread
        # share one connection — all writes go through the lock below.
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self.lock = threading.Lock()
        self._create_table()

    def _create_table(self):
        with self.lock:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    kind TEXT DEFAULT 'text',        -- text / code / link (auto-detect later)
                    created_at REAL NOT NULL,
                    copies INTEGER DEFAULT 1,        -- how many times re-copied
                    pinned INTEGER DEFAULT 0         -- 1 = pinned to top
                )
            """)
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_content ON history(content)"
            )
            # Migration for databases created before pinning existed
            cols = [r[1] for r in self.conn.execute("PRAGMA table_info(history)").fetchall()]
            if "pinned" not in cols:
                self.conn.execute("ALTER TABLE history ADD COLUMN pinned INTEGER DEFAULT 0")
            self.conn.commit()

    def add(self, content: str) -> bool:
        """Save a copied item. Returns True if new, False if duplicate."""
        content = content.strip()
        if not content:
            return False

        with self.lock:
            # Duplicate check: same content exists?
            row = self.conn.execute(
                "SELECT id, copies FROM history WHERE content = ?", (content,)
            ).fetchone()

            if row:
                # Bump count + timestamp instead of adding a duplicate
                self.conn.execute(
                    "UPDATE history SET copies = copies + 1, created_at = ? WHERE id = ?",
                    (time.time(), row[0]),
                )
                self.conn.commit()
                return False

            self.conn.execute(
                "INSERT INTO history (content, kind, created_at) VALUES (?, ?, ?)",
                (content, self._detect_kind(content), time.time()),
            )
            self.conn.commit()
            return True

    @staticmethod
    def _detect_kind(content: str) -> str:
        """Auto-tag clips: link / code / text."""
        import re
        stripped = content.strip()
        # Single URL -> link
        if re.fullmatch(r"https?://\S+", stripped):
            return "link"
        # Code hints: common keywords + symbols in the first 200 chars
        head = stripped[:200]
        if re.search(
            r"(def |import |class |function |const |var |let |#include|"
            r"<html|<!DOCTYPE|print\(|console\.log|SELECT .* FROM)",
            head,
        ):
            return "code"
        return "text"

    def search(self, query: str, limit: int = 20) -> list:
        """Search history. Empty query = latest items. Pinned clips come first."""
        q = f"%{query.strip()}%"
        with self.lock:
            rows = self.conn.execute(
                """
                SELECT id, content, kind, copies, created_at, pinned
                FROM history
                WHERE content LIKE ?
                ORDER BY pinned DESC, created_at DESC
                LIMIT ?
                """,
                (q, limit),
            ).fetchall()
        return rows

    def set_pinned(self, clip_id: int, pinned: bool):
        """Pin/unpin a clip. Pinned clips always sort to the top."""
        with self.lock:
            self.conn.execute(
                "UPDATE history SET pinned = ? WHERE id = ?",
                (1 if pinned else 0, clip_id),
            )
            self.conn.commit()

    def stats(self) -> dict:
        """Quick numbers for the panel footer + export metadata."""
        with self.lock:
            total = self.conn.execute("SELECT COUNT(*) FROM history").fetchone()[0]
            links = self.conn.execute(
                "SELECT COUNT(*) FROM history WHERE kind = 'link'"
            ).fetchone()[0]
            code = self.conn.execute(
                "SELECT COUNT(*) FROM history WHERE kind = 'code'"
            ).fetchone()[0]
        return {"total": total, "links": links, "code": code}

    def export_all(self, path: Path):
        """Dump the full history to a JSON file (backup / export feature)."""
        with self.lock:
            rows = self.conn.execute(
                """
                SELECT id, content, kind, copies, created_at, pinned
                FROM history ORDER BY created_at DESC
                """
            ).fetchall()
        data = [
            {
                "id": r[0], "content": r[1], "kind": r[2],
                "copies": r[3], "created_at": r[4],
                "created_iso": time.strftime(
                    "%Y-%m-%d %H:%M:%S", time.localtime(r[4])),
                "pinned": bool(r[5]),
            }
            for r in rows
        ]
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False),
                        encoding="utf-8")
        return len(data)

    def delete(self, clip_id: int):
        """Remove one clip by id."""
        with self.lock:
            self.conn.execute("DELETE FROM history WHERE id = ?", (clip_id,))
            self.conn.commit()

    def get_content(self, clip_id: int):
        """Return the full text of one clip by id (None if missing)."""
        with self.lock:
            row = self.conn.execute(
                "SELECT content FROM history WHERE id = ?", (clip_id,)
            ).fetchone()
        return row[0] if row else None

    def enforce_limit(self, limit: int):
        """Keep only the newest `limit` clips (0 = unlimited). Pinned clips survive."""
        if limit <= 0:
            return
        with self.lock:
            self.conn.execute(
                """
                DELETE FROM history WHERE pinned = 0 AND id NOT IN (
                    SELECT id FROM history ORDER BY created_at DESC LIMIT ?
                )
                """,
                (limit,),
            )
            self.conn.commit()

    def clear_all(self):
        """Wipe the entire history (Settings -> Clear all)."""
        with self.lock:
            self.conn.execute("DELETE FROM history")
            self.conn.commit()


class ClipboardListener(threading.Thread):
    """Background thread: watches the clipboard, saves new items."""

    def __init__(self, history: KlipHistory, interval: float = 0.5):
        super().__init__(daemon=True)
        self.history = history
        self.interval = interval
        self.last_text = None
        self.running = True
        self.paused = False  # settings can pause listening
        self.on_change = None  # optional callback(is_new) fired after every saved copy

    def run(self):
        print("[Klip] Listening to clipboard... (Ctrl+C to stop)")
        while self.running:
            try:
                if not self.paused:
                    current = pyperclip.paste()
                    if current and current != self.last_text:
                        self.last_text = current
                        # Skip giant payloads (e.g. whole Excel sheets, file
                        # dumps) — they would bloat the database for no gain.
                        if len(current) > 100_000:
                            tag = "SKIP"  # too big — not saved, no refresh
                        else:
                            is_new = self.history.add(current)
                            tag = "NEW" if is_new else "DUP"
                            if self.on_change:
                                try:
                                    self.on_change(is_new)
                                except Exception:
                                    pass
                        preview = current.replace("\n", " ")
                        preview = preview[:70] + ("..." if len(preview) > 70 else "")
                        size = len(current)
                        print(f"[Klip] {tag} ({size} chars): {preview}")
            except Exception as e:
                # Clipboard can be briefly locked by other apps — ignore and retry
                print(f"[Klip] clipboard busy: {e}")
            time.sleep(self.interval)


# ---- Quick test: run this file directly ----
if __name__ == "__main__":
    hist = KlipHistory()
    listener = ClipboardListener(hist)
    listener.start()

    print("Copy anything — it shows up here live. Type 'search <word>', 'stats', or 'exit'.")
    while True:
        try:
            cmd = input("> ").strip()
        except (KeyboardInterrupt, EOFError):
            listener.running = False
            print("\n[Klip] Stopped. Bye!")
            break
        if cmd.lower() in ("exit", "quit"):
            listener.running = False
            break
        if cmd.lower().startswith("search "):
            term = cmd[7:]
            results = hist.search(term)
            if not results:
                print("  (no matches)")
            for row in results:
                ago = int(time.time() - row[4])
                snippet = row[1].replace("\n", " ")[:60]
                print(f"  [{row[0]}] ({row[3]}x, {ago}s ago, {len(row[1])} chars) {snippet}")
        elif cmd == "stats":
            print(hist.stats())
