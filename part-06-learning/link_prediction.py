"""Comprehensive link prediction: predict missing edges in 3 query patterns.

    python link_prediction.py

Run from part-06-learning/ after build_graph.py.

This script evaluates link prediction in THREE query patterns:

Q1: (exporter, importer) → tier
    Question: "What tier does China export to Germany?"
    
Q2: (importer, tier) → exporter  
    Question: "Which countries export Memory chips to USA?"
    
Q3: (exporter, tier) → importer
    Question: "Where does Taiwan export Wafers to?"

Each query pattern is compared against a POPULARITY BASELINE.
We use FILTERED ranking - candidates already known in training are NOT counted.
"""

import sys
# Block torchvision import to avoid PyTorch version compatibility issues
sys.modules['torchvision'] = None

import collections
import os
from pathlib import Path

import numpy as np
import torch

HERE = Path(__file__).resolve().parent
os.environ.setdefault("PYSTOW_HOME", str(HERE / "data" / "pystow"))

from pykeen.pipeline import pipeline
from pykeen.triples import TriplesFactory

from learning_utils import hits_at_k, mrr

SEEDS = range(3)


def load_data():
    """Load training graph and hidden edges."""
    graph_data = torch.load(HERE / "data" / "semiconductor-graph.pt", weights_only=False)
    hidden_data = torch.load(HERE / "data" / "hidden-edges.pt", weights_only=False)
    return graph_data, hidden_data


def create_training_triples(graph_data):
    """Create training triples from the training graph."""
    edge_index = graph_data["data"]["country", "exports_to", "country"].edge_index.numpy()
    edge_tier = graph_data["edge_tier"].numpy()
    country_names = graph_data["country_names"]
    tier_names = graph_data["tier_names"]
    
    triples = []
    for (exp_idx, imp_idx), tier_idx in zip(edge_index.T, edge_tier):
        exp_name = country_names[exp_idx]
        imp_name = country_names[imp_idx]
        tier_name = tier_names[tier_idx]
        relation = f"exports_{tier_name.replace(' ', '_').replace('-', '_')}"
        triples.append((exp_name, relation, imp_name))
    
    return triples, country_names, tier_names


def get_known_relations(triples):
    """Get mapping of (head, tail) -> set of relations known in training."""
    known = collections.defaultdict(set)
    for h, r, t in triples:
        known[(h, t)].add(r)
    return known


def get_known_heads(triples):
    """Get mapping of (relation, tail) -> set of heads known in training."""
    known = collections.defaultdict(set)
    for h, r, t in triples:
        known[(r, t)].add(h)
    return known


def get_known_tails(triples):
    """Get mapping of (head, relation) -> set of tails known in training."""
    known = collections.defaultdict(set)
    for h, r, t in triples:
        known[(h, r)].add(t)
    return known


# =========================================================================
# Q1: (exporter, importer) -> tier
# =========================================================================
def predict_tier(model, tf, exp_name, imp_name, known_rels, ent_id, rel_ids):
    """Predict tier given exporter and importer.
    
    Use model.score_r with batch tensor [[h, 0, t]] to get all relation scores.
    """
    if exp_name not in ent_id or imp_name not in ent_id:
        return None
    
    exp_id = ent_id[exp_name]
    imp_id = ent_id[imp_name]
    
    # PyKEEN expects (batch_size, 3) tensor with [h, r, t]
    # Use 0 as placeholder for relation (we're scoring all relations)
    hrt_batch = torch.tensor([[exp_id, 0, imp_id]], dtype=torch.long)
    
    # score_r returns scores for ALL relations, shape [batch_size, num_relations]
    all_scores = model.score_r(hrt_batch)[0].detach().numpy()
    
    scores = {}
    for rel_name, rel_id in rel_ids.items():
        if rel_name not in known_rels.get((exp_name, imp_name), set()):
            scores[rel_name] = float(all_scores[rel_id])
    
    ranked = sorted(scores.items(), key=lambda x: -x[1])
    return ranked


