# Part 02: Data Treatment & Minimization

This directory handles the quantitative data treatment required to transform the clean `v1` dataset into a minimized, highly structured `v2` baseline ready for RDF graph materialization. 

---

## 1. Edge Transformation
Handled by `transformation_edges.py`, this step minimizes the transaction records to create a clean, distinct set of network edges:
-   **Country Group Filtering:** Explicitly dropped aggregate regional groups and non-standard territories to prevent the creation of artificial, distorted trade edges. The dropped ISO codes are: `_X`, `X1`, `E19`, `A59`, `O19`, `A79`, `F19`, `ATA`, `BVT`, `HMD`, `IOT`, `ATF`, `UMI`.
-   **Tier Aggregation:** Calculated the sums of distinct transactions for each specific semiconductor tier between the same exporter and importer nodes.
-   **Data Minimization:** By grouping the records by exporter, importer, tier, and year (2024), we reduced multiple granular rows into single, unified trade flows representing the total annual trade value.

---

## 2. Node Transformation
Handled by `transformation_nodes.py`, this step rebuilds the country profiles based on the newly minimized edges:
-   **Country Group Filtering:** Applied the exact same exclusion list (`_X`, `X1`, `E19`, `A59`, etc.) to ensure these aggregate entities are completely removed from the final country profiles, leaving only valid national nodes.
-   **Trade Metric Recalculation:** Computed the true `totalImportUsd` and `totalExportUsd` for each valid country node using the cleaned 2024 edge data.
-   **Balance Recalculation:** Derived each nation's net trade balance after all changes to ensure the node-level data perfectly matches the edge-level data.

---

## Data Flow

-   **Input:** Clean `v1` data files generated in Part 01.
-   **Process:** Python data transformations (`transformation_edges.py` and `transformation_nodes.py`).
-   **Output:** Generates the minimized `v2` datasets (CSV files in `./part-02-treatment/output`, later arranged in the `v2.zip` file), serving as the direct input source for Part 03.