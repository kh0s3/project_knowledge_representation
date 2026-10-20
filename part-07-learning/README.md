# Part 7: Learning Over the Semiconductor Knowledge Graph

Predict missing trade relationships in the semiconductor knowledge graph using link prediction with the TransE model.

## What This Part Does

Given trade data between countries (exporter → importer) with associated tiers, we can ask:
- **Q1**: "What tier does China export to Germany?"
- **Q2**: "Which countries export Memory chips to USA?"
- **Q3**: "Where does Taiwan export Wafers to?"

The model learns from the trade graph and predicts likely answers ranked by confidence.

## Setup

```powershell
cd part-07-learning
pip install torch torch_geometric pykeen numpy pandas flask
```

## How to Run

### Option A: Web UI (Recommended)

Start the web interface:

```powershell
python ui.py
```

Then open `http://localhost:5000` in your browser. The UI allows you to:
- Select query type Q1, Q2, or Q3
- Enter parameters via form fields
- View results with confidence percentages

### Option B: Command Line - Interactive Mode

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

### Option C: Batch Evaluation

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

## Docker

Build and run with Docker:

```powershell
docker build -t part7-learning .
docker run -p 5000:5000 part7-learning
```

Then open `http://localhost:5000` in your browser.

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

## Files

| File | Purpose |
|------|---------|
| `build_graph.py` | Builds graph from CSV, hides edges for testing |
| `link_prediction.py` | TransE model for 3 query patterns |
| `learning_utils.py` | Split and scoring utilities |
| `ui.py` | Flask web interface for querying |
| `templates/index.html` | HTML template for web UI |
| `data/semiconductor-graph.pt` | Training graph |
| `data/hidden-edges.pt` | Hidden edges for evaluation |
| `Dockerfile` | Docker configuration for this part |

## Evaluation Metrics

- **MRR** (Mean Reciprocal Rank): 1.0 = perfect, higher is better
- **Hits@5/10**: Share of correct answers in top 5/10 predictions
- **Popularity baseline**: Simple counting (most common answer). If model beats this, it learned meaningful patterns.
