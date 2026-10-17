# Part 3: RDF graph and Apache Jena Fuseki

This guide explains how to start Fuseki with Docker, load the semiconductor
knowledge graph, run the saved SPARQL queries, and optionally rebuild the graph
from the source CSVs and PostgreSQL database.

## 1. Understand the files

| File | Purpose | Do you run it? |
| --- | --- | --- |
| `docker-compose.yml` | Defines PostgreSQL and the Fuseki containers and persistent volumes. | Run its services with `docker compose`. |
| `semiconductor-knowledge-graph.nt` | Materialized RDF graph in N-Triples format; this is what Fuseki loads. | Upload this file to Fuseki. |
| `trade-mapping.ttl` | R2RML mapping from PostgreSQL tables to trade, country, and tier RDF facts. | `materialize.py` reads it; do not upload it as the trade graph. |
| `tier-knowledge.ttl` | Extra tier-feed relations and vocabulary facts added to the graph. | `materialize.py` reads it; it is already included in the generated `.nt` graph. |
| `materialize.py` | Uses Morph-KGC to map PostgreSQL data, adds `tier-knowledge.ttl`, and generates the `.nt` file. | Run only when rebuilding the graph. |
| `load_database.py` | Loads the source CSV files into PostgreSQL tables. | Run only when loading or refreshing the source database. |
| `queries.rq` | Collection of standalone SPARQL query examples. | Copy and run one query at a time in Fuseki. |

The normal data flow is:

```text
source CSVs -> PostgreSQL -> trade-mapping.ttl + tier-knowledge.ttl
            -> materialize.py -> semiconductor-knowledge-graph.nt
            -> Fuseki/TDB2 -> SPARQL queries
```

The existing `.nt` graph is already materialized. To try Fuseki, you do not
need to run Python or start PostgreSQL; you only need Docker and the `.nt`
file.

## 2. Prerequisites and local no-password access

1. Install and start Docker Desktop. Confirm Docker Compose is available:

   ```powershell
   docker --version
   docker compose version
   ```

2. Open PowerShell at the repository root (the folder containing
   `.gitignore` and `part-03-RDF`). No Fuseki password or `.env` setting is
   needed to start the local Fuseki service.

For this course project, `fuseki-shiro.ini` disables authentication for the
Fuseki UI and API. Docker Compose binds port 3030 to `127.0.0.1`, so access is
limited to this computer. Do not change that binding or expose this
no-authentication service to a network. The repository-root `.env` is only
needed when you rebuild the RDF graph using PostgreSQL; it may contain
`DATABASE_URL` and `LOCAL_PATH_PROJECT` for that separate workflow.

## 3. Get the Fuseki image and start the service

This project uses the pinned published image `stain/jena-fuseki:5.1.0`.
There is no project Dockerfile to build: Docker Compose downloads (pulls) the
existing Fuseki image. This avoids maintaining a custom image that only wraps
the upstream Fuseki server.

From the repository root, pre-download the image:

```powershell
docker compose -f .\part-03-RDF\docker-compose.yml pull fuseki
```

Start Fuseki:

```powershell
docker compose -f .\part-03-RDF\docker-compose.yml up -d fuseki
```

Check the container status and startup logs:

```powershell
docker compose -f .\part-03-RDF\docker-compose.yml ps
docker compose -f .\part-03-RDF\docker-compose.yml logs fuseki
```

The service uses TDB2 storage in the named Docker volume
`fuseki-semiconductor` and exposes Fuseki only on this computer at port 3030.
The mounted `fuseki-shiro.ini` disables authentication; the service must remain
bound to localhost. PostgreSQL is not started by the command above and is not
needed to query the already-generated graph.

If Fuseki was already running before this no-password setup, recreate its
container to apply the new configuration (this preserves the named data volume):

```powershell
docker compose -f .\part-03-RDF\docker-compose.yml up -d --force-recreate fuseki
```

## 4. Open Fuseki and load the graph

1. Browse to <http://localhost:3030>.
2. No sign-in is required. Select the `semiconductor` dataset.
3. Open its upload page/control and choose:
   `part-03-RDF/semiconductor-knowledge-graph.nt`.
4. Upload the file as N-Triples (`.nt`) to the **default graph**.
5. Wait for the upload to finish before running queries.

Do not upload `trade-mapping.ttl` as the data graph. It is a database mapping
recipe, not the materialized trade observations. Do not separately upload
`tier-knowledge.ttl` when loading the generated `.nt` file: those knowledge
triples are already merged into it by `materialize.py`.

### Check that upload worked

In the Fuseki UI, open the `semiconductor` query page and run:

