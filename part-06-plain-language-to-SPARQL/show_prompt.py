"""Shows the exact prompt for a question. No model call, so it costs nothing.
Usage: python show_prompt.py "How many trades are there?" """
import sys
from access_layer import build_prompt

question = " ".join(sys.argv[1:]) or "Which countries export Tier 1 equipment?"
prompt, picked = build_prompt(question)
print(prompt)
print(f"\n--- examples picked: {', '.join(map(str, picked))} | {len(prompt)} characters ---")
