"""Measures the access layer. Runs every question in eval_questions.json in three settings:
  schema    the model sees only the VoID schema (no examples, no repair)
  examples  schema + 3 worked examples
  repair    schema + examples + the check-and-repair loop
Score = F1 between the cell values of the model's result and the gold query's result.
A question that should be refused scores 1 if refused, 0 if answered.
About 25 calls. Answers are cached, so a second run is almost free."""
import json
from decimal import Decimal
from urllib.parse import unquote

import config
from access_layer import ask, load_graph, run_query, Schema, ensure_prefixes

SETTINGS = {"schema": dict(k=0, repair=False),
            "examples": dict(k=3, repair=False),
            "repair": dict(k=3, repair=True)}


def norm(v):
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, (int, float, Decimal)):
        return str(round(float(v), 2))
    s = str(v).strip()
    for ns in (config.TIER_NS, config.COUNTRY_NS):
        if s.startswith(ns):
            s = unquote(s[len(ns):])
    return s.lower()


def cells(rows):
    return {norm(c) for r in rows for c in r if c is not None}


def f1(pred, gold):
    p, g = cells(pred), cells(gold)
    tp = len(p & g)
    prec = tp / len(p) if p else 0.0
    rec = tp / len(g) if g else 0.0
    return 2 * prec * rec / (prec + rec) if prec + rec else 0.0


questions = json.loads((config.HERE / "eval_questions.json").read_text(encoding="utf-8"))
g, schema = load_graph(), Schema.load()

gold = {}
for q in questions:
    if q.get("refuse"):
        continue
    _, rows = run_query(g, q["gold"])
    gold[q["id"]] = rows
    if not rows:
        print(f"WARNING {q['id']}: the gold query returned nothing. Check the names in vocab.json. Skipped.")

lines = []
summary = []
for name, opts in SETTINGS.items():
    scores, refused_ok, refused_bad, failed = [], 0, 0, 0
    print(f"\n== {name} ==")
    for q in questions:
        res = ask(q["question"], g=g, schema=schema, **opts)
        if q.get("refuse"):
            ok = res["status"] == "refused"
            refused_ok += ok
            score = 1.0 if ok else 0.0
            note = "refused (correct)" if ok else "answered, should have refused"
        elif q["id"] not in gold or not gold[q["id"]]:
            continue
        elif res["status"] == "refused":
            refused_bad += 1
            score, note = 0.0, "refused wrongly"
            scores.append(score)
        elif res["status"] == "failed":
            failed += 1
            score, note = 0.0, "failed: " + "; ".join(res["problems"])[:80]
            scores.append(score)
        else:
            score = f1(res["rows"], gold[q["id"]])
            note = f"repairs={res['repairs']}"
            scores.append(score)
        line = f"{q['id']:>4}  F1 {score:.2f}  {note}  | {q['question']}"
        print(line)
        lines.append(f"[{name}] {line}")
    mean = sum(scores) / len(scores) if scores else 0.0
    n_ref = sum(1 for q in questions if q.get("refuse"))
    summary.append(f"{name:<9} mean F1 {mean:.2f}   correct refusals {refused_ok}/{n_ref}   "
                   f"wrong refusals {refused_bad}   failed {failed}")

print("\n" + "\n".join(summary))
out = config.STATE_DIR / "results"
out.mkdir(parents=True, exist_ok=True)
(out / "evaluate.txt").write_text("\n".join(summary) + "\n\n" + "\n".join(lines) + "\n", encoding="utf-8")
print(f"\nsaved results/{'evaluate.txt'}")
