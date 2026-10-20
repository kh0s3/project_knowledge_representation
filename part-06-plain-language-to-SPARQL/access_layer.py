"""The access layer: plain English -> one SPARQL query for the semiconductor graph.

Steps (the same ones as in the lecture):
  1. GROUND   the model in the graph's own description (void.ttl + vocab.json)
  2. SHOW     it a few worked examples (examples.ttl)
  3. CHECK    the query it writes (syntax + names that really exist)
  4. REPAIR   by sending the problems back (max 2 times)
  5. REFUSE   when the graph cannot answer the question
"""
import hashlib
import json
import os
import pathlib
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal
from urllib.parse import unquote

from rdflib import Graph, Literal, Namespace
from rdflib.plugins.sparql import prepareQuery

import config
from config import UL, TIER_NS, COUNTRY_NS

VOID = Namespace("http://rdfs.org/ns/void#")
VEXT = Namespace("http://ldf.fi/void-ext#")
XSD_NS = "http://www.w3.org/2001/XMLSchema#"
SH = Namespace("http://www.w3.org/ns/shacl#")
RDFS = Namespace("http://www.w3.org/2000/01/rdf-schema#")
EXAMPLES_FILE = config.HERE / "examples.ttl"

PREFIXES = {
    "ul": UL,
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "xsd": XSD_NS,
}


# ---------------------------------------------------------------- the graph
# Two ways to reach the graph: local files (rdflib) or a SPARQL endpoint such as Fuseki.
INT_TYPES = {"integer", "int", "long", "short", "nonNegativeInteger", "positiveInteger",
             "negativeInteger", "nonPositiveInteger", "unsignedInt", "unsignedLong"}


def _value(b):
    """One cell of a SPARQL JSON result -> a plain Python value."""
    if b is None:
        return None
    kind, v = b["type"], b["value"]
    if kind == "uri":
        return v
    if kind == "bnode":
        return "_:" + v
    dt = b.get("datatype", "")
    if dt.startswith(XSD_NS):
        short = dt[len(XSD_NS):]
        try:
            if short in INT_TYPES:
                return int(v)
            if short == "decimal":
                return Decimal(v)
            if short in ("double", "float"):
                return float(v)
            if short == "boolean":
                return v == "true"
        except ValueError:
            pass
    return v


class RemoteResult:
    def __init__(self, type_, vars_=None, rows=None, ask=None):
        self.type, self.vars, self.askAnswer = type_, vars_ or [], ask
        self._rows = rows or []

    def __iter__(self):
        return iter(self._rows)


class RemoteGraph:
    """A SPARQL endpoint (Fuseki) that answers .query() like an rdflib Graph does."""

    def __init__(self, endpoint):
        self.endpoint = endpoint

    def query(self, q):
        body = urllib.parse.urlencode({"query": q}).encode("utf-8")
        headers = {"Content-Type": "application/x-www-form-urlencoded",
                   "Accept": "application/sparql-results+json"}
        try:
            with urllib.request.urlopen(urllib.request.Request(self.endpoint, body, headers), timeout=120) as r:
                data = json.load(r)
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"endpoint error {e.code}: {e.read()[:300].decode('utf-8', 'replace')}")
        except urllib.error.URLError as e:
            raise RuntimeError(f"cannot reach {self.endpoint}: {e.reason}")
        if "boolean" in data:
            return RemoteResult("ASK", ask=data["boolean"])
        names = data["head"]["vars"]
        rows = [tuple(_value(b.get(v)) for v in names) for b in data["results"]["bindings"]]
        return RemoteResult("SELECT", names, rows)


def load_graph():
    if config.SPARQL_ENDPOINT:
        return RemoteGraph(config.SPARQL_ENDPOINT)
    g = Graph()
    for f in config.GRAPH_FILES:
        if not pathlib.Path(f).exists():
            raise FileNotFoundError(
                f"Missing {f}. The graph files should be in ../part-03-RDF "
                "(or set KG_DIR to their folder, or SPARQL_ENDPOINT to use Fuseki).")
        g.parse(f)
    return g


def count_triples(g):
    if isinstance(g, RemoteGraph):
        for (n,) in g.query("SELECT (COUNT(*) AS ?n) WHERE { ?s ?p ?o }"):
            return int(n)
    return len(g)


