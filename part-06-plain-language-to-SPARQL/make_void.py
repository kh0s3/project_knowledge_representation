"""Step 1. Describe the graph: writes void.ttl (the graph's own description) and vocab.json.

void.ttl says, for every class: how many entities, which properties they have,
and which class (or datatype) each property points to. The model is shown this
instead of guessing the schema.
"""
import json

from rdflib import BNode, Graph, Literal, Namespace, RDF, URIRef

import config
from access_layer import load_graph, VOID, VEXT

UL = config.UL
g = load_graph()
 
""" how many instance per class"""
CLASSES = """
SELECT ?class (COUNT(DISTINCT ?s) AS ?n)
WHERE { ?s a ?class . FILTER(STRSTARTS(STR(?class), "__UL__")) }
GROUP BY ?class"""



PROPS = """
SELECT ?class ?p ?oclass ?dt ?iri (COUNT(*) AS ?n)
WHERE {
  ?s a ?class ; ?p ?o .
  FILTER(?p != <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> && STRSTARTS(STR(?class), "__UL__"))
  OPTIONAL { ?o a ?oclass . FILTER(STRSTARTS(STR(?oclass), "__UL__")) }
  BIND(DATATYPE(?o) AS ?dt)
  BIND(isIRI(?o) AS ?iri)
}
GROUP BY ?class ?p ?oclass ?dt ?iri"""

vg = Graph()
vg.bind("void", VOID)
vg.bind("void-ext", VEXT)
vg.bind("ul", Namespace(UL))
ds = URIRef(config.DATASET)
vg.add((ds, RDF.type, VOID.Dataset))
vg.add((ds, VOID.triples, Literal(len(g))))

parts = {}
for klass, n in g.query(CLASSES.replace("__UL__", UL)):
    cp = BNode()
    parts[str(klass)] = cp
    vg.add((ds, VOID.classPartition, cp))
    vg.add((cp, VOID["class"], URIRef(klass)))
    vg.add((cp, VOID.entities, Literal(int(n))))

props = {}
for klass, p, oclass, dt, iri, n in g.query(PROPS.replace("__UL__", UL)):
    d = props.setdefault((str(klass), str(p)), {"triples": 0, "targets": set(), "dts": set()})
    d["triples"] += int(n)
    if oclass is not None:
        d["targets"].add(str(oclass))
    elif dt is not None:
        d["dts"].add(str(dt))
    elif not (iri is not None and bool(iri)):
        d["dts"].add("http://www.w3.org/2001/XMLSchema#string")

for (klass, p), d in sorted(props.items()):
    pp = BNode()
    vg.add((parts[klass], VOID.propertyPartition, pp))
    vg.add((pp, VOID.property, URIRef(p)))
    vg.add((pp, VOID.triples, Literal(d["triples"])))
    for t in sorted(d["targets"]):
        b = BNode()
        vg.add((pp, VEXT.objectClassPartition, b))
        vg.add((b, VOID["class"], URIRef(t)))
    for t in sorted(d["dts"]):
        b = BNode()
        vg.add((pp, VEXT.datatypePartition, b))
        vg.add((b, VEXT.datatype, URIRef(t)))

vg.serialize(str(config.VOID_FILE), format="turtle")
print(f"wrote {config.VOID_FILE.name}: {len(vg)} triples")

# Values the model needs but a schema cannot give: tier ids, years, exporter names
vocab = {
    "tiers": [{"id": str(t).replace(config.TIER_NS, ""), "name": str(c)} for t, c in g.query(
        f'PREFIX ul: <{UL}> SELECT ?t ?c WHERE {{ ?t a ul:Tier ; ul:categoryName ?c }} ORDER BY ?t')],
    "years": sorted(int(y) for (y,) in g.query(
        f'PREFIX ul: <{UL}> SELECT DISTINCT ?y WHERE {{ ?t ul:year ?y }}')),
    "exporters": sorted(str(n) for (n,) in g.query(
        f'PREFIX ul: <{UL}> SELECT DISTINCT ?n WHERE {{ ?t ul:exportedBy ?c . ?c ul:name ?n }}')),
}
config.VOCAB_FILE.write_text(json.dumps(vocab, indent=1, ensure_ascii=False), encoding="utf-8")
print(f"wrote {config.VOCAB_FILE.name}: {len(vocab['tiers'])} tiers, {len(vocab['years'])} years, "
      f"{len(vocab['exporters'])} exporters")
if not vocab["tiers"]:
    print("WARNING: no tiers found. Rebuild the graph with the <#Tiers> block in trade-mapping.ttl.")