```sparql
SELECT (COUNT(*) AS ?tripleCount)
WHERE {
  ?subject ?predicate ?object
}
```

The existing graph should contain approximately 46,000 triples. The exact
count may vary if the graph has been regenerated.

## 5. Run the saved SPARQL queries

The dataset query endpoint is:

```text
http://localhost:3030/semiconductor/sparql
```

To run a query in the web UI:

1. Open <http://localhost:3030>.
2. Select the `semiconductor` dataset and open its query page.
3. Open `part-03-RDF/queries.rq` in VS Code or another text editor.
4. Copy the three `PREFIX` lines at the top and **one complete query**,
   including its `SELECT`, `WHERE`, and any `GROUP BY`, `ORDER BY`, or
   `LIMIT` clauses.
5. Paste the selection into the Fuseki query editor and execute it.

`queries.rq` contains 15 separate queries. Run them individually; do not
paste the whole file as one SPARQL query. They cover class counts, large
trade flows, country and tier trade summaries, supply-chain traversal,
bottlenecks, deficit countries, USA import dependence, deficit countries
that also export tiers, supplier concentration, country-profile consistency,
and strategic-role conflicts.

The USA-dependence query defines dependence as the USA's share of each
country's **observed 2024 imports in this graph**. It does not measure all of
that country's imports. Likewise, the supplier-concentration query considers
only suppliers represented in the graph. Country profile balances and mapped
trade observations come from separate sources, so a profile-deficit country
can still appear as an exporter of a tier in the observed data.

## 6. Refresh the graph after changing source data (optional)

Skip this section if you only need to query the existing
`semiconductor-knowledge-graph.nt`.

The database loader replaces the `trades`, `countries`, and `tiers` tables.
Run it only when you intend to reload those tables from the source CSV files.

1. In the repository-root `.env`, confirm `DATABASE_URL` points to the
   PostgreSQL service defined in `part-03-RDF/docker-compose.yml` and
   `LOCAL_PATH_PROJECT` points to the repository root containing `dataset`.
   No Fuseki password variable is used.
2. From the repository root, start PostgreSQL:

   ```powershell
   docker compose -f .\part-03-RDF\docker-compose.yml up -d postgres
   ```

3. Load the CSV files into PostgreSQL. Confirm the expected CSV files exist
   under `dataset` first:

   ```text
   dataset/edges_semiconductor_trade.csv
   dataset/nodes_countries.csv
   dataset/supply_chain_tiers.csv
   ```

   Run:

   ```powershell
   python .\part-03-RDF\load_database.py
   ```

   This operation replaces the three database tables.

4. Generate a fresh graph. `materialize.py` reads `DATABASE_URL` from the
   repository-root `.env` and defaults to the mapping and knowledge files
   in `part-03-RDF`:

   ```powershell
   python .\part-03-RDF\materialize.py
   ```

   On success, it writes
   `part-03-RDF/semiconductor-knowledge-graph.nt`.

5. In the Fuseki UI, clear/delete the old contents of the dataset's default
   graph before uploading the regenerated `.nt` file. This avoids keeping
   triples that no longer occur in the new snapshot.
6. Upload the regenerated `.nt` file using the steps in section 4, then
   rerun the queries.

The `.nt` file is a snapshot. Re-run `materialize.py` after changes to the
source database, `trade-mapping.ttl`, or `tier-knowledge.ttl`. If the
PostgreSQL tables already contain the intended data, steps 2 and 3 are not
needed; regenerate the graph directly.

## 7. Stop Fuseki and understand data persistence

From the repository root, stop the containers:

```powershell
docker compose -f .\part-03-RDF\docker-compose.yml down
```

This stops and removes the containers but preserves the named volumes.
Fuseki's loaded graph survives normal container stop/start operations.

To stop only Fuseki without stopping PostgreSQL:

```powershell
docker compose -f .\part-03-RDF\docker-compose.yml stop fuseki
```

To delete both Compose volumes (including the Fuseki graph and PostgreSQL
data), run:

```powershell
docker compose -f .\part-03-RDF\docker-compose.yml down --volumes
```

This last command is destructive. Do not run it unless you intend to erase
the stored database and RDF dataset.

## Notes on reasoning and inference

- The graph contains explicit classes such as `ul:DeficitCountry`; the saved
  queries use these explicit triples and do not rely on RDFS inference.
- `tier-knowledge.ttl` describes tier-to-tier `ul:feeds` relations. It does
  not encode a specific country's manufacturing route.
- Country-profile export/import totals should not automatically be treated
  as sums of only the mapped trade observations in this graph.