# ---------------------------------------------------------------- the schema
def _local(uri):
    return str(uri).replace(UL, "")


def _dt(uri):
    return str(uri).replace(XSD_NS, "xsd:")


class Schema:
    """What the graph says about itself: read from void.ttl and vocab.json."""

    def __init__(self, by_class, vocab):
        self.by_class = by_class                      # class -> {entities, props}
        self.classes = set(by_class)
        self.props = {p["name"] for c in by_class.values() for p in c["props"]}
        self.tiers = [t["id"] for t in vocab["tiers"]]
        self.vocab = vocab

    @classmethod
    def load(cls):
        if not config.VOID_FILE.exists():
            raise FileNotFoundError("void.ttl not found. Run: python make_void.py")
        vg = Graph()
        vg.parse(str(config.VOID_FILE), format="turtle")
        by_class = {}
        for cp in vg.objects(None, VOID.classPartition):
            name = _local(vg.value(cp, VOID["class"]))
            info = {"entities": int(vg.value(cp, VOID.entities)), "props": []}
            for pp in vg.objects(cp, VOID.propertyPartition):
                info["props"].append({
                    "name": _local(vg.value(pp, VOID.property)),
                    "triples": int(vg.value(pp, VOID.triples)),
                    "targets": sorted(_local(vg.value(b, VOID["class"]))
                                      for b in vg.objects(pp, VEXT.objectClassPartition)),
                    "datatypes": sorted(_dt(vg.value(b, VEXT.datatype))
                                        for b in vg.objects(pp, VEXT.datatypePartition)),
                })
            info["props"].sort(key=lambda p: p["name"])
            by_class[name] = info
        vocab = json.loads(config.VOCAB_FILE.read_text(encoding="utf-8"))
        return cls(by_class, vocab)

    def text(self):
        lines = [f"PREFIX ul: <{UL}>", ""]
        for k in sorted(self.by_class):
            info = self.by_class[k]
            lines.append(f"ul:{k}  ({info['entities']} entities)")
            for p in info["props"]:
                if p["targets"]:
                    lines.append(f"    ul:{p['name']} -> " + " | ".join(f"ul:{t}" for t in p["targets"]))
                else:
                    lines.append(f"    ul:{p['name']}  (" + ", ".join(p["datatypes"] or ["string"]) + ")")
        return "\n".join(lines)

    def vocab_text(self):
        v = self.vocab
        tiers = "\n".join(f"    {t['id']}  =  {t['name']}" for t in v["tiers"])
        return (f"Tier ids (IRI = <{TIER_NS}ID>):\n{tiers}\n"
                f"Years in the data: {', '.join(str(y) for y in v['years'])}\n"
                f"Countries that export (use their ul:name): {', '.join(v['exporters'])}")

    def hints(self):
        return ("Real classes: " + ", ".join(f"ul:{c}" for c in sorted(self.classes)) + "\n"
                "Real properties: " + ", ".join(f"ul:{p}" for p in sorted(self.props)))


# ---------------------------------------------------------------- examples
STOP = {"the", "and", "for", "what", "which", "who", "how", "many", "much", "are", "is", "of",
        "in", "to", "from", "does", "did", "with", "that", "there", "has", "have", "all", "each"}


def _tokens(s):
    return {w.rstrip("s") for w in re.findall(r"[a-z0-9]+", s.lower()) if w not in STOP and len(w) > 2}


def load_examples():
    """Read the worked examples from examples.ttl (SHACL SPARQLSelectExecutable, like the lab)."""
    eg = Graph()
    eg.parse(str(EXAMPLES_FILE), format="turtle")
    items = []
    for s, query in eg.subject_objects(SH.select):
        items.append({"id": int(str(s).rsplit("/", 1)[-1]),
                      "question": str(eg.value(s, RDFS.comment)),
                      "query": str(query)})
    return sorted(items, key=lambda e: e["id"])


def pick_examples(question, k=3):
    """The k examples whose words overlap most with the question (numbers as in examples.ttl)."""
    examples = load_examples()
    qt = _tokens(question)
    scored = sorted((-len(qt & _tokens(e["question"])), e["id"]) for e in examples)
    by_id = {e["id"]: e for e in examples}
    return [(i, by_id[i]) for _, i in scored[:k]]


