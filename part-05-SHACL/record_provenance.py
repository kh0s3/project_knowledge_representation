"""Record provenance for a SHACL validation run and its output report."""

import argparse
import hashlib
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from rdflib import DCTERMS, PROV, RDF, RDFS, XSD, Graph, Literal, Namespace, URIRef


HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
DEFAULT_DATA = PROJECT_ROOT / "part-03-RDF" / "semiconductor-knowledge-graph.nt"
DEFAULT_SHAPES = HERE / "semiconductor-shapes.ttl"
DEFAULT_REPORT = HERE / "output" / "validation-report.ttl"
DEFAULT_OUTPUT = HERE / "output" / "provenance.ttl"
BASE = "https://ul.edu.lb/kr/id/semiconductor/"


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def package_version(name):
    try:
        return version(name)
    except PackageNotFoundError:
        return "unknown"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--shapes", type=Path, default=DEFAULT_SHAPES)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    for path in (args.data, args.shapes, args.report):
        if not path.is_file():
            parser.error(f"input file not found: {path}")

    now = datetime.now(timezone.utc).replace(microsecond=0)
    timestamp = now.strftime("%Y%m%dT%H%M%SZ")
    run = URIRef(f"{BASE}activity/shacl-validation-{timestamp}")
    agent = URIRef(f"{BASE}software/validate_graph.py")

    graph = Graph()
    graph.bind("prov", PROV)
    graph.bind("dcterms", DCTERMS)
    graph.bind("rdfs", RDFS)
    graph.bind("xsd", XSD)

    graph.add((agent, RDF.type, PROV.SoftwareAgent))
    graph.add((agent, RDFS.label, Literal("Part 5 SHACL validation script")))
    graph.add((agent, DCTERMS.identifier, Literal(f"pySHACL {package_version('pyshacl')}")))

    graph.add((run, RDF.type, PROV.Activity))
    graph.add((run, RDFS.label, Literal("SHACL validation of the semiconductor trade graph")))
    graph.add((run, PROV.startedAtTime, Literal(now.isoformat(), datatype=XSD.dateTime)))
    graph.add((run, PROV.endedAtTime, Literal(now.isoformat(), datatype=XSD.dateTime)))
    graph.add((run, PROV.wasAssociatedWith, agent))

    entities = (
        ("data-graph", args.data, "N-Triples RDF graph"),
        ("shapes", args.shapes, "SHACL shapes"),
        ("validation-report", args.report, "SHACL validation report"),
    )
    for key, path, label in entities:
        entity = URIRef(f"{BASE}entity/{key}/{sha256(path)}")
        graph.add((entity, RDF.type, PROV.Entity))
        graph.add((entity, RDFS.label, Literal(label)))
        graph.add((entity, DCTERMS.title, Literal(path.name)))
        graph.add((entity, DCTERMS.identifier, Literal(f"sha256:{sha256(path)}")))
        graph.add((entity, DCTERMS.format, Literal(path.suffix.lstrip("."))))
        if key != "validation-report":
            graph.add((run, PROV.used, entity))
        else:
            graph.add((entity, PROV.wasGeneratedBy, run))

    report_entity = next(
        entity for entity, _, _ in graph.triples((None, DCTERMS.title, Literal(args.report.name)))
    )
    graph.add((report_entity, PROV.wasDerivedFrom, URIRef(
        f"{BASE}entity/data-graph/{sha256(args.data)}"
    )))
    graph.add((report_entity, PROV.wasDerivedFrom, URIRef(
        f"{BASE}entity/shapes/{sha256(args.shapes)}"
    )))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    graph.serialize(destination=str(args.out), format="turtle")
    print(f"Wrote {len(graph)} provenance triples to {args.out}")
    print(f"Validation activity: {run}")
    print(f"pySHACL version: {package_version('pyshacl')}")
    print("The metadata hashes the exact data, shapes, and report files used.")


if __name__ == "__main__":
    main()
