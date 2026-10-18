# Part 01: Data Profiling & Cleaning

This directory handles the raw dataset extraction, general profiling, and deep cleaning required to convert UN trade records into a sanitized baseline. This phase combines manual dataset refinement using OpenRefine with automated Python rule checks.

---

## 1. Manual Changes (OpenRefine)

Initial data reduction and standardization were performed manually using OpenRefine on the raw `v0` dataset:
*   **Temporal Scope:** Filtered the dataset exclusively for the year **2024** to establish a focused baseline for the KRR model.
*   **Weight Dropping:** Removed physical weight metrics entirely due to missing, zero-value, or rounded inaccuracies, establishing **USD Trade Value** as the sole weight metric.
*   **Entity Cleanup:** Filtered out unresolved aggregate dummy codes (e.g., `_X` / "Areas, nes") to prevent distorted "super-nodes" in the network. Standardized country names and ISO alpha-3 codes.

---

## 2. Automated Rule Checks

Following the manual OpenRefine cleanup, a suite of 5 specific data-profiling rule checks were executed to enforce logical consistency:

1.  **Tier Description Consistency:** Validated that every trade record accurately aligns with one of the predefined semiconductor supply chain tiers.
2.  **Irreflexive Trades:** Scanned for and removed illogical self-loops (e.g., a country reporting an export to itself).
3.  **Check for Trade Values:** Ensured all recorded trade flows possess a strictly positive, non-zero USD trade value.
4.  **Mirror Data Check (Resolving UN Duality):** Raw UN data contains dual perspectives (both the exporter and importer report the same transaction, often with discrepancies). We solved this by **flipping import records** to match the export perspective and removing the resulting duplicates, creating a single, unified source of truth for each trade flow.
5.  **Check for Orphan Nodes:** Verified network integrity by ensuring no isolated country nodes exist without at least one valid trade link.

---

## Data Flow

*   **Input:** Raw data from `dataset/v0.zip`.
*   **Process:** Python general profiling (generalProfiling.py), the 5 rule checks (rule_checks.py), mirror and duplicate data fix (flippingImport.py) and OpenRefine manual cleaning (remove weight and select )
*   **Output:** Generates the clean `v1` datasets (csv in ./part-01-profiling/output later on arranged in v1 zip file), staging the environment for database minimization and transformation in Part 02.