# =========================================================================
# Q2: (importer, tier) -> exporter  
# =========================================================================
def predict_exporter(model, tf, imp_name, tier_name, known_heads, ent_id, rel_ids):
    """Predict exporter given importer and tier.
    
    Use model.score_h with batch tensor [[0, relation, tail]] to get all head scores.
    """
    relation = f"exports_{tier_name.replace(' ', '_').replace('-', '_')}"
    
    if imp_name not in ent_id or relation not in rel_ids:
        return None
    
    imp_id = ent_id[imp_name]
    rel_id = rel_ids[relation]
    
    # Placeholder 0 for head (we're scoring all heads)
    hrt_batch = torch.tensor([[0, rel_id, imp_id]], dtype=torch.long)
    
    # score_h returns scores for ALL heads, shape [batch_size, num_entities]
    all_scores = model.score_h(hrt_batch)[0].detach().numpy()
    
    scores = {}
    ent_id_reverse = {v: k for k, v in ent_id.items()}
    for exp_idx, score in enumerate(all_scores):
        exp_name = ent_id_reverse.get(exp_idx)
        if exp_name is None:
            continue
        if exp_name not in known_heads.get((relation, imp_name), set()):
            scores[exp_name] = float(score)
    
    ranked = sorted(scores.items(), key=lambda x: -x[1])
    return ranked


# =========================================================================
# Q3: (exporter, tier) -> importer
# =========================================================================
def predict_importer(model, tf, exp_name, tier_name, known_tails, ent_id, rel_ids):
    """Predict importer given exporter and tier.
    
    Use model.score_t with batch tensor [[head, relation, 0]] to get all tail scores.
    """
    relation = f"exports_{tier_name.replace(' ', '_').replace('-', '_')}"
    
    if exp_name not in ent_id or relation not in rel_ids:
        return None
    
    exp_id = ent_id[exp_name]
    rel_id = rel_ids[relation]
    
    # Placeholder 0 for tail (we're scoring all tails)
    hrt_batch = torch.tensor([[exp_id, rel_id, 0]], dtype=torch.long)
    
    # score_t returns scores for ALL tails, shape [batch_size, num_entities]
    all_scores = model.score_t(hrt_batch)[0].detach().numpy()
    
    scores = {}
    ent_id_reverse = {v: k for k, v in ent_id.items()}
    for imp_idx, score in enumerate(all_scores):
        imp_name = ent_id_reverse.get(imp_idx)
        if imp_name is None:
            continue
        if imp_name not in known_tails.get((exp_name, relation), set()):
            scores[imp_name] = float(score)
    
    ranked = sorted(scores.items(), key=lambda x: -x[1])
    return ranked


# =========================================================================
# Popularity baselines
# =========================================================================
def popularity_tier_baseline(triples, exp_name, imp_name):
    """Most common tier for (exporter, importer) in training."""
    counter = collections.Counter()
    for h, r, t in triples:
        if h == exp_name and t == imp_name:
            counter[r] += 1
    if not counter:
        return None
    return counter.most_common(1)[0][0]


def popularity_exporter_baseline(triples, imp_name, tier_name):
    """Most common exporter for (importer, tier) in training."""
    counter = collections.Counter()
    relation = f"exports_{tier_name.replace(' ', '_').replace('-', '_')}"
    for h, r, t in triples:
        if r == relation and t == imp_name:
            counter[h] += 1
    if not counter:
        return None
    return counter.most_common(1)[0][0]


def popularity_importer_baseline(triples, exp_name, tier_name):
    """Most common importer for (exporter, tier) in training."""
    counter = collections.Counter()
    relation = f"exports_{tier_name.replace(' ', '_').replace('-', '_')}"
    for h, r, t in triples:
        if h == exp_name and r == relation:
            counter[t] += 1
    if not counter:
        return None
    return counter.most_common(1)[0][0]


def rank_of正确答案(ranked_list, true_item):
    """Find rank of true item in ranked list (1-indexed)."""
    for i, (item, score) in enumerate(ranked_list):
        if item == true_item:
            return i + 1
    return len(ranked_list) + 1