# ---------------------------------------------------------------- the prompt
RULES = f"""You translate a plain-English question into ONE SPARQL 1.1 query for the knowledge graph described below.

RULES
1. Answer with exactly one query inside a ```sparql block and nothing else. Start with PREFIX lines.
2. Use ONLY the classes and properties listed in SCHEMA. Never invent a name.
3. A ul:TradeObservation is one export: one exporter country sends one tier to one importer country in one year.
   ul:exportedBy = the exporter, ul:importedBy = the importer, ul:hasTier = the product tier. Values are in USD.
4. Countries are found by name: ?c ul:name ?n . FILTER(LCASE(STR(?n)) = "china"). Return ?n, not the IRI.
5. Tiers are IRIs: <{TIER_NS}ID>, with ID taken from the list of tier ids.
6. ul:feeds links tiers in supply order (equipment -> wafers -> chips). Use ul:feeds for one step and ul:feeds+ for direct or indirect.
7. ul:SurplusCountry, ul:DeficitCountry and ul:BalancedCountry are kinds of ul:Country (from the net trade balance number).
8. For "top N" use ORDER BY DESC(...) LIMIT N. For other lists add LIMIT 50.
9. If the graph cannot answer the question (data that is not in SCHEMA, forecasts, opinions, other topics), reply exactly:
   REFUSE: <one short reason>"""


def build_prompt(question, k=3, schema=None):
    schema = schema or Schema.load()
    picked = pick_examples(question, k) if k else []
    parts = [RULES, "SCHEMA (from the graph's own VoID description)", schema.text(), "",
             "VALUES IN THE GRAPH", schema.vocab_text(), ""]
    if picked:
        parts.append("EXAMPLES")
        for n, e in picked:
            parts.append(f"Question: {e['question']}\n```sparql\n{e['query'].strip()}\n```\n")
    parts.append(f"QUESTION: {question}")
    return "\n".join(parts), [n for n, _ in picked]


def repair_prompt(prompt, query, problems, schema):
    return (prompt + "\n\nYour previous answer was:\n```sparql\n" + query + "\n```\n"
            "It has these problems:\n" + "\n".join(f"- {p}" for p in problems) + "\n" + schema.hints() +
            "\n\nReturn the corrected query only, in one ```sparql block (or REFUSE: reason).")


# ---------------------------------------------------------------- the model
def _cache():
    if config.CACHE_FILE.exists():
        return json.loads(config.CACHE_FILE.read_text(encoding="utf-8"))
    return {}


def call_llm(prompt):
    """Gemini over plain HTTPS. Every answer is cached, so LLM_MODE=replay can repeat it later."""
    key = hashlib.sha256((config.MODEL + "\n" + prompt).encode("utf-8")).hexdigest()
    cache = _cache()
    if key in cache:
        return cache[key]
    if config.LLM_MODE == "replay":
        raise RuntimeError("replay mode: no saved answer for this prompt. Run it once live first.")
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("No GOOGLE_API_KEY. Copy .env.example to .env and add your key.")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{config.MODEL}:generateContent"
    body = json.dumps({"contents": [{"parts": [{"text": prompt}]}],
                       "generationConfig": {"temperature": 0}}).encode("utf-8")
    headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}
    for attempt in range(5):
        time.sleep(config.LLM_DELAY)
        try:
            with urllib.request.urlopen(urllib.request.Request(url, body, headers), timeout=120) as r:
                data = json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = 15 * (attempt + 1)
                print(f"  (429 too many requests, waiting {wait}s)")
                time.sleep(wait)
                continue
            raise RuntimeError(f"Gemini error {e.code}: {e.read()[:300]!r}")
        try:
            text = "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"])
        except (KeyError, IndexError):
            raise RuntimeError(f"Gemini returned no text: {str(data)[:300]}")
        cache[key] = text
        config.CACHE_FILE.parent.mkdir(exist_ok=True)
        config.CACHE_FILE.write_text(json.dumps(cache, indent=1), encoding="utf-8")
        return text
    raise RuntimeError("Still rate limited. If the daily limit is used up, use LLM_MODE=replay "
                       "(only works for prompts you already ran) or try again tomorrow.")


