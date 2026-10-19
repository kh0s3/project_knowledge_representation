# Part 05: SHACL Validation & Provenance

This directory contains the SHACL shape definitions, the local validation runner, and PROV-O provenance recording scripts. This phase serves as an automated data quality gate, ensuring the materialized RDF graph complies with structural and business logic constraints before publication or querying.

---

## 1. SHACL Validation Gate

Handled by validate_graph.py and semiconductor-shapes.ttl, this step strictly evaluates the Part 03 N-Triples graph against custom SHACL shapes. 

-   *Decoupled Architecture:* The validator runs entirely locally using pySHACL and does not require Docker, Fuseki, or the Part 04 OWL ontology to function. It checks the data graph (semiconductor-knowledge-graph.nt) directly against the shapes.
-   *Strict vs. Flexible Rules:* 
    -   *Violations (Exit Code 1):* Critical structural errors (e.g., missing mandatory properties, wrong data types) that will fail the validation gate.
    -   *Warnings (Exit Code 0):* Pragmatic data quality flags (e.g., expected business logic mismatches) that are reported for review but do not block the gate.
-   *Current Baseline:* The validated 2024 graph explicitly expects *0 Violations and 51 Warnings* (49 country strategic-role/balance mismatches, and 2 country profiles without display names).

## 2. Provenance Tracking

Handled by record_provenance.py, this script ensures reproducibility and traceability for the validation process.
-   *PROV-O Audit Trail:* Generates provenance.ttl immediately after a successful validation.
-   *Immutability Checks:* Captures SHA-256 file hashes of the input graph, the shapes file, and the resulting validation report, alongside the execution timestamp and pySHACL software version.

## 3. CI/CD Integration

The repository enforces this validation automatically via GitHub Actions:
-   *Workflow (shacl-gate.yml):* Runs the local validation script on pushes and pull requests affecting the graph or SHACL files.
-   *Protection:* Acts as a required status check. A single SHACL Violation will fail the pipeline and block merges, ensuring malformed triples never enter the main project trunk.

---

## Data Flow & Execution

-   *Input:* The materialized graph (part-03-RDF/semiconductor-knowledge-graph.nt) and the rule definitions (semiconductor-shapes.ttl).
-   *Process:* 
    1. Run the gate: python .\part-05-SHACL\validate_graph.py
    2. Record the run: python .\part-05-SHACL\record_provenance.py
-   *Output:* 
    -   output/validation-report.ttl (The detailed pySHACL constraint report).
    -   output/provenance.ttl (The PROV-O execution hash record).