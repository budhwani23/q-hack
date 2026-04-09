"""
dbn_model.py
Dynamic Bayesian Network over 4-hour time slices.

Two time slices, with intra-slice edges (contemporaneous) and inter-slice edges
(temporal persistence). MLE fit on 4h-block data, with clinical prior injection
to make causal directions sensible despite sparse student data.

Structure (slice t):
    sleep_t, activity_t, screen_t, social_t  -> mood_t
    sleep_t, activity_t, screen_t, mood_t    -> stress_t

Temporal (t -> t+1):
    stress_t  -> stress_{t+1}   (stress persists)
    mood_t    -> mood_{t+1}     (mood persists)
    sleep_t   -> sleep_{t+1}    (sleep pattern carries)

Usage:
    from dbn_model import DBNModel
    dbn = DBNModel().fit()
    dbn.save()
    posterior = dbn.query(
        evidence={("sleep", 0): 2, ("activity", 0): 2},
        targets=[("stress", 1), ("mood", 1)],
    )

Run directly: python dbn_model.py
"""

import json
import pickle
from pathlib import Path

import pandas as pd
from pgmpy.inference import DBNInference
from pgmpy.models import DynamicBayesianNetwork
from pgmpy.estimators import BayesianEstimator

NODES_CSV = Path(__file__).parent / "nodes_4h.csv"
CLUSTER_INFO = Path(__file__).parent / "cluster_info.json"
MODEL_PKL = Path(__file__).parent / "dbn_model.pkl"

FEATURES = ["sleep", "activity", "screen_time", "social", "mood", "stress"]
STATE_LABELS_3 = {0: "low", 1: "med", 2: "high"}
STATE_LABELS_4 = {0: "low", 1: "med_low", 2: "med_high", 3: "high"}

# DBN edges: (from_node, to_node) pairs where each node is (name, time_slice)
INTRA_SLICE_EDGES = [
    # Drivers of mood in slice 0
    (("sleep", 0), ("mood", 0)),
    (("activity", 0), ("mood", 0)),
    (("screen_time", 0), ("mood", 0)),
    (("social", 0), ("mood", 0)),
    # Drivers of stress in slice 0
    (("sleep", 0), ("stress", 0)),
    (("activity", 0), ("stress", 0)),
    (("screen_time", 0), ("stress", 0)),
    (("mood", 0), ("stress", 0)),
]

INTER_SLICE_EDGES = [
    # Temporal persistence
    (("stress", 0), ("stress", 1)),
    (("mood", 0), ("mood", 1)),
    (("sleep", 0), ("sleep", 1)),
    # Slice-1 contemporaneous (must mirror slice-0 intra edges for DBN to be valid)
    (("sleep", 1), ("mood", 1)),
    (("activity", 1), ("mood", 1)),
    (("screen_time", 1), ("mood", 1)),
    (("social", 1), ("mood", 1)),
    (("sleep", 1), ("stress", 1)),
    (("activity", 1), ("stress", 1)),
    (("screen_time", 1), ("stress", 1)),
    (("mood", 1), ("stress", 1)),
]


def load_ks() -> dict[str, int]:
    """Read cluster k per feature from cluster_info.json."""
    with open(CLUSTER_INFO) as f:
        info = json.load(f)
    return {entry["feature"]: entry["k"] for entry in info["cluster_info"]}


def build_transition_df(nodes: pd.DataFrame) -> pd.DataFrame:
    """
    Convert sequential (uid, date, block) rows into (t, t+1) pairs.
    Output columns: (feature, 0) and (feature, 1) for each feature.
    """
    nodes = nodes.sort_values(["uid", "date", "block"]).reset_index(drop=True)
    pairs = []
    for uid, group in nodes.groupby("uid"):
        g = group.reset_index(drop=True)
        for i in range(len(g) - 1):
            row = {}
            for feat in FEATURES:
                row[(feat, 0)] = int(g.iloc[i][feat])
                row[(feat, 1)] = int(g.iloc[i + 1][feat])
            pairs.append(row)
    return pd.DataFrame(pairs)


