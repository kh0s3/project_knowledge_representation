"""Validate the Part 3 semiconductor RDF graph against this part's SHACL shapes."""

import argparse
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

from pyshacl import validate
from rdflib import Graph, Namespace, RDF


HERE = Path(__file__).resolve().parent
DEFAULT_DATA = HERE.parent / "part-03-RDF" / "semiconductor-knowledge-graph.nt"
DEFAULT_SHAPES = HERE / "semiconductor-shapes.ttl"
SH = Namespace("http://www.w3.org/ns/shacl#")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA, help="RDF graph to validate")
    parser.add_argument("--shapes", type=Path, default=DEFAULT_SHAPES, help="SHACL shapes Turtle file")
    parser.add_argument(
        "--report",
        type=Path,
        default=HERE / "output" / "validation-report.ttl",
        help="Path for the full Turtle validation report",
    )
    args = parser.parse_args()

    for path in (args.data, args.shapes):
        if not path.is_file():
            parser.error(f"input file not found: {path}")

    data = Graph()
    data.parse(str(args.data), format="nt")
    shapes = Graph()
    shapes.parse(str(args.shapes), format="turtle")

    print(f"Data graph: {args.data} ({len(data):,} triples)")
    print(f"Shapes:     {args.shapes} ({len(shapes):,} triples)")

    started = time.perf_counter()
    conforms, report_graph, _ = validate(
        data_graph=data,
        shacl_graph=shapes,
        inference="none",
        advanced=True,
        abort_on_first=False,
    )
    elapsed = time.perf_counter() - started

    results = list(report_graph.subjects(RDF.type, SH.ValidationResult))
    severity_counts = Counter(report_graph.value(result, SH.resultSeverity) for result in results)
    violations = severity_counts[SH.Violation]
    warnings = severity_counts[SH.Warning]
    infos = severity_counts[SH.Info]

    print(
        f"SHACL conforms: {conforms}; "
        f"{violations} violation(s), {warnings} warning(s), {infos} info result(s); "
        f"validated in {elapsed:.2f}s."
    )

    grouped = defaultdict(list)
    for result in results:
        severity = report_graph.value(result, SH.resultSeverity)
        message = report_graph.value(result, SH.resultMessage)
        focus = report_graph.value(result, SH.focusNode)
        path = report_graph.value(result, SH.resultPath)
        label = severity.rsplit("#", 1)[-1] if severity else "Unknown"
        grouped[(label, str(message), str(path) if path else "")].append(str(focus))

    severity_order = {"Violation": 0, "Warning": 1, "Info": 2, "Unknown": 3}
    for (label, message, path), focus_nodes in sorted(
        grouped.items(), key=lambda entry: (severity_order.get(entry[0][0], 4), -len(entry[1]), entry[0][1])
    ):
        focus_examples = ", ".join(sorted(focus_nodes)[:3])
        path_text = f"; path={path}" if path else ""
        remainder = f", +{len(focus_nodes) - 3} more" if len(focus_nodes) > 3 else ""
        print(
            f"  {label}: {len(focus_nodes)} result(s){path_text}; "
            f"{message}; focus examples: {focus_examples}{remainder}"
        )

    args.report.parent.mkdir(parents=True, exist_ok=True)
    report_graph.serialize(destination=str(args.report), format="turtle")
    print(f"Full validation report: {args.report}")

    if violations:
        print("GATE: FAIL (one or more SHACL Violations).")
        return 1
    if warnings:
        print("GATE: PASS (warnings are reported for review).")
    else:
        print("GATE: PASS.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
