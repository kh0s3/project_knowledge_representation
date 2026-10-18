"""Ask a question in plain English. Usage: python ask.py "Who exports the most wafers?" """
import sys
from access_layer import ask

question = " ".join(sys.argv[1:]) or "How many countries import logic processors?"
res = ask(question)
print("QUESTION:", question)
print("examples picked:", res["picked"], "| repairs:", res["repairs"])
if res["status"] == "refused":
    print("\nREFUSED:", res["reason"])
elif res["status"] == "failed":
    print("\nFAILED. Last query:\n" + res["query"])
    print("Problems:", *res["problems"], sep="\n  - ")
else:
    print("\n" + res["query"] + "\n")
    print(" | ".join(res["vars"]))
    print("-" * 50)
    for row in res["rows"][:15]:
        print(" | ".join("" if c is None else str(c) for c in row))
    if len(res["rows"]) > 15:
        print(f"... {len(res['rows'])} rows in total")
    if len(res["rows"]) == 1 and len(res["rows"][0]) == 1:
        print(f"\nn={res['rows'][0][0]}")
