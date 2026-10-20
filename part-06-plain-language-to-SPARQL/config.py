"""Paths, names and settings shared by every script. Nothing secret lives here."""
import os
import pathlib

HERE = pathlib.Path(__file__).parent


def _load_env():
    """Read GOOGLE_API_KEY and friends from .env (this folder, then the parent)."""
    for p in (HERE / ".env", HERE.parent / ".env"):
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env()

UL = "https://ul.edu.lb/kr/scm#"
TIER_NS = "https://ul.edu.lb/kr/id/tier/"
COUNTRY_NS = "https://ul.edu.lb/kr/id/country/"
DATASET = "https://ul.edu.lb/kr/semiconductor/"

# The three files that together make "the graph" live in the sibling folder part-03-RDF.
# Set KG_DIR to look somewhere else, or KG_GRAPH to point at the .nt file directly.
SEARCH_DIRS = ([pathlib.Path(os.environ["KG_DIR"])] if os.getenv("KG_DIR") else []) + [
    HERE.parent / "part-03-RDF",
    HERE / "data",
]


def _find(name):
    for d in SEARCH_DIRS:
        if (d / name).exists():
            return str(d / name)
    return str(SEARCH_DIRS[0] / name)      # not found: the error message names this path


GRAPH_FILES = [
    os.getenv("KG_GRAPH") or _find("semiconductor-knowledge-graph.nt"),
    _find("tier-knowledge.ttl"),
    _find("ontology.ttl"),
]

# Everything the scripts write (void.ttl, vocab.json, model cache, results) goes in STATE_DIR.
# Locally that is this folder; in Docker it is a volume (STATE_DIR=/state).
STATE_DIR = pathlib.Path(os.getenv("STATE_DIR", str(HERE)))
# If set, queries go to this SPARQL endpoint (Fuseki) and no graph files are loaded here.
# Example: http://localhost:3030/semiconductor/sparql
SPARQL_ENDPOINT = os.getenv("SPARQL_ENDPOINT", "")

VOID_FILE = STATE_DIR / "void.ttl"
VOCAB_FILE = STATE_DIR / "vocab.json"
CACHE_FILE = STATE_DIR / "cache" / "llm_cache.json"

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
LLM_MODE = os.getenv("LLM_MODE", "live")          # live | replay
LLM_DELAY = float(os.getenv("LLM_DELAY", "4"))    # seconds between real calls
