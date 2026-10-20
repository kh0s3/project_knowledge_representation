"""Flask UI for part-07-learning link prediction queries."""

import sys
sys.modules['torchvision'] = None

import collections
import os
from pathlib import Path

import numpy as np
import torch
from flask import Flask, render_template, request, jsonify

HERE = Path(__file__).resolve().parent
os.environ.setdefault("PYSTOW_HOME", str(HERE / "data" / "pystow"))

from pykeen.pipeline import pipeline
from pykeen.triples import TriplesFactory

app = Flask(__name__)

GRAPH_DATA = None
HIDDEN_DATA = None
MODEL = None
TRIPLES = None
COUNTRY_NAMES = None
TIER_NAMES = None
ENT_ID = None
REL_IDS = None
KNOWN_RELS = None
KNOWN_HEADS = None
KNOWN_TAILS = None


def softmax(scores):
    scores = np.array(scores)
    exp_scores = np.exp(scores - np.max(scores))
    return exp_scores / exp_scores.sum()


def load_data():
    global GRAPH_DATA, HIDDEN_DATA
    if GRAPH_DATA is None:
        GRAPH_DATA = torch.load(HERE / "data" / "semiconductor-graph.pt", weights_only=False)
        HIDDEN_DATA = torch.load(HERE / "data" / "hidden-edges.pt", weights_only=False)
    return GRAPH_DATA, HIDDEN_DATA


def create_training_triples(graph_data):
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
    known = collections.defaultdict(set)
    for h, r, t in triples:
        known[(h, t)].add(r)
    return known


def get_known_heads(triples):
    known = collections.defaultdict(set)
    for h, r, t in triples:
        known[(r, t)].add(h)
    return known


def get_known_tails(triples):
    known = collections.defaultdict(set)
    for h, r, t in triples:
        known[(h, r)].add(t)
    return known


def predict_tier(model, tf, exp_name, imp_name, known_rels, ent_id, rel_ids):
    if exp_name not in ent_id or imp_name not in ent_id:
        return None

    exp_id = ent_id[exp_name]
    imp_id = ent_id[imp_name]

    hrt_batch = torch.tensor([[exp_id, 0, imp_id]], dtype=torch.long)
    all_scores = model.score_r(hrt_batch)[0].detach().numpy()

    scores = {}
    for rel_name, rel_id in rel_ids.items():
        if rel_name not in known_rels.get((exp_name, imp_name), set()):
            scores[rel_name] = float(all_scores[rel_id])

    ranked = sorted(scores.items(), key=lambda x: -x[1])
    return ranked


def predict_exporter(model, tf, imp_name, tier_name, known_heads, ent_id, rel_ids):
    relation = f"exports_{tier_name.replace(' ', '_').replace('-', '_')}"

    if imp_name not in ent_id or relation not in rel_ids:
        return None

    imp_id = ent_id[imp_name]
    rel_id = rel_ids[relation]

    hrt_batch = torch.tensor([[0, rel_id, imp_id]], dtype=torch.long)
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


def predict_importer(model, tf, exp_name, tier_name, known_tails, ent_id, rel_ids):
    relation = f"exports_{tier_name.replace(' ', '_').replace('-', '_')}"

    if exp_name not in ent_id or relation not in rel_ids:
        return None

    exp_id = ent_id[exp_name]
    rel_id = rel_ids[relation]

    hrt_batch = torch.tensor([[exp_id, rel_id, 0]], dtype=torch.long)
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


def initialize_model():
    global MODEL, TRIPLES, COUNTRY_NAMES, TIER_NAMES, ENT_ID, REL_IDS
    global KNOWN_RELS, KNOWN_HEADS, KNOWN_TAILS

    if MODEL is not None:
        return

    graph_data, _ = load_data()
    TRIPLES, COUNTRY_NAMES, TIER_NAMES = create_training_triples(graph_data)

    KNOWN_RELS = get_known_relations(TRIPLES)
    KNOWN_HEADS = get_known_heads(TRIPLES)
    KNOWN_TAILS = get_known_tails(TRIPLES)

    tf = TriplesFactory.from_labeled_triples(np.array(TRIPLES))

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

    MODEL = result.model
    ENT_ID = tf.entity_to_id
    REL_IDS = tf.relation_to_id


@app.route("/")
def index():
    initialize_model()
    return render_template("index.html",
                           countries=list(ENT_ID.keys())[:20],
                           tiers=TIER_NAMES)


@app.route("/query", methods=["POST"])
def query():
    initialize_model()

    data = request.get_json()
    qtype = data.get("type")
    exp_name = data.get("exporter", "").strip().upper()
    imp_name = data.get("importer", "").strip().upper()
    tier_name = data.get("tier", "").strip()

    result = []

    if qtype == "Q1":
        if not exp_name or not imp_name:
            return jsonify({"error": "Exporter and Importer are required for Q1"}), 400
        ranked = predict_tier(MODEL, None, exp_name, imp_name, {}, ENT_ID, REL_IDS)
        if ranked:
            scores = [s for _, s in ranked[:5]]
            probs = softmax(scores) * 100
            result = [
                {"name": r[0].replace("exports_", "").replace("_", " "), "prob": f"{probs[i]:.1f}%"}
                for i, r in enumerate(ranked[:5])
            ]
            question = f"What tier does {exp_name} export to {imp_name}?"
        else:
            return jsonify({"error": "Cannot answer: country not in training graph (cold start)"}), 400

    elif qtype == "Q2":
        if not imp_name or not tier_name:
            return jsonify({"error": "Importer and Tier are required for Q2"}), 400
        ranked = predict_exporter(MODEL, None, imp_name, tier_name, {}, ENT_ID, REL_IDS)
        if ranked:
            scores = [s for _, s in ranked[:10]]
            probs = softmax(scores) * 100
            result = [
                {"name": r[0], "prob": f"{probs[i]:.1f}%"}
                for i, r in enumerate(ranked[:10])
            ]
            question = f"Which countries export {tier_name} to {imp_name}?"
        else:
            return jsonify({"error": "Cannot answer: country/tier not in training graph"}), 400

    elif qtype == "Q3":
        if not exp_name or not tier_name:
            return jsonify({"error": "Exporter and Tier are required for Q3"}), 400
        ranked = predict_importer(MODEL, None, exp_name, tier_name, {}, ENT_ID, REL_IDS)
        if ranked:
            scores = [s for _, s in ranked[:10]]
            probs = softmax(scores) * 100
            result = [
                {"name": r[0], "prob": f"{probs[i]:.1f}%"}
                for i, r in enumerate(ranked[:10])
            ]
            question = f"Where does {exp_name} export {tier_name}?"
        else:
            return jsonify({"error": "Cannot answer: country/tier not in training graph"}), 400

    else:
        return jsonify({"error": "Invalid query type"}), 400

    return jsonify({"question": question, "results": result})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