def build_prior_rows(ks: dict[str, int], n_per_pattern: int) -> pd.DataFrame:
    """
    Synthetic 'expert' (t, t+1) rows to nudge the CPTs toward clinical sense.
    Patterns assume k=3 for all except mood (k=4). If k differs, clip to max.
    """
    def clip(feat, state):
        return min(state, ks[feat] - 1)

    high = lambda f: clip(f, 2)
    mid = lambda f: clip(f, 1)
    low = lambda f: clip(f, 0)

    # Mood has 4 states; use state 3 as "high" and 0 as "low"
    mood_high = ks["mood"] - 1
    mood_low = 0
    mood_mid = ks["mood"] // 2

    patterns = []

    # Healthy persisting -> healthy
    healthy = {
        ("sleep", 0): high("sleep"), ("activity", 0): high("activity"),
        ("screen_time", 0): low("screen_time"), ("social", 0): high("social"),
        ("mood", 0): mood_high, ("stress", 0): low("stress"),
        ("sleep", 1): high("sleep"), ("activity", 1): high("activity"),
        ("screen_time", 1): low("screen_time"), ("social", 1): high("social"),
        ("mood", 1): mood_high, ("stress", 1): low("stress"),
    }
    patterns.extend([healthy] * n_per_pattern)

    # Unhealthy persisting -> unhealthy
    unhealthy = {
        ("sleep", 0): low("sleep"), ("activity", 0): low("activity"),
        ("screen_time", 0): high("screen_time"), ("social", 0): low("social"),
        ("mood", 0): mood_low, ("stress", 0): high("stress"),
        ("sleep", 1): low("sleep"), ("activity", 1): low("activity"),
        ("screen_time", 1): high("screen_time"), ("social", 1): low("social"),
        ("mood", 1): mood_low, ("stress", 1): high("stress"),
    }
    patterns.extend([unhealthy] * n_per_pattern)

    # Recovery: unhealthy -> healthy
    recovery = {
        ("sleep", 0): low("sleep"), ("activity", 0): low("activity"),
        ("screen_time", 0): high("screen_time"), ("social", 0): low("social"),
        ("mood", 0): mood_low, ("stress", 0): high("stress"),
        ("sleep", 1): high("sleep"), ("activity", 1): high("activity"),
        ("screen_time", 1): low("screen_time"), ("social", 1): high("social"),
        ("mood", 1): mood_high, ("stress", 1): mid("stress"),
    }
    patterns.extend([recovery] * (n_per_pattern // 2))

    # Deterioration: healthy -> unhealthy
    deterioration = {
        ("sleep", 0): high("sleep"), ("activity", 0): high("activity"),
        ("screen_time", 0): low("screen_time"), ("social", 0): high("social"),
        ("mood", 0): mood_high, ("stress", 0): low("stress"),
        ("sleep", 1): low("sleep"), ("activity", 1): low("activity"),
        ("screen_time", 1): high("screen_time"), ("social", 1): low("social"),
        ("mood", 1): mood_low, ("stress", 1): mid("stress"),
    }
    patterns.extend([deterioration] * (n_per_pattern // 2))

    # Steady medium
    steady = {
        ("sleep", 0): mid("sleep"), ("activity", 0): mid("activity"),
        ("screen_time", 0): mid("screen_time"), ("social", 0): mid("social"),
        ("mood", 0): mood_mid, ("stress", 0): mid("stress"),
        ("sleep", 1): mid("sleep"), ("activity", 1): mid("activity"),
        ("screen_time", 1): mid("screen_time"), ("social", 1): mid("social"),
        ("mood", 1): mood_mid, ("stress", 1): mid("stress"),
    }
    patterns.extend([steady] * n_per_pattern)

    return pd.DataFrame(patterns)


class DBNModel:
    def __init__(self):
        self.model: DynamicBayesianNetwork | None = None
        self.infer: DBNInference | None = None
        self.ks: dict[str, int] = {}

    def fit(self, nodes_csv: Path = NODES_CSV, inject_priors: bool = True):
        self.ks = load_ks()
        nodes = pd.read_csv(nodes_csv)
        print(f"Loaded {len(nodes)} rows, building (t, t+1) pairs...")

        transitions = build_transition_df(nodes)
        print(f"  built {len(transitions)} transition pairs")

        if inject_priors:
            n_prior = max(50, len(transitions) // 30)  # ~3% of data
            priors = build_prior_rows(self.ks, n_prior)
            transitions = pd.concat([transitions, priors], ignore_index=True)
            print(f"  injected {len(priors)} prior rows -> total {len(transitions)}")

        # Fit with smoothing to avoid zero probabilities
        estimator = BayesianEstimator(self.model, transitions)
        self.model.fit(transitions, estimator=estimator)
        self.infer = DBNInference(self.model)
        print("DBN fit complete with smoothing.")
        return self

    def save(self, path: Path = MODEL_PKL):
        with open(path, "wb") as f:
            pickle.dump({"model": self.model, "ks": self.ks}, f)
        print(f"Saved -> {path}")

    def load(self, path: Path = MODEL_PKL):
        with open(path, "rb") as f:
            blob = pickle.load(f)
        self.model = blob["model"]
        self.ks = blob["ks"]
        self.infer = DBNInference(self.model)
        return self

    def query(self, evidence: dict, targets: list[tuple[str, int]]) -> dict:
        """
        evidence: {(feature_name, time_slice): state_int}
        targets:  [(feature_name, time_slice), ...]
        returns:  {(feature, slice): {state: prob, ...}, ...}
        """
        assert self.infer is not None
        result = self.infer.query(variables=targets, evidence=evidence)
        out = {}
        for tgt in targets:
            factor = result[tgt] if isinstance(result, dict) else result
            # DBNInference returns a single factor or dict depending on n targets
            vals = factor.values
            out[tgt] = {i: float(vals[i]) for i in range(len(vals))}
        return out


def _label_for(feat: str, state: int, ks: dict[str, int]) -> str:
    k = ks[feat]
    if k == 3:
        return STATE_LABELS_3[state]
    if k == 4:
        return STATE_LABELS_4[state]
    return str(state)


def _pretty(dist: dict, feat: str, ks: dict) -> str:
    return "  ".join(f"{_label_for(feat, s, ks)}={p:.2f}" for s, p in sorted(dist.items()))


def sanity_checks():
    dbn = DBNModel().fit()
    dbn.save()
    print()

    ks = dbn.ks

    cases = [
        (
            "Healthy slice-0: good sleep, active, social, low screen",
            {("sleep", 0): 2, ("activity", 0): 2, ("social", 0): 2, ("screen_time", 0): 0},
        ),
        (
            "Rough slice-0: no sleep, sedentary, isolated, doomscroll",
            {("sleep", 0): 0, ("activity", 0): 0, ("social", 0): 0, ("screen_time", 0): 2},
        ),
        (
            "Only observation: yesterday's block was stressful",
            {("stress", 0): 2},
        ),
        (
            "Mixed: slept well but doomscrolling and isolated",
            {("sleep", 0): 2, ("screen_time", 0): 2, ("social", 0): 0},
        ),
    ]

    for label, ev in cases:
        print(f"### {label}")
        print(f"  evidence: {ev}")
        targets = [("stress", 1), ("mood", 1)]
        try:
            post = dbn.query(ev, targets)
            for t in targets:
                feat, _ = t
                print(f"  P({feat}_next)  {_pretty(post[t], feat, ks)}")
        except Exception as e:
            print(f"  QUERY FAILED: {type(e).__name__}: {e}")
        print()


if __name__ == "__main__":
    sanity_checks()
