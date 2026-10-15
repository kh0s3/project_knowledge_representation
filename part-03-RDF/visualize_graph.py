from pathlib import Path

from rdflib import Graph, Namespace, RDF, URIRef, Literal
from pyvis.network import Network

HERE = Path(__file__).resolve().parent
RDF_FILE = HERE / "semiconductor-knowledge-graph.nt"
TIER_FILE = HERE / "tier-knowledge.ttl"      # holds the 'feeds' links
OUTPUT_FILE = HERE / "semiconductor-graph.html"

TOP_N = 40        # how many trades to draw
YEAR = None       # e.g. 2023 to only show one year, None = all years

UL = Namespace("https://ul.edu.lb/kr/scm#")

g = Graph()
g.parse(str(RDF_FILE), format="nt")
if TIER_FILE.exists():
    g.parse(str(TIER_FILE), format="turtle")
print(f"Loaded {len(g):,} RDF triples")


def num(uri, pred):
    v = g.value(uri, pred)
    return float(str(v)) if v is not None else 0.0


# Pick the biggest trades (not the first 50 in alphabetical order,
# which would all come from one or two exporters)
trades = list(g.subjects(RDF.type, UL.TradeObservation))
if YEAR:
    trades = [t for t in trades if int(num(t, UL.year)) == YEAR]
selected = sorted(trades, key=lambda t: num(t, UL.tradeValueUsd), reverse=True)[:TOP_N]

nodes = set(selected)
for t in selected:
    for p, o in g.predicate_objects(t):
        if isinstance(o, URIRef) and p != RDF.type:   # skip class nodes
            nodes.add(o)

# Always show every tier so the feeds chain is visible
nodes.update(g.subjects(RDF.type, UL.Tier))


def short_name(uri):
    return str(uri).rstrip("/").split("#")[-1].split("/")[-1]


def label(uri):
    if (uri, RDF.type, UL.TradeObservation) in g:
        value = num(uri, UL.tradeValueUsd) / 1e9
        return f"${value:.1f}B\n{int(num(uri, UL.year))}"
    name = g.value(uri, UL.name)
    return str(name) if name else short_name(uri).replace("_", " ")


net = Network(height="800px", width="100%", directed=True,
              bgcolor="#ffffff", font_color="#222222", cdn_resources="in_line")

for uri in nodes:
    props = [f"{short_name(p)}: {v}" for p, v in g.predicate_objects(uri)
             if isinstance(v, Literal)]
    types = set(g.objects(uri, RDF.type))
    if UL.TradeObservation in types:
        color = "#93c5fd"      # blue  = trade
    elif UL.Country in types:
        color = "#86efac"      # green = country
    else:
        color = "#fde68a"      # yellow = tier
    net.add_node(str(uri), label=label(uri), title="<br>".join(props) or str(uri),
                 color=color, shape="dot", size=18)

for s in nodes:
    for p, o in g.predicate_objects(s):
        if isinstance(o, URIRef) and o in nodes and p != RDF.type:
            net.add_edge(str(s), str(o), label=short_name(p), title=str(p),
                         arrows="to", dashes=(p == UL.feeds),
                         color="#d97706" if p == UL.feeds else None)

net.show_buttons(filter_=["physics"])
OUTPUT_FILE.write_text(net.generate_html(notebook=False), encoding="utf-8")
print(f"Saved {OUTPUT_FILE} | trades: {len(selected)} | nodes: {len(nodes)}")
