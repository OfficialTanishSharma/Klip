"""OpenAI key test — reads OPENAI_API_KEY from klip_data/.env (NEVER printed),
lists available models, then tries one tiny chat call.
Tells us: key works? credits left? which GPT models are real?"""
import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

ENV_PATH = Path(__file__).parent.parent / "klip_data" / ".env"

# Load .env (same pattern as klip_ai.py)
if ENV_PATH.exists():
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

key = os.environ.get("OPENAI_API_KEY", "").strip()
if not key:
    print("NO KEY FOUND — add this line to klip_data/.env:")
    print("  OPENAI_API_KEY=sk-...")
    sys.exit(1)

# Show only a safe fragment so we can confirm WHICH key loaded
print(f"Key loaded: {key[:10]}...{key[-4:]} ({len(key)} chars)")
headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

# ---- Step 1: list models (no credits consumed) ----
print("\n=== 1. MODELS LIST ===")
try:
    req = urllib.request.Request("https://api.openai.com/v1/models", headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode("utf-8"))
        models = sorted(m["id"] for m in data.get("data", []))
        print(f"Account has access to {len(models)} models:")
        for m in models:
            print("  ", m)
except urllib.error.HTTPError as e:
    body = e.read().decode("utf-8")[:400]
    print(f"FAILED: HTTP {e.code}")
    print(body)
    if e.code == 401:
        print("-> 401 = key invalid/revoked")
    sys.exit(1)
except Exception as e:
    print(f"FAILED: {e}")
    sys.exit(1)

# ---- Step 2: tiny chat call on candidate models (first hit wins) ----
print("\n=== 2. CHAT TEST (tiny, cheap) ===")
candidates = [
    "gpt-5.6-luna-terra", "gpt-5.6", "gpt-5.4",
    "gpt-4.1-mini", "gpt-4o-mini",
]
for model in candidates:
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": "Say OK and nothing else."}],
        "max_completion_tokens": 10,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=payload, headers=headers,
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read().decode("utf-8"))
            answer = data["choices"][0]["message"]["content"].strip()
            usage = data.get("usage", {})
            print(f"  WORKS: {model} -> '{answer}' "
                  f"(tokens used: {usage.get('total_tokens', '?')})")
            break
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")[:250]
        msg = "unknown"
        try:
            msg = json.loads(body)["error"]["message"]
        except Exception:
            msg = body
        print(f"  {model}: HTTP {e.code} — {msg[:120]}")
        if e.code == 429 and "quota" in msg.lower():
            print("  -> 429 quota = account has NO credits (free tier nahi hai)")
            break
else:
    print("  None of the candidate models worked.")
