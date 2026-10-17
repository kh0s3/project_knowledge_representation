# Part 5: SHACL validation and provenance

Part 5 validates the RDF data graph produced by Part 3 using the SHACL shapes
in this directory. The Part 4 ontology is the model used to design and review
the shapes; the validator does **not** load the ontology as an input. It loads
the Part 3 N-Triples graph and `semiconductor-shapes.ttl` only.

No database, Docker, or Fuseki service is needed to run validation when the
materialized graph already exists.

## Files and inputs

| Path | Purpose |
| --- | --- |
| `part-03-RDF/semiconductor-knowledge-graph.nt` | Part 3 RDF data graph being checked (N-Triples). |
| `part-05-SHACL/semiconductor-shapes.ttl` | SHACL rules applied to the data graph (Turtle). |
| `part-05-SHACL/validate_graph.py` | Runs pySHACL, prints grouped results, writes the full report, and fails on any Violation. |
| `part-05-SHACL/record_provenance.py` | Records the input, shapes, report, timestamp, software version, and hashes after validation. |
| `part-05-SHACL/output/validation-report.ttl` | Generated full SHACL report (not tracked by Git). |
| `part-05-SHACL/output/provenance.ttl` | Generated PROV-O provenance (not tracked by Git). |
| `.github/workflows/shacl-gate.yml` | GitHub Actions gate using the same validator and default inputs. |

The shapes include ontology-aligned constraints as well as project data-quality
rules. For example, the year range and positive trade value are additional
checks, not axioms from the Part 4 ontology. Review the shape messages and
severities in `semiconductor-shapes.ttl` when deciding whether a result is a
data issue or a rule that needs revision.

The Part 4 ontology files are useful design references, but the validator does
not import or load them. In particular, deleting the generated
`part-04-ontology/output/ontology_treated.ttl` file does not affect validation.
If ontology reference files change, the workflow can still run, but only the
Part 3 graph and Part 5 shapes are inputs to the check.

## Before you run

1. Open PowerShell at the repository root (the directory containing `.gitignore`,
   `part-03-RDF`, and `part-05-SHACL`).
2. Confirm that the graph and shapes exist:

   ```powershell
   Test-Path .\part-03-RDF\semiconductor-knowledge-graph.nt
   Test-Path .\part-05-SHACL\semiconductor-shapes.ttl
   ```

   Both commands should print `True`. No Part 4 ontology output file is
   required to run `validate_graph.py`.
3. Use the project Python 3.12 virtual environment. If it has not been created,
   create it from the repository root:

   ```powershell
   py -3.12 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

   If PowerShell blocks activation, run the validator directly with
   `.\.venv\Scripts\python.exe` instead of activating the environment.
4. Install only the validation dependencies if they are missing:

   ```powershell
   python -m pip install pyshacl==0.40.1 rdflib==7.6.0
   ```

   To prepare the full project environment instead, use
   `python -m pip install -r .\requirement\requirements.txt`.

If the Part 3 graph is missing or out of date, regenerate it by following
[Part 3's graph refresh instructions](../part-03-RDF/README.md) (section 6).
That requires the project's PostgreSQL/database setup. Do not use the Fuseki
upload file `trade-mapping.ttl` as validation data; the validator expects the
materialized `.nt` graph.

## Run the validation

From the repository root, use the defaults:

```powershell
python .\part-05-SHACL\validate_graph.py
if ($LASTEXITCODE -ne 0) { throw "SHACL validation failed (exit $LASTEXITCODE)" }
```

The defaults are:

- Data: `part-03-RDF/semiconductor-knowledge-graph.nt` (read as N-Triples).
- Shapes: `part-05-SHACL/semiconductor-shapes.ttl` (read as Turtle).
- Report: `part-05-SHACL/output/validation-report.ttl` (written as Turtle).

You can override any path, for example:

```powershell
python .\part-05-SHACL\validate_graph.py `
  --data .\part-03-RDF\semiconductor-knowledge-graph.nt `
  --shapes .\part-05-SHACL\semiconductor-shapes.ttl `
  --report .\part-05-SHACL\output\validation-report.ttl
```

The validator reports the number of input triples, findings grouped by
severity/message, elapsed validation time, and report path. Exit status is `0`
when there are no Violations (warnings may still exist), and `1` when at least
one Violation exists. Missing inputs or parsing errors also stop the run; fix
those errors rather than treating the result as a successful validation.

## Check that the output is correct

After the command finishes, check all of the following:

1. The console prints the expected data and shapes paths and a triple count.
   The current checked-in graph has about 46,000 triples; the exact count can
   change when Part 3 is regenerated.