def evaluate_query_pattern(model, tf, hidden_edges, query_pattern, triples, ent_id, rel_ids,
                           known_rels, known_heads, known_tails):
    """Evaluate one query pattern on all hidden edges."""
    
    ranks_model = []
    ranks_pop = []
    
    for edge in hidden_edges:
        exp_name = edge["exporter_name"]
        imp_name = edge["importer_name"]
        tier_name = edge["tier_name"]
        true_relation = f"exports_{tier_name.replace(' ', '_').replace('-', '_')}"
        
        if query_pattern == "Q1":  # (exporter, importer) -> tier
            ranked_tiers = predict_tier(model, tf, exp_name, imp_name, known_rels, ent_id, rel_ids)
            if ranked_tiers:
                rank = rank_of正确答案(ranked_tiers, true_relation)
                ranks_model.append(rank)
            
            # Popularity baseline
            counter = collections.Counter()
            for h, r, t in triples:
                if h == exp_name and t == imp_name:
                    counter[r] += 1
            if counter:
                ranked_pop = sorted(counter.items(), key=lambda x: -x[1])
                rank = rank_of正确答案(ranked_pop, true_relation)
                ranks_pop.append(rank)
                    
        elif query_pattern == "Q2":  # (importer, tier) -> exporter
            ranked_exporters = predict_exporter(model, tf, imp_name, tier_name, known_heads, ent_id, rel_ids)
            if ranked_exporters:
                rank = rank_of正确答案(ranked_exporters, exp_name)
                ranks_model.append(rank)
            
            counter = collections.Counter()
            for h, r, t in triples:
                if r == true_relation and t == imp_name:
                    counter[h] += 1
            if counter:
                ranked_pop = sorted(counter.items(), key=lambda x: -x[1])
                rank = rank_of正确答案(ranked_pop, exp_name)
                ranks_pop.append(rank)
                
        elif query_pattern == "Q3":  # (exporter, tier) -> importer
            ranked_importers = predict_importer(model, tf, exp_name, tier_name, known_tails, ent_id, rel_ids)
            if ranked_importers:
                rank = rank_of正确答案(ranked_importers, imp_name)
                ranks_model.append(rank)
            
            counter = collections.Counter()
            for h, r, t in triples:
                if h == exp_name and r == true_relation:
                    counter[t] += 1
            if counter:
                ranked_pop = sorted(counter.items(), key=lambda x: -x[1])
                rank = rank_of正确答案(ranked_pop, imp_name)
                ranks_pop.append(rank)
    
    return ranks_model, ranks_pop


def print_results(pattern_name, description, ranks_model, ranks_pop, seed, n_hidden):
    """Print results for one query pattern."""
    n_valid = len(ranks_model)
    if n_valid == 0:
        print(f"\n{pattern_name}: No valid predictions (all entities cold start)")
        return
    
    model_mrr = mrr(ranks_model)
    model_h5 = hits_at_k(ranks_model, 5)
    model_h10 = hits_at_k(ranks_model, 10)
    
    pop_mrr = mrr(ranks_pop) if ranks_pop else 0
    pop_h5 = hits_at_k(ranks_pop, 5) if ranks_pop else 0
    pop_h10 = hits_at_k(ranks_pop, 10) if ranks_pop else 0
    
    print(f"\n{pattern_name}: {description}")
    print(f"  {n_valid}/{n_hidden} hidden edges evaluable ({n_hidden - n_valid} cold start)")
    print(f"  Model:   MRR={model_mrr:.3f}  Hits@5={model_h5:.3f}  Hits@10={model_h10:.3f}")
    print(f"  Pop:     MRR={pop_mrr:.3f}  Hits@5={pop_h5:.3f}  Hits@10={pop_h10:.3f}")


