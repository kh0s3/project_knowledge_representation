"""Turn the semiconductor trade data into a PyTorch Geometric graph for learning,
with support for hiding/removing some edges for link prediction testing.

    python build_graph.py

Run from part-06-learning/ with the .venv active.

This script:
1. Loads CSV data
2. Removes/hides some edges (creates "missing" links for testing)
3. Builds PyG graph with remaining edges
4. Saves hidden edges separately for testing

HIDING EDGES:
- Edges are hidden by tier, by country, or randomly
- Hidden edges become the TEST SET
- Remaining edges become the TRAINING SET

SPLIT STRATEGIES:
- split="random": randomly hide 10% of edges
- split="by_tier": hide ALL edges of 1-2 tiers (tests generalization to unseen tier)
- split="by_country": hide all edges of some countries (tests generalization to unseen countries)

For link prediction, we predict:
- Q1: (exporter, importer) → tier
- Q2: (importer, tier) → exporter
- Q3: (exporter, tier) → importer
"""

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch_geometric.data import HeteroData

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EDGES_CSV = PROJECT_ROOT / "dataset" / "edges_semiconductor_trade.csv"
NODES_CSV = PROJECT_ROOT / "dataset" / "nodes_countries.csv"
TIERS_CSV = PROJECT_ROOT / "dataset" / "supply_chain_tiers.csv"
OUT = Path(__file__).resolve().parent / "data" / "semiconductor-graph.pt"
HIDDEN_OUT = Path(__file__).resolve().parent / "data" / "hidden-edges.pt"

STRATEGIC_ROLES = [
    "Net Importer / High Dependency",
    "Net Exporter / Supply Powerhouse",
    "Balanced Intermediary / Assembly Hub"
]
TIER_NAMES = ["Tier_1_Equipment", "Tier_2_Wafers", "Tier_3A_Logic_Processors", "Tier_3B_Memory", "Tier_3C_Other_ICs"]

SPLIT_RANDOM = "random"
SPLIT_BY_TIER = "by_tier"
SPLIT_BY_COUNTRY = "by_country"


def load_data():
    """Load CSV files and apply cleaning."""
    edges = pd.read_csv(EDGES_CSV)
    countries = pd.read_csv(NODES_CSV)
    tiers = pd.read_csv(TIERS_CSV)

    print(f"Loaded: {len(edges):,} trade edges, {len(countries):,} countries, {len(tiers):,} tiers")

    # Remove _X (Areas, nes) - meaningless for analysis
    mask = ~edges["exporter_iso"].str.contains("_X", na=False) & \
           ~edges["importer_iso"].str.contains("_X", na=False)
    edges_clean = edges[mask].copy()
    print(f"Removed {(~mask).sum():,} edges with _X (Areas, nes)")
    edges_clean = edges_clean[edges_clean["exporter_iso"] != edges_clean["importer_iso"]]

    # Remove _X from countries
    countries_clean = countries[~countries["country_iso"].str.contains("_X", na=False)].copy()

    return edges_clean, countries_clean, tiers


def split_edges_by_random(edges_df, test_ratio=0.1, seed=42):
    """Randomly split edges: test_ratio% for testing, rest for training."""
    rng = np.random.RandomState(seed)
    n_edges = len(edges_df)
    n_test = int(n_edges * test_ratio)
    
    indices = np.arange(n_edges)
    rng.shuffle(indices)
    
    test_indices = indices[:n_test]
    train_indices = indices[n_test:]
    
    train_edges = edges_df.iloc[train_indices].copy()
    test_edges = edges_df.iloc[test_indices].copy()
    
    return train_edges, test_edges


def split_edges_by_tier(edges_df, test_tiers=None, seed=42):
    """Hide ALL edges of certain tiers for testing.
    Tests generalization: can model predict links for unseen tier types?
    
    Args:
        edges_df: DataFrame with edges
        test_tiers: list of tier names to hide (e.g., ["Tier_3A_Logic_Processors"])
                    If None, randomly select 1 tier
    """
    rng = np.random.RandomState(seed)
    
    if test_tiers is None:
        # Randomly select 1 tier to hide
        test_tiers = [rng.choice(TIER_NAMES)]
    
    train_mask = ~edges_df["tier"].isin(test_tiers)
    test_mask = edges_df["tier"].isin(test_tiers)
    
    train_edges = edges_df[train_mask].copy()
    test_edges = edges_df[test_mask].copy()
    
    return train_edges, test_edges


