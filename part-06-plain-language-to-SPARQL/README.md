# Part 05: plain English to SPARQL (the access layer)

Someone who does not know SPARQL types a question in English. The access layer turns it into a
SPARQL query for the semiconductor trade graph, checks the query, and (if you want) runs it.

## The idea in four steps
1. **Describe the graph** (`void.ttl`): classes, properties and what they point to, read from the graph itself.
2. **Show examples** (`examples.json`): 9 questions, each with its correct query. 3 are picked per question.
3. **Check the answer**: the query must parse and use only names that exist. If not, the problems go back to the model (max 2 repairs).
4. **Refuse** when the graph cannot answer (prices, forecasts, companies).

## Before you start
1. Nothing to copy. The scripts read `semiconductor-knowledge-graph.nt`, `tier-knowledge.ttl` and
   `ontology.ttl` from the sibling folder `../part-03-RDF`. Keep `part-03-RDF` and this folder side by side.
   (Files are somewhere else? Set `KG_DIR` to that folder.)
2. `pip install rdflib` (only if it is not already in your environment).
3. Copy `.env.example` to `.env` and put your Gemini key after `GOOGLE_API_KEY=`.
4. Run every command from this folder.

## Run in this order
| Command | What it does | Model call? |
|---|---|---|
| `python make_void.py` | writes `void.ttl` and `vocab.json` | no |
| `python show_prompt.py "How many trade records are there?"` | prints the full prompt | no |
| `python check.py broken.sparql` | finds `ul:shippedBy` is not a property, lists the real ones | no |
| `python ask.py "Which country exports the most wafers?"` | question, query, rows | yes |
| `python evaluate.py` | 3 settings (schema / examples / repair), about 25 calls | yes |

## Files
- `config.py`: paths and settings. `access_layer.py`: the whole pipeline.
- `make_void.py`, `show_prompt.py`, `ask.py`, `check.py`, `evaluate.py`, `serve.py`: the runnable steps.
- `examples.json`: worked examples. `eval_questions.json`: 12 test questions (10 answerable with a gold query, 2 that must be refused).
- `broken.sparql`: a query with a wrong property, for `check.py`.
- `void.ttl`, `vocab.json`, `cache/`, `results/`: created when you run things.

## Notes
- Every model answer is cached in `cache/llm_cache.json`. `LLM_MODE=replay` repeats cached answers with no key and no internet, but only for prompts you already ran live.
- Free tier too slow or 429 errors? Set `LLM_DELAY=8`. Wrong model name? Set `GEMINI_MODEL` to one listed in AI Studio.
- `eval_questions.json` and two examples use "China" and "Japan". Check `vocab.json` for the exact country names in your data. If a gold query returns nothing, `evaluate.py` warns and skips that question.
- F1 compares the set of values in the rows, ignoring column order and names.
