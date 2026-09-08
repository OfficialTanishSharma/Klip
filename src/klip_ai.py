"""
Klip — AI actions (Feature 2)
Takes copied text and sends it to a free AI provider (Groq first, Gemini fallback).
Actions: summarize / translate / explain / fix code.

Setup:
1. Get a FREE Groq API key: https://console.groq.com/keys
2. Put it in klip_data/.env file like this:
   GROQ_API_KEY=gsk_your_key_here
"""

import os
import re
import json
import urllib.request
from pathlib import Path

# .env lives in klip_data/ (gitignored — never upload keys)
ENV_PATH = Path(__file__).parent.parent / "klip_data" / ".env"


def load_env():
    """Read klip_data/.env into os.environ (no external library needed)."""
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())


load_env()

# ---- Provider chain (same pattern as Zevion: try 1, fall back to 2) ----
# Model picked from Groq's live /models list (verified working, Sep 2026)
PROVIDERS = [
    {
        "name": "Groq",
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "model": "openai/gpt-oss-120b",
        "key_env": "GROQ_API_KEY",
    },
    {
        "name": "Groq-Qwen",
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "model": "qwen/qwen3.8-27b",
        "key_env": "GROQ_API_KEY",
    },
]

PROMPTS = {
    "summarize": (
        "Summarize the following text in 3 short bullet points. "
        "Keep it simple and clear. Reply with plain text only — no markdown, "
        "no bold (**), no asterisks.\n\nText:\n"
    ),
    "translate": (
        "Translate the following text to {lang}. "
        "If the text is already in {lang}, translate it to English. "
        "Reply with ONLY the translated text. No quotes, no labels, "
        "no notes, no repetition of the original.\n\nText:\n"
    ),
    "explain": (
        "Explain the following text/code in simple words, like you are teaching "
        "a beginner. Keep it under 150 words. Reply with plain text only — no "
        "markdown, no bold (**), no asterisks, no tables.\n\nText:\n"
    ),
    "fix": (
        "The following is a code snippet. Find bugs or problems in it, list them "
        "briefly in plain sentences (no markdown, no bold, no tables), then show "
        "the corrected version as plain code. Keep the explanation short.\n\nCode:\n"
    ),
}

# ---- Safety guard: detect passwords/keys so they never leave the machine ----
SENSITIVE_PATTERNS = [
    (r"\b(gsk|sk|pk|rk)_[A-Za-z0-9]{16,}", "API key"),
    (r"\b(gsk|sk|pk|rk)-[A-Za-z0-9_\-]{16,}", "API key"),
    (r"\bAKIA[0-9A-Z]{16}\b", "AWS access key"),
    (r"\bghp_[A-Za-z0-9]{20,}\b", "GitHub token"),
    (r"\bgh[pousr]_[A-Za-z0-9]{20,}\b", "GitHub token"),
    (r"\bxox[baprs]-[A-Za-z0-9\-]{10,}", "Slack token"),
    (r"-----BEGIN [A-Z ]*PRIVATE KEY-----", "private key"),
    (r"(?i)\b(password|passwd|pwd)\s*[:=]\s*\S+", "password line"),
    (r"(?i)\b(api[_-]?key|secret|token)\s*[:=]\s*['\"]?\S{8,}", "secret line"),
    (r"\b(?:\d[ -]?){13,16}\b", "credit-card-like number"),
]

_COMPILED = [(re.compile(p), label) for p, label in SENSITIVE_PATTERNS]


def is_sensitive(text: str):
    """Return (True, reason) if the text looks like a password/key/card, else (False, None)."""
    if not text:
        return False, None
    # Long code files may contain the word 'password' innocuously — only scan the
    # whole text for key-like patterns, but skip card check for >2000 chars.
    for pattern, label in _COMPILED:
        if label == "credit-card-like number" and len(text) > 2000:
            continue
        if pattern.search(text):
            return True, label
    return False, None


# Languages available for the Translate action (Settings -> Translate language)
LANGUAGES = [
    "Hindi", "English", "Spanish", "French", "German", "Portuguese",
    "Italian", "Russian", "Arabic", "Chinese", "Japanese", "Korean",
    "Turkish", "Urdu", "Bengali", "Punjabi", "Tamil", "Telugu",
    "Marathi", "Gujarati", "Indonesian", "Dutch", "Polish", "Thai",
    "Vietnamese",
]


def build_prompt(action: str, text: str, translate_lang: str = "Hindi") -> str:
    """Build the full prompt for an action, using the selected translate language."""
    if action == "translate":
        return PROMPTS["translate"].format(lang=translate_lang) + text
    return PROMPTS.get(action, PROMPTS["summarize"]) + text


def ask_ai(action: str, text: str, translate_lang: str = "Hindi") -> str:
    """Send text to the first available provider, return the answer."""
    if not PROVIDERS:
        return "No providers configured."

    # Very long clips: keep the head + tail so the prompt stays within limits
    if len(text) > 12000:
        text = text[:9000] + "\n\n[...middle part skipped...]\n\n" + text[-2500:]
    prompt = build_prompt(action, text, translate_lang)

    for provider in PROVIDERS:
        api_key = os.environ.get(provider["key_env"], "").strip()
        if not api_key:
            continue  # no key for this provider -> try next

        payload = json.dumps({
            "model": provider["model"],
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_completion_tokens": 1600,
        }).encode("utf-8")

        request = urllib.request.Request(
            provider["url"],
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
                # Cloudflare (error 1010) blocks requests without a User-Agent
                "User-Agent": "Klip/1.0",
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                data = json.loads(response.read().decode("utf-8"))
                content = data["choices"][0]["message"]["content"].strip()
                # gpt-oss models put the visible answer after the reasoning block
                if "<think>" in content and "</think>" in content:
                    content = content.split("</think>", 1)[1].strip()
                return content if content else "(empty response from model)"
        except Exception as e:
            print(f"[Klip AI] {provider['name']} failed: {e}")
            continue  # fall back to next provider

    return (
        "No AI provider available. "
        f"Get a free Groq key at https://console.groq.com/keys "
        f"and put it in {ENV_PATH} as GROQ_API_KEY=your_key"
    )


# ---- CLI test mode ----
if __name__ == "__main__":
    import pyperclip

    print("Klip AI actions — test mode")
    print("Actions: summarize / translate / explain / fix")
    print("It uses whatever is currently in your clipboard.\n")

    while True:
        action = input("Action (or 'exit'): ").strip().lower()
        if action in ("exit", "quit"):
            break
        if action not in PROMPTS:
            print(f"Unknown action. Choose one of: {', '.join(PROMPTS)}")
            continue

        text = pyperclip.paste().strip()
        if not text:
            print("Clipboard is empty — copy something first.")
            continue

        print(f"Sending {len(text)} chars to AI ({action})... ")
        answer = ask_ai(action, text)
        print("\n--- AI says ---")
        print(answer)
        print("--- end ---\n")