def main():
    print("="*70)
    print("COMPREHENSIVE LINK PREDICTION")
    print("Q1: (exporter, importer) -> tier")
    print("Q2: (importer, tier) -> exporter")
    print("Q3: (exporter, tier) -> importer")
    print("="*70)
    
    graph_data, hidden_data = load_data()
    hidden_edges = hidden_data["hidden_edges"]
    split_mode = hidden_data["split_mode"]
    n_train = hidden_data["n_train_edges"]
    n_test = hidden_data["n_test_edges"]
    
    print(f"\nSplit mode: {split_mode}")
    print(f"Training edges: {n_train:,}")
    print(f"Hidden (test) edges: {n_test:,}")
    
    triples, country_names, tier_names = create_training_triples(graph_data)
    
    all_relations = [f"exports_{t.replace(' ', '_').replace('-', '_')}" for t in tier_names]
    
    print(f"\nTriples: {len(triples):,} training triples, {len(all_relations)} relation types")
    
    known_rels = get_known_relations(triples)
    known_heads = get_known_heads(triples)
    known_tails = get_known_tails(triples)
    
    all_results = {"Q1": [], "Q2": [], "Q3": []}
    
    for seed in SEEDS:
        print(f"\n{'='*70}")
        print(f"SEED {seed}")
        print("="*70)
        
        tf = TriplesFactory.from_labeled_triples(np.array(triples))
        
        result = pipeline(
            training=tf,
            validation=tf,
            testing=tf,
            model="TransE",
            model_kwargs=dict(embedding_dim=32),
            training_kwargs=dict(num_epochs=100, batch_size=256),
            random_seed=seed,
            device="cpu",
            use_tqdm=False
        )
        
        model = result.model
        ent_id = tf.entity_to_id
        rel_ids = tf.relation_to_id
        
        for q_pattern in ["Q1", "Q2", "Q3"]:
            desc = {
                "Q1": "(exporter, importer) → tier: What tier does A export to B?",
                "Q2": "(importer, tier) → exporter: Who exports tier X to B?",
                "Q3": "(exporter, tier) → importer: Where does A export tier X?"
            }[q_pattern]
            
            ranks_m, ranks_p = evaluate_query_pattern(
                model, tf, hidden_edges, q_pattern, triples,
                ent_id, rel_ids, known_rels, known_heads, known_tails
            )
            
            print_results(q_pattern, desc, ranks_m, ranks_p, seed, len(hidden_edges))
            all_results[q_pattern].append((ranks_m, ranks_p))
    
    # Summary
    print("\n" + "="*70)
    print("SUMMARY ACROSS SEEDS")
    print("="*70)
    
    for q_pattern in ["Q1", "Q2", "Q3"]:
        desc = {
            "Q1": "(exporter, importer) → tier",
            "Q2": "(importer, tier) → exporter",
            "Q3": "(exporter, tier) → importer"
        }[q_pattern]
        
        model_mrrs = []
        pop_mrrs = []
        for ranks_m, ranks_p in all_results[q_pattern]:
            if ranks_m:
                model_mrrs.append(mrr(ranks_m))
            if ranks_p:
                pop_mrrs.append(mrr(ranks_p))
        
        if model_mrrs:
            print(f"\n{q_pattern}: {desc}")
            print(f"  Model MRR: {min(model_mrrs):.3f} - {max(model_mrrs):.3f} (spread)")
            print(f"  Pop MRR:  {min(pop_mrrs):.3f} - {max(pop_mrrs):.3f}")
            
            if min(model_mrrs) > max(pop_mrrs):
                print(f"  -> Model BEATS baseline")
            elif max(model_mrrs) < min(pop_mrrs):
                print(f"  -> Baseline BEATS model")
            else:
                print(f"  -> Mixed (depends on seed)")
    
    print("\n" + "="*70)
    print("KEY INSIGHTS:")
    print("- MRR close to 0 = model struggles; close to 1 = perfect ranking")
    print("- Hits@10: share of correct answers in top 10")
    print("- Cold start = entity/relation not in training -> cannot predict")
    print("- If model beats baseline -> learned meaningful graph patterns")
    print("="*70)


def softmax(scores):
    """Convert scores to probabilities using softmax."""
    import numpy as np
    scores = np.array(scores)
    exp_scores = np.exp(scores - np.max(scores))
    return exp_scores / exp_scores.sum()