# ---------------------------------------------------------------- the check
def extract_sparql(text):
    """-> (query, None) or (None, refusal reason)."""
    t = text.strip()
    m = re.search(r"```(?:sparql)?\s*(.*?)```", t, re.S | re.I)
    if m:
        return m.group(1).strip(), None
    if re.match(r"^\s*REFUSE", t, re.I):
        return None, t
    return t, None


def ensure_prefixes(q):
    missing = [f"PREFIX {p}: <{u}>" for p, u in PREFIXES.items()
               if not re.search(rf"PREFIX\s+{p}\s*:", q, re.I)]
    return "\n".join(missing) + "\n" + q if missing else q


def check_query(query, schema):
    """Return a list of problems (empty list = the query is fine)."""
    problems = []
    q = ensure_prefixes(query)
    if re.search(r"\b(INSERT|DELETE|DROP|CLEAR|LOAD|CREATE)\b\s*(DATA|WHERE|GRAPH|SILENT|\{|<)", q, re.I):
        return ["only read queries (SELECT or ASK) are allowed"]
    try:
        algebra = prepareQuery(q).algebra.name
        if algebra not in ("SelectQuery", "AskQuery"):
            problems.append("only SELECT or ASK queries are allowed")
    except Exception as e:
        problems.append("syntax error: " + str(e).strip().splitlines()[0][:200])

    used = set(re.findall(r"\bul:([A-Za-z_][A-Za-z0-9_]*)", q)) | \
        set(re.findall(rf"<{re.escape(UL)}([A-Za-z0-9_]+)>", q))
    as_class = set(re.findall(r"(?<![\w?$])a\s+ul:([A-Za-z0-9_]+)", q)) | \
        set(re.findall(r"rdf:type\s+ul:([A-Za-z0-9_]+)", q))
    for n in sorted(used):
        if n in as_class:
            if n not in schema.classes:
                problems.append(f"ul:{n} is not a class of this graph")
        elif n in schema.classes and n not in schema.props:
            problems.append(f"ul:{n} is a class, not a property")
        elif n not in schema.props:
            problems.append(f"ul:{n} is not a property of this graph")
    for t in sorted(set(re.findall(rf"{re.escape(TIER_NS)}([A-Za-z0-9_]+)", q))):
        if t not in schema.tiers:
            problems.append(f"tier '{t}' does not exist. Tiers: {', '.join(schema.tiers)}")
    return problems


# ---------------------------------------------------------------- running
def _cell(x):
    if isinstance(x, Literal):
        return x.toPython()
    if x is None or isinstance(x, (int, float, bool, Decimal)):
        return x
    return str(x)


def run_query(g, query):
    res = g.query(ensure_prefixes(query))
    if res.type == "ASK":
        return ["answer"], [[bool(res.askAnswer)]]
    names = [str(v) for v in res.vars]
    rows = []
    for r in res:
        rows.append([_cell(x) for x in r])
        if len(rows) >= 1000:
            break
    return names, rows


def ask(question, k=3, repair=True, execute=True, g=None, schema=None, max_repairs=2):
    """Full path. status is: ok | refused | failed."""
    schema = schema or Schema.load()
    if execute and g is None:
        g = load_graph()
    prompt, picked = build_prompt(question, k, schema)
    text = call_llm(prompt)
    repairs, query, problems = 0, "", []
    while True:
        query, refusal = extract_sparql(text)
        if refusal:
            return {"status": "refused", "reason": refusal, "query": "", "picked": picked, "repairs": repairs}
        problems = check_query(query, schema) if repair else []
        if not problems:
            if not execute:
                return {"status": "ok", "query": query, "picked": picked, "repairs": repairs}
            try:
                names, rows = run_query(g, query)
                return {"status": "ok", "query": query, "vars": names, "rows": rows,
                        "picked": picked, "repairs": repairs}
            except Exception as e:
                problems = [f"the query failed to run: {str(e)[:200]}"]
        if not repair or repairs >= max_repairs:
            return {"status": "failed", "query": query, "problems": problems,
                    "picked": picked, "repairs": repairs}
        repairs += 1
        text = call_llm(repair_prompt(prompt, query, problems, schema))
