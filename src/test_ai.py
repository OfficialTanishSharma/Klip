"""Non-interactive end-to-end test of klip_ai.ask_ai() with the real API."""
import sys

sys.path.insert(0, r"C:\Users\AVITA\Downloads\Meow Asistant\Klip\src")
from klip_ai import ask_ai

sample = (
    "Klip is an AI clipboard manager for Windows. It watches your clipboard, "
    "saves every copy automatically, and lets you summarize, translate, explain "
    "or fix code with one click. It uses free AI providers like Groq. "
    "Built by a 14-year-old developer named RolBol."
)

print("Testing action: summarize")
answer = ask_ai("summarize", sample)
print("=== AI RESPONSE ===")
print(answer)
