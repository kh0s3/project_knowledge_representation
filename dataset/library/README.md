# Dataset Overview

This directory contains the data files used and generated throughout the progression of the project. To maintain version control and track the data transformations, the datasets are grouped into three distinct zip files representing different stages of our pipeline.

---

## Data Versions

### 1. `v0.zip` (Raw Data)
*   **Contents:** `worldwide economics`, `semiconductor prices`
*   **Description:** The original, untouched datasets sourced from Kaggle (Global Semiconductor Trade Network 2020–2025). This serves as the raw starting point before any profiling or KRR methodologies are applied.

### 2. `v1.zip` (Post-Profiling - Part 01)
*   **Contents:** `worldwide economics`, `semiconductor prices`
*   **Description:** The dataset after the initial profiling and cleaning phase (Part 01). This version resolves UN reporting dualities, drops physical weight anomalies, filters out unresolved entities, and isolates the temporal scope to the year 2024.

### 3. `v2.zip` (Post-Treatment - Part 02)
*   **Contents:** `worldwide economics`, `semiconductor prices`
*   **Description:** The finalized, minimized, and transformed dataset resulting from Part 02. In this version, data is structured for relational clarity:
    *   Calculated sums for distinct tier transactions per node.
    *   Recalculated total imports, total exports, and net trade balances based on the filtered 2024 data.

---

## Usage Instructions

*   **Active Dataset:** All graph materialization (Part 03), ontology mapping, and reasoning (Part 04 & 05) strictly use the data extracted from **`v2.zip`**. 
*   **Extraction:** When working with the codebase, ensure the contents of the zip files (specifically `v2`) are extracted directly into this `dataset/` root directory so the Python scripts can locate the CSVs correctly.