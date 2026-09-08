"""Klip test suite — checks the modules without needing user interaction."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from klip_history import KlipHistory
from klip_ai import is_sensitive
from klip_settings import load_settings, save_settings
import json

results = []

def check(name, fn):
    try:
        fn()
        results.append((name, "PASS"))
    except Exception as e:
        results.append((name, f"FAIL: {e}"))

def test_add_new():
    h = KlipHistory()
    assert h.add(f"test item {time.time()}") == True

def test_add_duplicate():
    h = KlipHistory()
    item = "duplicate check unique string"
    h.add(item)
    assert h.add(item) == False  # second add = duplicate

def test_search():
    h = KlipHistory()
    marker = f"searchable marker {time.time()}"
    h.add(marker)
    rows = h.search(marker[:20])
    assert len(rows) >= 1

def test_stats():
    h = KlipHistory()
    s = h.stats()
    assert "total" in s and s["total"] >= 1

# ---- Safety guard tests ----

def test_guard_groq_key():
    hit, why = is_sensitive("my key is gsk_FAKEKEY1234567890abcdefFAKEKEY")
    assert hit and why == "API key"

def test_guard_openai_key():
    hit, why = is_sensitive("sk-proj-abc123def456ghi789jkl012")
    assert hit and why == "API key"

def test_guard_aws():
    hit, why = is_sensitive("AKIAIOSFODNN7EXAMPLE")
    assert hit and why == "AWS access key"

def test_guard_github():
    hit, why = is_sensitive("ghp_abcdefghijklmnopqrstuvwx")
    assert hit and why == "GitHub token"

def test_guard_private_key():
    hit, why = is_sensitive("-----BEGIN RSA PRIVATE KEY-----")
    assert hit and why == "private key"

def test_guard_password_line():
    hit, why = is_sensitive("password: hunter2secret")
    assert hit and why == "password line"

def test_guard_credit_card():
    hit, why = is_sensitive("4111 1111 1111 1111")
    assert hit and why == "credit-card-like number"

def test_guard_clean_text_passes():
    hit, why = is_sensitive("Klip is a clipboard manager built in Python. It saves copies.")
    assert not hit and why is None

def test_guard_empty():
    hit, why = is_sensitive("")
    assert not hit

def test_settings_defaults():
    s = load_settings()
    assert s["history_limit"] == 500
    assert s["ai_actions"]["Summarize"] == True

def test_settings_roundtrip():
    s = load_settings()
    s["history_limit"] = 123
    save_settings(s)
    s2 = load_settings()
    assert s2["history_limit"] == 123
    s2["history_limit"] = 500  # restore default
    save_settings(s2)

def test_history_limit_enforced():
    h = KlipHistory()
    h.add("limit test a")
    h.add("limit test b")
    h.enforce_limit(1)  # keep only newest
    rows = h.search("limit test")
    assert len(rows) == 1 and "b" in rows[0][1]

def test_clear_all():
    h = KlipHistory()
    h.add("clear-all marker 999")
    h.clear_all()
    assert h.search("clear-all marker 999") == []

# ---- Pin + delete tests ----

def test_pin():
    h = KlipHistory()
    a = f"pin test A {time.time()}"
    b = f"pin test B {time.time()}"
    h.add(a)
    h.add(b)
    row_a = h.search("pin test A")[0]
    h.set_pinned(row_a[0], True)
    rows = h.search("pin test")
    assert rows[0][1] == row_a[1]  # pinned clip comes first despite being older
    h.set_pinned(row_a[0], False)
    rows = h.search("pin test")
    assert rows[0][1] != row_a[1] or rows[-1][1] == row_a[1]

def test_delete():
    h = KlipHistory()
    marker = f"delete marker {time.time()}"
    h.add(marker)
    row = h.search(marker[:30])[0]
    h.delete(row[0])
    assert h.search(marker[:30]) == []

def test_get_content():
    h = KlipHistory()
    marker = f"content marker {time.time()}"
    h.add(marker)
    row = h.search(marker[:30])[0]
    assert h.get_content(row[0]) == marker
    assert h.get_content(999999) is None

def test_pinned_survives_limit():
    h = KlipHistory()
    p = f"pinned survivor {time.time()}"
    h.add(p)
    row = h.search("pinned survivor")[0]
    h.set_pinned(row[0], True)
    for i in range(5):
        h.add(f"filler {time.time()} {i}")
    h.enforce_limit(3)  # keep only 3 newest — pinned one must survive
    rows = h.search("pinned survivor")
    assert len(rows) == 1

# ---- Auto-tag (kind) tests ----

def test_kind_link():
    h = KlipHistory()
    url = f"https://example.com/unique-{time.time()}"
    h.add(url)
    assert h.search(url[:40])[0][2] == "link"

def test_kind_code():
    h = KlipHistory()
    code = f"def hello_{int(time.time())}():\n    return 'hi'"
    h.add(code)
    assert h.search(code[:30])[0][2] == "code"

def test_kind_text():
    h = KlipHistory()
    text = f"just a plain sentence about nothing {time.time()}"
    h.add(text)
    assert h.search(text[:30])[0][2] == "text"

def test_stats_kinds():
    h = KlipHistory()
    s = h.stats()
    assert "links" in s and "code" in s

def test_export_all():
    h = KlipHistory()
    marker = f"export marker {time.time()}"
    h.add(marker)
    out = Path(__file__).parent.parent / "klip_data" / "_test_export.json"
    count = h.export_all(out)
    assert count >= 1
    data = json.loads(out.read_text(encoding="utf-8"))
    assert any(marker in d["content"] for d in data)
    out.unlink()  # clean up

check("add new item", test_add_new)
check("duplicate merge", test_add_duplicate)
check("search works", test_search)
check("stats works", test_stats)
check("guard: groq key", test_guard_groq_key)
check("guard: openai key", test_guard_openai_key)
check("guard: aws key", test_guard_aws)
check("guard: github token", test_guard_github)
check("guard: private key", test_guard_private_key)
check("guard: password line", test_guard_password_line)
check("guard: credit card", test_guard_credit_card)
check("guard: clean text ok", test_guard_clean_text_passes)
check("guard: empty ok", test_guard_empty)
check("settings: defaults", test_settings_defaults)
check("settings: save/load", test_settings_roundtrip)
check("history: limit enforced", test_history_limit_enforced)
check("history: clear all", test_clear_all)
check("pin: pinned first + unpin", test_pin)
check("delete: remove one clip", test_delete)
check("get_content: by id", test_get_content)
check("pin: survives limit", test_pinned_survives_limit)
check("kind: link detected", test_kind_link)
check("kind: code detected", test_kind_code)
check("kind: text default", test_kind_text)
check("stats: kind counts", test_stats_kinds)
check("export: json backup", test_export_all)

print("\n=== KLIP TEST RESULTS ===")
for name, status in results:
    icon = "OK" if status == "PASS" else "XX"
    print(f"  [{icon}] {name}: {status}")
passed = sum(1 for _, s in results if s == "PASS")
print(f"\n{passed}/{len(results)} passed")
