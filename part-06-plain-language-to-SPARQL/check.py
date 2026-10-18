"""Checks a query file against the graph's description. No model call.
Usage: python check.py broken.sparql"""
import sys
import pathlib
from access_layer import Schema, check_query

path = sys.argv[1] if len(sys.argv) > 1 else "broken.sparql"
schema = Schema.load()
problems = check_query(pathlib.Path(path).read_text(encoding="utf-8"), schema)
if not problems:
    print("no problems")
else:
    print(f"{len(problems)} problem{'s' if len(problems) > 1 else ''}:")
    for p in problems:
        print("  -", p)
    print("\n" + schema.hints())
