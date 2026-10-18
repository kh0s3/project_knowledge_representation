# Part 04: OWL Ontology Definition & Reasoning

This directory contains the formal OWL 2 ontology (`ontology.ttl`) defining the domain logic, class hierarchies, property constraints, and transitive rules for the semiconductor trade network. It serves as the structural rulebook for our Knowledge Graph.

---

## 1. Ontology Design (`ontology.ttl`)

The ontology defines the blueprint of the global supply chain using Semantic Web standards:
-   **Classes:** Core entities include `Country`, `TradeObservation`, and `Tier`. Countries are further classified into `SurplusCountry`, `DeficitCountry`, and `BalancedCountry`.
-   **Object Properties:** 
    -   `exportedBy`, `importedBy`, and `hasTier` (Functional properties linking trades to countries and tiers).
    -   `feeds` (A **TransitiveProperty** linking upstream tiers to downstream tiers).
-   **Data Properties:** Attributes like `year`, `tradeValueUsd`, `isoCode`, `netTradeBalanceUsd`, and `strategicRole`.
-   **Restrictions & Rules:**
    -   Qualified exact cardinality constraints (exactly 1 exporter, 1 importer, and 1 tier per trade).
    -   Strict `AllDisjointClasses` rules to ensure logical separation between core entities (a Country cannot be a Tier) and balance classifications (a Country cannot be both a Surplus and Deficit country).

---

## 3. Verification (Protégé)

To verify the logical consistency of the ontology before querying:
1.  Open **Protégé** (v5.6.4+).
2.  Load `ontology.ttl` and import `tier-knowledge.ttl` into the same workspace.
3.  Run a reasoner (such as HermiT) to verify that the transitive inference on the `feeds` property works correctly and that no disjointness contradictions exist in the class hierarchy.

---

## 3. Triplestore Integration (Apache Jena Fuseki)

To apply this ontology to the materialized data, you must load it into the triplestore engine set up in Part 03.

1.  **Start the Server:** Open your terminal, navigate to the Part 03 directory, and spin up Fuseki using the root environment variables:
    ```powershell
    cd part-03-RDF
    docker-compose --env-file ../.env up -d
    ```
2.  **Create a Dataset:** Navigate to `http://localhost:3030`, log in, and add a new persistent dataset (e.g., `scm`).
3.  **Upload the Unified Graph:** Upload the following three files sequentially:
    -   `ontology.ttl` (The rulebook defining classes and properties).
    -   `tier-knowledge.ttl` (The explicit background knowledge that connects the 5 Tiers together via the `feeds` property, ensuring the database understands the full supply chain loop).
    -   `semiconductor-knowledge-graph.nt` (The massive dataset of 46,000+ trade observations generated in Part 03).

---

## 4. Querying the Graph (`queries.txt`)

Once the graph is fully loaded in Fuseki, you can use the SPARQL scripts provided in `queries.txt` to answer the core analytical questions of this project:

-   **QUESTION 1:** Where are the massive streams of essential semiconductor parts flowing from dominant producer nations into countries that are unable to produce them locally and highly vulnerable to supply disruptions?
-   **QUESTION 2:** Which countries have an overall trade deficit, but are critical to the network because other nations depend on their specific tier exports?

---

## Data Flow

-   **Input:** The materialized graph (`.nt`) and tier facts from Part 03.
-   **Process:** 1. Define logical rules (`ontology.ttl`). 2. Verify rules in Protégé. 3. Merge data, facts, and rules inside Fuseki.
-   **Output:** A fully reasoned, queryable Knowledge Graph capable of answering complex SPARQL supply chain questions (`queries.txt`).