2. The summary reports the counts for Violations, Warnings, and Info results,
   then prints `GATE: PASS` or `GATE: FAIL`.
3. The printed report path exists and its timestamp is current. Open
   `part-05-SHACL/output/validation-report.ttl` in VS Code to inspect each
   result's focus node, path, severity, and message. The Turtle report has a
   `sh:ValidationReport` node and `sh:ValidationResult` entries.
4. Use the exit status as the gate result. `sh:conforms false` in the report
   does not by itself mean the gate failed: SHACL also sets it to false for
   warnings, while this project's gate fails only on Violations. A warning-only
   report therefore has a nonzero count of warnings, zero Violations, and
   `GATE: PASS` / exit status `0`.

For the graph currently in the repository, the expected baseline is **0
Violations and 51 Warnings**: 49 country strategic-role/balance mismatches and
2 country profiles without a display name. Those warnings are reported for
review and do not block the gate. If the graph or shapes have changed, counts
may differ; review the new report rather than assuming the baseline still
applies. A successful run means the rules passed as currently written; it does
not establish that the rules themselves are complete or that every warning is
acceptable.

When a result is unexpected, use its message and focus node to decide whether
to correct the Part 3 source data or revise the corresponding SHACL rule. Do
not suppress a result by lowering severity until it has been triaged and the
reason is documented in the shapes.

## Record provenance

Run provenance after validation so it hashes the newly generated report:

```powershell
python .\part-05-SHACL\record_provenance.py
```

The script writes `part-05-SHACL/output/provenance.ttl`, containing the exact
input graph, shapes, report, validation activity and time, pySHACL version, and
SHA-256 file hashes. If validation inputs or report change, rerun provenance.
This covers the validation run; it does not capture which CSV rows or database
snapshot were used to create the Part 3 graph.

## GitHub Actions gate

The workflow at `.github/workflows/shacl-gate.yml` runs the same validator on
pushes and pull requests that change the graph, Part 4 ontology, Part 5 files,
or validation requirements. It also supports manual runs from the Actions
tab. A Violation fails the job; warnings pass. The report is generated on the
runner, while the job log retains the summary. Configure the workflow's
`validate` job as a required status check in repository branch protection or
a ruleset if merges must be blocked when the check fails.

## Check the SHACL gate

The workflow runs `python part-05-SHACL/validate_graph.py`, so running that
same command locally checks the validation step used by CI:

```powershell
python .\part-05-SHACL\validate_graph.py
$gateExitCode = $LASTEXITCODE
"SHACL gate exit code: $gateExitCode"
```

Exit code `0` means the gate passes (even if the report contains Warnings);
exit code `1` means one or more Violations were found. This local check does
not run GitHub Actions itself.

To verify that the gate rejects a bad graph without changing the project graph,
create a temporary N-Triples input with an incomplete trade observation and
run the validator with that graph:

```powershell
$badGraph = Join-Path $env:TEMP "shacl-gate-bad-sample.nt"
$testReport = Join-Path $env:TEMP "shacl-gate-test-report.ttl"
'<https://example.org/test-observation> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <https://ul.edu.lb/kr/scm#TradeObservation> .' | Set-Content -Path $badGraph -Encoding ascii
python .\part-05-SHACL\validate_graph.py --data $badGraph --report $testReport
$gateExitCode = $LASTEXITCODE
"Expected 1 (failure); got $gateExitCode"
Remove-Item $badGraph, $testReport -ErrorAction SilentlyContinue
if ($gateExitCode -ne 1) { throw "The negative gate test failed: expected exit code 1, got $gateExitCode" }
```

For an end-to-end GitHub Actions check:

1. Ensure the workflow `.github/workflows/shacl-gate.yml` and the Part 5 files
   are included in a commit and pushed to GitHub.
2. Open the repository's **Actions** tab and select **SHACL gate**. Use
   **Run workflow** to start a manual run, or push a change to one of the paths
   listed in the workflow or open a pull request containing such a change.
3. Open the run and inspect the `Validate the semiconductor graph` step. A
   zero-Violation run should be green; any Violation or parsing/input error
   should make it red. Warnings are printed but do not fail the job.
4. To block merges, configure the `validate` job as a required status check in
   the repository's branch protection or ruleset.

The GitHub workflow only exists after it is committed and pushed; a local run
alone cannot confirm GitHub's runner, permissions, or Actions configuration.

## Use with Fuseki

SHACL validation is a local Python step and does not require Fuseki or Docker.
Run it before publishing the Part 3 graph. If there are Violations, resolve or
explicitly reconsider them before upload, and review warnings as well. The
validation report and provenance are separate from the trade graph; upload
them to a separate named graph only if you specifically need to query
validation history in Fuseki.
