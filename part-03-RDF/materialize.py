"""
Materialize the semiconductor trade knowledge graph using Morph-KGC.

Run from part-03-RDF/ with your existing .venv active:

    python materialize.py

Optional arguments:

    python materialize.py --mapping trade-mapping.ttl
    python materialize.py --knowledge tier-knowledge.ttl
    python materialize.py --out semiconductor-graph.nt
    python materialize.py --no-knowledge

The script:
1. Reads the PostgreSQL URL from the parent project's .env file.
2. Materializes trade-mapping.ttl using Morph-KGC.
3. Optionally merges the triples from tier-knowledge.ttl.
4. Writes the combined graph as N-Triples.

The output is a snapshot. Rerun the script after changing the
database or either input file.
"""

import argparse
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from rdflib import Graph
from sqlalchemy import create_engine, text


HERE = Path(__file__).resolve().parent
PROJECT_DIR = HERE.parent

# Your .env is in project_knowledge_representation/, one level above
# part-03-RDF/.
load_dotenv(PROJECT_DIR / ".env")

DATABASE_URL = os.getenv("DATABASE_URL")


def config(mapping, db_url):
    """Build the Morph-KGC configuration."""
    return (
        "[CONFIGURATION]\n"
        "logging_level=WARNING\n\n"
        "[Semiconductor]\n"
        f"mappings={mapping.as_posix()}\n"
        f"db_url={db_url}\n"
    )


def run(mapping, knowledge, out, include_knowledge=True):
    if not DATABASE_URL:
        sys.exit(
            "DATABASE_URL is missing from the .env file at:\n"
            f"{PROJECT_DIR / '.env'}"
        )

    if not mapping.is_file():
        sys.exit(f"R2RML mapping file not found: {mapping}")

    if include_knowledge and not knowledge.is_file():
        sys.exit(f"Knowledge file not found: {knowledge}")

    try:
        import morph_kgc
    except ImportError:
        sys.exit(
            "Morph-KGC is not installed in the active environment.\n"
            "Install it using the requirements instructions from your lab."
        )

    # Check the PostgreSQL connection before materializing.
    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        engine.dispose()
    except Exception as err:
        sys.exit(
            "Could not connect to PostgreSQL. Check Docker and DATABASE_URL.\n"
            f"Details: {err}"
        )

    start = time.time()

    try:
        print(f"Materializing R2RML mapping: {mapping.name}")

        graph = morph_kgc.materialize(
            config(mapping, DATABASE_URL)
        )

        mapped_count = len(graph)
        print(f"Generated {mapped_count:,} mapped triples.")

        if include_knowledge:
            print(f"Loading additional knowledge: {knowledge.name}")

            knowledge_graph = Graph()
            knowledge_graph.parse(str(knowledge), format="turtle")

            knowledge_count = len(knowledge_graph)
            graph += knowledge_graph

            print(f"Read {knowledge_count:,} knowledge triples.")

        # Create the output directory if necessary.
        out.parent.mkdir(parents=True, exist_ok=True)

        graph.serialize(destination=str(out), format="nt", encoding="utf-8")




    except Exception:
        import traceback
        traceback.print_exc()
        raise
        
        
        
    elapsed = time.time() - start

    print("\nMaterialization complete")
    print("------------------------")
    print(f"Mapped triples:     {mapped_count:,}")

    if include_knowledge:
        print(f"Knowledge triples:  {knowledge_count:,}")

    print(f"Unique total:       {len(graph):,}")
    print(f"Output:             {out}")
    print(f"Elapsed time:       {elapsed:.1f} seconds")


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--mapping",
        type=Path,
        default=HERE / "trade-mapping.ttl",
        help="R2RML mapping file",
    )

    parser.add_argument(
        "--knowledge",
        type=Path,
        default=HERE / "tier-knowledge.ttl",
        help="Additional Turtle knowledge or ontology file",
    )

    parser.add_argument(
        "--out",
        type=Path,
        default=HERE / "semiconductor-knowledge-graph.nt",
        help="Output N-Triples file",
    )

    parser.add_argument(
        "--no-knowledge",
        action="store_true",
        help="Materialize only the R2RML mapping",
    )

    args = parser.parse_args()

    run(
        mapping=args.mapping.resolve(),
        knowledge=args.knowledge.resolve(),
        out=args.out.resolve(),
        include_knowledge=not args.no_knowledge,
    )


if __name__ == "__main__":
    main()