def split_edges_by_country(edges_df, test_countries=None, test_ratio=0.2, seed=42):
    """Hide all edges involving certain countries for testing.
    Tests generalization: can model predict links for unseen countries?
    
    Args:
        edges_df: DataFrame with edges
        test_countries: list of country ISOs to hide
                        If None, randomly select test_ratio% of countries
    """
    rng = np.random.RandomState(seed)
    
    if test_countries is None:
        # Randomly select some countries (exclude NaN and non-string values)
        exp_countries = edges_df["exporter_iso"].dropna().unique()
        imp_countries = edges_df["importer_iso"].dropna().unique()
        all_countries = set(exp_countries) | set(imp_countries)
        # Filter to only string values
        all_countries = {c for c in all_countries if isinstance(c, str)}
        n_test = max(1, int(len(all_countries) * test_ratio))
        choices = rng.choice(list(all_countries), size=n_test, replace=False)
        # Ensure it's always a list (rng.choice returns scalar when n_test=1)
        test_countries = [choices.item()] if n_test == 1 else choices.tolist()
    
    # Hide edges where either exporter or importer is a test country
    train_mask = ~edges_df["exporter_iso"].isin(test_countries) & ~edges_df["importer_iso"].isin(test_countries)
    test_mask = edges_df["exporter_iso"].isin(test_countries) | edges_df["importer_iso"].isin(test_countries)
    
    train_edges = edges_df[train_mask].copy()
    test_edges = edges_df[test_mask].copy()
    
    return train_edges, test_edges


def build_graph(edges, countries, tiers, tier_to_idx, country_to_idx):
    """Build PyG graph with country and tier nodes."""
    # Build country features (label removed to avoid leakage)
    country_features = []
    country_labels = []
    for iso in sorted(country_to_idx.keys()):
        row = countries[countries["country_iso"] == iso].iloc[0]
        # Features: log(export), log(import) - NO net_balance (would leak label)
        export = np.log1p(row["total_export_usd"]) if row["total_export_usd"] > 0 else 0
        import_ = np.log1p(row["total_import_usd"]) if row["total_import_usd"] > 0 else 0
        country_features.append([export, import_])

        # Label: strategic_role
        role = row["strategic_role"]
        country_labels.append(STRATEGIC_ROLES.index(role) if role in STRATEGIC_ROLES else -1)

    x_country = np.array(country_features, dtype=np.float32)
    y_country = np.array(country_labels, dtype=np.int64)

    # Build tier features (one-hot)
    x_tier = np.eye(len(TIER_NAMES), dtype=np.float32)

    # Build edges: exporter -> importer
    edge_list = []
    tier_for_edge = []

    for _, row in edges.iterrows():
        exp_iso = row["exporter_iso"]
        imp_iso = row["importer_iso"]
        tier = row["tier"]

        if exp_iso in country_to_idx and imp_iso in country_to_idx and tier in tier_to_idx:
            exp_idx = country_to_idx[exp_iso]
            imp_idx = country_to_idx[imp_iso]
            tier_idx = tier_to_idx[tier]
            edge_list.append((exp_idx, imp_idx))
            tier_for_edge.append(tier_idx)

    edge_index = np.array(edge_list, dtype=np.int64).T  # [2, num_edges]
    edge_tier = np.array(tier_for_edge, dtype=np.int64)  # tier per edge

    n_countries = len(country_to_idx)
    n_tiers = len(TIER_NAMES)
    n_edges = edge_index.shape[1]

    # Create PyG HeteroData
    data = HeteroData()
    data["country"].x = torch.tensor(x_country, dtype=torch.float32)
    data["tier"].x = torch.tensor(x_tier, dtype=torch.float32)
    data["country", "exports_to", "country"].edge_index = torch.tensor(edge_index, dtype=torch.long).contiguous()

    extra = {
        "y": torch.tensor(y_country),
        "country_names": list(country_to_idx.keys()),
        "tier_names": TIER_NAMES,
        "edge_tier": torch.tensor(edge_tier),
        "source": "semiconductor-trade-network"
    }

    return data, extra


def create_hidden_edges_df(test_edges, country_to_idx, tier_to_idx):
    """Convert test_edges DataFrame to tensor format for evaluation."""
    hidden = []
    for _, row in test_edges.iterrows():
        exp_iso = row["exporter_iso"]
        imp_iso = row["importer_iso"]
        tier = row["tier"]
        
        if exp_iso in country_to_idx and imp_iso in country_to_idx and tier in tier_to_idx:
            hidden.append({
                "exporter_idx": country_to_idx[exp_iso],
                "importer_idx": country_to_idx[imp_iso],
                "tier_idx": tier_to_idx[tier],
                "exporter_name": exp_iso,
                "importer_name": imp_iso,
                "tier_name": tier
            })
    
    return hidden


