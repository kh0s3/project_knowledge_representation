#!/bin/sh
# Loads the three graph files (mounted at /data) into one read-only dataset called /semiconductor.
# N-Triples is valid Turtle, so the three files can simply be joined into one Turtle file.
set -e
mkdir -p /tmp/kg
: > /tmp/kg/all.ttl
for f in semiconductor-knowledge-graph.nt tier-knowledge.ttl ontology.ttl; do
  if [ ! -f "/data/$f" ]; then
    echo "ERROR: /data/$f not found. Mount the folder with the graph files at /data." >&2
    exit 1
  fi
  cat "/data/$f" >> /tmp/kg/all.ttl
  printf '\n' >> /tmp/kg/all.ttl
done
echo "loading $(wc -l < /tmp/kg/all.ttl) lines into /semiconductor"
cd /fuseki
exec ./fuseki-server --file=/tmp/kg/all.ttl --port=3030 /semiconductor
