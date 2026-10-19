"""Small helpers for learning scripts: how to split the data, and how to score.

Splits:
- split_random: random 70/30 split (stratified)
- split_by_tier: put ~30% of tiers in test, all their trade edges with them

Scores:
- precision_at_k: of top-k predictions, share that were correct
- recall_at_k: of all true positives, share found in top-k
- mrr: mean reciprocal rank (1/rank)
- hits_at_k: share of answers ranked in top k
"""

import numpy as np


# ---------------------------------------------------------------- splits
def split_random(n_samples, y, test_share=0.3, seed=0):
    """Random stratified split: 30% test, same class balance on both sides."""
    rng = np.random.RandomState(seed)
    test = []
    for label in (0, 1):
        idx = np.flatnonzero(y == label)
        rng.shuffle(idx)
        test.extend(idx[: int(round(test_share * len(idx)))])
    test = np.sort(np.array(test))
    train = np.setdiff1d(np.arange(n_samples), test)
    return train, test


def split_by_tier(tier_idx, test_share=0.3, seed=0):
    """Put ~30% of TIERS in the test set, all their trade observations with them.
    No tier has observations on both sides, so a model cannot pass by remembering
    which tier an edge belongs to. Returns (train_indices, test_indices)."""
    rng = np.random.RandomState(seed)
    tiers = np.unique(tier_idx)
    rng.shuffle(tiers)
    n_test = max(1, int(round(test_share * len(tiers))))
    test_tiers = tiers[:n_test]
    test = np.flatnonzero(np.isin(tier_idx, test_tiers))
    train = np.flatnonzero(~np.isin(tier_idx, test_tiers))
    return train, test


# ---------------------------------------------------------------- scores
def precision_at_k(y_true, scores, k=100):
    """Of the k predictions ranked highest, the share that were correct."""
    top = np.argsort(-np.asarray(scores), kind="stable")[:k]
    return float(np.asarray(y_true)[top].mean())


def recall_at_k(y_true, scores, k=100):
    """Of all true positives, the share found in the top k predictions."""
    top = np.argsort(-np.asarray(scores), kind="stable")[:k]
    total_positives = max(1, np.asarray(y_true).sum())
    return float(np.asarray(y_true)[top].sum() / total_positives)


def mrr(ranks):
    """Mean reciprocal rank: average of 1/rank for each correct answer.
    Rank 1 = 1.0, rank 2 = 0.5, rank 10 = 0.1."""
    return float(np.mean(1.0 / np.asarray(ranks, dtype=float)))


def hits_at_k(ranks, k=10):
    """Share of answers ranked at most k."""
    ranks = np.asarray(ranks, dtype=int)
    return float(np.mean(ranks <= k))


def average_precision(y_true, scores):
    """PR-AUC: precision-recall area under curve. Guessing scores the base rate."""
    from sklearn.metrics import average_precision_score
    yt = np.asarray(y_true)
    if yt.sum() == 0:
        return float("nan")
    return average_precision_score(yt, np.asarray(scores))


def roc_auc(y_true, scores):
    """ROC-AUC: 0.5 is guessing, 1.0 is perfect."""
    from sklearn.metrics import roc_auc_score
    yt = np.asarray(y_true)
    if yt.sum() == 0 or yt.sum() == len(yt):
        return float("nan")
    return roc_auc_score(yt, np.asarray(scores))
