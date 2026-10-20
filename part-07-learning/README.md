# Part 6: Learning Over the Semiconductor Knowledge Graph

Predict missing trade relationships in the semiconductor knowledge graph using link prediction with the TransE model.

## What This Part Does

Given trade data between countries (exporter → importer) with associated tiers, we can ask:
- **Q1**: "What tier does China export to Germany?"
- **Q2**: "Which countries export Memory chips to USA?"
- **Q3**: "Where does Taiwan export Wafers to?"

The model learns from the trade graph and predicts likely answers ranked by confidence.

## Setup

```powershell
cd part-06-learning
pip install torch torch_geometric pykeEN numpy pandas
```

## How to Run

### Step 1: Build the graph

```powershell
python build_graph.py --split random --test_ratio 0.1 --seed 42
```

This creates `data/semiconductor-graph.pt` and `data/hidden-edges.pt`.

### Step 2: Query the model

**Option A: Interactive mode** (recommended)
```powershell
python link_prediction.py --query
```

Then type queries at the prompt:
```
Q1 CHN DEU        # What tier does China export to Germany?
Q2 USA Tier_3B_Memory    # Which countries export Memory chips to USA?
Q3 TWN Tier_2_Wafers     # Where does Taiwan export Wafers to?
quit              # Exit
```

**Option B: Batch evaluation** (evaluates all 3 query patterns)
```powershell
python link_prediction.py
```

## Query Format

| Query | Format | Example |
|-------|--------|---------|
| Q1 | `Q1 EXPORTER IMPORTER` | `Q1 CHN DEU` |
| Q2 | `Q2 IMPORTER TIER` | `Q2 USA Tier_3B_Memory` |
| Q3 | `Q3 EXPORTER TIER` | `Q3 TWN Tier_2_Wafers` |

**Available country codes**: CHN (China), DEU (Germany), USA, TWN (Taiwan), JPN (Japan), KOR (South Korea), etc.

**Available tiers**:
- Tier_1_Equipment
- Tier_2_Wafers
- Tier_3A_Logic_Processors
- Tier_3B_Memory
- Tier_3C_Other_ICs

## Output

Results show percentages (softmax confidence) for top candidates:

```
Q1 CHN DEU

Question: What tier does CHN export to DEU?
Model ranking:
  1. Tier 3A Logic Processors (35.2%)
  2. Tier 3C Other ICs (21.8%)
  3. Tier 3B Memory (19.1%)
  4. Tier 1 Equipment (14.3%)
  5. Tier 2 Wafers (9.6%)
```

## Split Modes

Use `--split` to control which edges are hidden for testing:

| Mode | What It Hides | Use Case |
|------|---------------|----------|
| `random` | Random 10% of edges | General link prediction |
| `by_tier` | ALL edges of 1 tier | Test generalization to unseen tier |
| `by_country` | Edges of some countries | Test generalization to unseen countries |

```powershell
# Random split (default)
python build_graph.py --split random

# Hide all Tier_3A_Logic_Processors edges
python build_graph.py --split by_tier

# Hide edges of 20% of countries
python build_graph.py --split by_country --test_ratio 0.2
```

## Files

| File | Purpose |
|------|---------|
| `build_graph.py` | Builds graph from CSV, hides edges for testing |
| `link_prediction.py` | TransE model for 3 query patterns |
| `learning_utils.py` | Split and scoring utilities |
| `data/semiconductor-graph.pt` | Training graph |
| `data/hidden-edges.pt` | Hidden edges for evaluation |

## Evaluation Metrics

- **MRR** (Mean Reciprocal Rank): 1.0 = perfect, higher is better
- **Hits@5/10**: Share of correct answers in top 5/10 predictions
- **Popularity baseline**: Simple counting (most common answer). If model beats this, it learned meaningful patterns.