def main(split_mode="random", test_ratio=0.1, seed=42):
    """Main function to build graph with optional edge hiding.
    
    Args:
        split_mode: "random", "by_tier", or "by_country"
        test_ratio: fraction of edges to hide (for random split)
        seed: random seed for reproducibility
    """
    t0 = time.time()
    edges_full, countries, tiers = load_data()
    
    # Create country index
    all_exporters = set(edges_full["exporter_iso"].unique())
    all_importers = set(edges_full["importer_iso"].unique())
    all_countries_set = sorted(all_exporters | all_importers)
    country_to_idx = {c: i for i, c in enumerate(all_countries_set)}
    
    # Create tier index
    tier_to_idx = {t: i for i, t in enumerate(TIER_NAMES)}
    
    # Split edges based on mode
    if split_mode == SPLIT_RANDOM:
        train_edges, test_edges = split_edges_by_random(edges_full, test_ratio, seed)
        split_desc = f"random {test_ratio*100:.0f}%"
    elif split_mode == SPLIT_BY_TIER:
        train_edges, test_edges = split_edges_by_tier(edges_full, seed=seed)
        test_tiers = test_edges["tier"].unique()
        split_desc = f"by tier (hidden: {list(test_tiers)})"
    elif split_mode == SPLIT_BY_COUNTRY:
        train_edges, test_edges = split_edges_by_country(
            edges_full, test_ratio=test_ratio, seed=seed
        )
        split_desc = f"by country ({test_ratio*100:.0f}% of countries)"
    else:
        raise ValueError(f"Unknown split_mode: {split_mode}")
    
    print(f"\nSplit ({split_desc}, seed {seed}):")
    print(f"  Training edges: {len(train_edges):,}")
    print(f"  Test (hidden) edges: {len(test_edges):,}")
    
    # Build training graph
    data, extra = build_graph(train_edges, countries, tiers, tier_to_idx, country_to_idx)
    
    # Create hidden edges for evaluation
    hidden_edges = create_hidden_edges_df(test_edges, country_to_idx, tier_to_idx)
    
    # Save training graph
    OUT.parent.mkdir(exist_ok=True)
    torch.save({"data": data, **extra}, OUT)
    
    # Save hidden edges for link prediction evaluation
    torch.save({
        "hidden_edges": hidden_edges,
        "split_mode": split_mode,
        "test_ratio": test_ratio,
        "seed": seed,
        "n_train_edges": len(train_edges),
        "n_test_edges": len(test_edges)
    }, HIDDEN_OUT)
    
    # Stats
    y = extra["y"].numpy()
    n_per_class = [int((y == i).sum()) for i in range(len(STRATEGIC_ROLES))]
    
    print(f"\nGraph: {len(country_to_idx)} countries, {len(tier_to_idx)} tiers, {len(train_edges):,} training edges")
    print(f"\nLabel distribution ({len(y)} countries):")
    for i, (role, n) in enumerate(zip(STRATEGIC_ROLES, n_per_class)):
        print(f"  {i}: {role} -> {n} countries")
    
    print(f"\nHidden edges for testing: {len(hidden_edges):,}")
    print(f"Written: {OUT.relative_to(Path(__file__).resolve().parent)}")
    print(f"Hidden edges: {HIDDEN_OUT.relative_to(Path(__file__).resolve().parent)} ({time.time()-t0:.1f}s)")
    
    # Leak check
    print("\n" + "="*60)
    print("LEAK CHECK - Features removed from country nodes:")
    print("  - net_trade_balance_usd: directly reveals strategic_role")
    print("  - hs_description: free text, redundant with tier")
    print("  - _X (Areas, nes): meaningless 'super-node'")
    print("="*60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Build semiconductor graph for learning")
    parser.add_argument("--split", choices=["random", "by_tier", "by_country"], 
                       default="random", help="How to split edges into train/test")
    parser.add_argument("--test_ratio", type=float, default=0.1,
                       help="Fraction of edges to hide (for random split)")
    parser.add_argument("--seed", type=int, default=42,
                       help="Random seed")
    args = parser.parse_args()
    
    main(split_mode=args.split, test_ratio=args.test_ratio, seed=args.seed)