def query_model(model, tf, ent_id, rel_ids, tier_names, question_type, exp_name=None, imp_name=None, tier_name=None):
    """Ask a specific question to the trained model.

    Args:
        model: trained PyKEEN model
        tf: TriplesFactory with entity/relation mappings
        ent_id: entity_to_id dict
        rel_ids: relation_to_id dict
        tier_names: list of tier names for display
        question_type: "Q1", "Q2", or "Q3"
        exp_name: exporter country ISO (e.g., "CHN" for China)
        imp_name: importer country ISO (e.g., "DEU" for Germany)
        tier_name: tier name (e.g., "Tier_3B_Memory")

    Returns:
        ranked list of (candidate, score) tuples
    """
    if question_type == "Q1":
        result = predict_tier(model, tf, exp_name, imp_name, {}, ent_id, rel_ids)
        print(f"\nQuestion: What tier does {exp_name} export to {imp_name}?")
        if result:
            scores = [s for _, s in result[:5]]
            probs = softmax(scores) * 100
            print("Model ranking:")
            for i, (tier, score) in enumerate(result[:5], 1):
                tier_clean = tier.replace("exports_", "").replace("_", " ")
                print(f"  {i}. {tier_clean} ({probs[i-1]:.1f}%)")
        else:
            print("  Cannot answer: country not in training graph (cold start)")
        return result

    elif question_type == "Q2":
        result = predict_exporter(model, tf, imp_name, tier_name, {}, ent_id, rel_ids)
        print(f"\nQuestion: Who exports {tier_name} to {imp_name}?")
        if result:
            scores = [s for _, s in result[:10]]
            probs = softmax(scores) * 100
            print("Model ranking:")
            for i, (exp, score) in enumerate(result[:10], 1):
                print(f"  {i}. {exp} ({probs[i-1]:.1f}%)")
        else:
            print("  Cannot answer: country/tier not in training graph")
        return result

    elif question_type == "Q3":
        result = predict_importer(model, tf, exp_name, tier_name, {}, ent_id, rel_ids)
        print(f"\nQuestion: Where does {exp_name} export {tier_name}?")
        if result:
            scores = [s for _, s in result[:10]]
            probs = softmax(scores) * 100
            print("Model ranking:")
            for i, (imp, score) in enumerate(result[:10], 1):
                print(f"  {i}. {imp} ({probs[i-1]:.1f}%)")
        else:
            print("  Cannot answer: country/tier not in training graph")
        return result


def interactive_query():
    """Run an interactive query session after training."""
    graph_data, hidden_data = load_data()
    triples, country_names, tier_names = create_training_triples(graph_data)
    
    print("\n" + "="*70)
    print("INTERACTIVE QUERY MODE")
    print("="*70)
    print("Train model for queries...")
    
    tf = TriplesFactory.from_labeled_triples(np.array(triples))
    result = pipeline(
        training=tf,
        validation=tf,
        testing=tf,
        model="TransE",
        model_kwargs=dict(embedding_dim=32),
        training_kwargs=dict(num_epochs=100, batch_size=256),
        random_seed=42,
        device="cpu",
        use_tqdm=False
    )
    
    model = result.model
    ent_id = tf.entity_to_id
    rel_ids = tf.relation_to_id
    
    print("\nAvailable countries (ISOs):", list(ent_id.keys())[:20], "...")
    print("Available tiers:", tier_names)
    print("\nQuery types:")
    print("  Q1: What tier does EXPORTER export to IMPORTER?")
    print("  Q2: Who exports TIER to IMPORTER?")
    print("  Q3: Where does EXPORTER export TIER?")
    print("  'quit' to exit")
    
    while True:
        print("\n" + "-"*50)
        q = input("Enter query (e.g., 'Q1 CHN DEU' or 'Q2 USA Tier_3B_Memory'): ").strip()
        if q.lower() == 'quit':
            break
        
        parts = q.split()
        if len(parts) < 2:
            print("Invalid format. Try 'Q1 CHN DEU' or 'Q2 USA Tier_3B_Memory'")
            continue
        
        qtype = parts[0].upper()
        if qtype == "Q1" and len(parts) >= 3:
            query_model(model, tf, ent_id, rel_ids, tier_names, "Q1", 
                       exp_name=parts[1], imp_name=parts[2])
        elif qtype == "Q2" and len(parts) >= 3:
            query_model(model, tf, ent_id, rel_ids, tier_names, "Q2",
                       imp_name=parts[1], tier_name=parts[2])
        elif qtype == "Q3" and len(parts) >= 3:
            query_model(model, tf, ent_id, rel_ids, tier_names, "Q3",
                       exp_name=parts[1], tier_name=parts[2])
        else:
            print("Invalid query. Format: 'Q1 EXPORTER IMPORTER' or 'Q2 IMPORTER TIER' or 'Q3 EXPORTER TIER'")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Link prediction for semiconductor trade")
    parser.add_argument("--query", action="store_true", help="Run interactive query mode")
    args = parser.parse_args()
    
    if args.query:
        interactive_query()
    else:
        main()
