"""
data_prep_dbn.py
Preprocesses StudentLife CSV into 4-hour time-slice rows for a Dynamic Bayesian Network.

Pipeline:
  1. Load CSV, sort by (uid, window_start).
  2. Parse window_start -> hour, bucket into 4-hour blocks (0..5).
  3. Z-score-merge stress signals, compute PANAS PA/NA.
  4. Log-transform heavy-tailed features (screen_time, call_duration).
  5. Aggregate hourly windows -> 4-hour blocks per (uid, date, block).
  6. Drop users with <50 blocks.
  7. Cyclic-encode block index (block_sin, block_cos) and keep as metadata only
     (not BN nodes — they inform clustering context).
  8. Forward-fill EMA columns within user, median-fill leftover.
  9. K-means cluster each feature independently, k chosen by elbow (range 2..5).
 10. Save clustered integer states -> nodes_4h.csv
     Also save cluster centers JSON for interpretation.

Run: python data_prep_dbn.py
Inputs: ../studentlife_daily_and_surveys_qh.csv
Outputs: nodes_4h.csv, cluster_info.json
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

RAW = Path(__file__).parent.parent / "studentlife_daily_and_surveys_qh.csv"
OUT_CSV = Path(__file__).parent / "nodes_4h.csv"
OUT_INFO = Path(__file__).parent / "cluster_info.json"

PANAS_POS = [
    "panas_interested", "panas_enthusiastic", "panas_strong", "panas_proud",
    "panas_attentive", "panas_inspired", "panas_determined", "panas_active",
    "panas_alert",
]
PANAS_NEG = [
    "panas_distressed", "panas_upset", "panas_scared", "panas_nervous",
    "panas_jittery", "panas_afraid", "panas_guilty", "panas_hostile",
    "panas_irritable",
]

# Features we'll cluster into discrete BN node states
FEATURES = [
    "sleep",        # from prev_day_sleep_ema_hours
    "activity",     # from active_ratio
    "screen_time",  # from log(screen_time_window_minutes)
    "social",       # from call_count + sms_count
    "mood",         # from panas_PA - panas_NA
    "stress",       # z-merged stress_ema + panas_NA + vr_downhearted
]


def z(s: pd.Series) -> pd.Series:
    mu = s.mean(skipna=True)
    sd = s.std(skipna=True)
    if sd == 0 or np.isnan(sd):
        return s - mu
    return (s - mu) / sd


def elbow_k(X: np.ndarray, k_range=range(2, 6), random_state=42) -> int:
    """Pick k using the simple 'max distance from line' elbow heuristic."""
    inertias = []
    ks = list(k_range)
    for k in ks:
        km = KMeans(n_clusters=k, random_state=random_state, n_init=10)
        km.fit(X)
        inertias.append(km.inertia_)
    # Geometric elbow: distance from each point to the line (k_min, I_min)-(k_max, I_max)
    p1 = np.array([ks[0], inertias[0]])
    p2 = np.array([ks[-1], inertias[-1]])
    line_vec = p2 - p1
    line_len = np.linalg.norm(line_vec)
    dists = []
    for i, k in enumerate(ks):
        p = np.array([k, inertias[i]])
        cross = np.abs(np.cross(line_vec, p1 - p))
        dists.append(cross / line_len)
    return ks[int(np.argmax(dists))]


def cluster_feature(series: pd.Series, name: str) -> tuple[np.ndarray, dict]:
    """Z-score a feature, pick k via elbow, fit k-means, return labels ordered by center."""
    values = series.values.reshape(-1, 1)
    scaler = StandardScaler()
    X = scaler.fit_transform(values)
    k = elbow_k(X)
    km = KMeans(n_clusters=k, random_state=42, n_init=10)
    raw_labels = km.fit_predict(X)
    # Reorder labels so that 0 = lowest center, k-1 = highest
    centers_scaled = km.cluster_centers_.flatten()
    order = np.argsort(centers_scaled)
    remap = {old: new for new, old in enumerate(order)}
    labels = np.array([remap[l] for l in raw_labels])
    # Report centers in original units
    centers_original = scaler.inverse_transform(km.cluster_centers_).flatten()
    centers_ordered = centers_original[order].tolist()
    info = {
        "feature": name,
        "k": int(k),
        "centers_original_units": [round(float(c), 3) for c in centers_ordered],
    }
    return labels, info


def main():
    print(f"Loading {RAW}...")
    df = pd.read_csv(RAW)
    print(f"  raw shape: {df.shape}")

    # ---- 1. Parse timestamp, extract hour, create 4-hour block index (0..5) ----
    df["ts"] = pd.to_datetime(df["window_start"], format="%d-%m-%Y %H:%M", errors="coerce")
    df = df.dropna(subset=["ts"])
    df["hour"] = df["ts"].dt.hour
    df["block"] = df["hour"] // 4  # 0=00-04, 1=04-08, 2=08-12, 3=12-16, 4=16-20, 5=20-24
    df["date"] = df["ts"].dt.date.astype(str)
    df = df.sort_values(["uid", "ts"]).reset_index(drop=True)

    # ---- 2. Log-transform heavy-tailed columns BEFORE aggregation ----
    df["screen_log"] = np.log1p(df["screen_time_window_minutes"].fillna(0))
    df["call_dur_log"] = np.log1p(df["call_duration_total"].fillna(0))

    # ---- 3. Forward-fill EMA/survey within user (sparse by design) ----
    ema_cols = [
        "prev_day_sleep_ema_hours", "stress_ema_level", "vr_downhearted",
    ] + PANAS_POS + PANAS_NEG
    df[ema_cols] = df.groupby("uid")[ema_cols].ffill()

    # ---- 4. Aggregate hourly windows -> 4-hour blocks per (uid, date, block) ----
    agg = df.groupby(["uid", "date", "block"]).agg(
        sedentary_ratio=("sedentary_ratio", "mean"),
        active_ratio=("active_ratio", "mean"),
        screen_log=("screen_log", "mean"),
        call_count=("call_count", "sum"),
        sms_count=("sms_count", "sum"),
        call_dur_log=("call_dur_log", "mean"),
        sleep_hours=("prev_day_sleep_ema_hours", "first"),
        stress_ema=("stress_ema_level", "first"),
        vr_downhearted=("vr_downhearted", "first"),
        **{c: (c, "first") for c in PANAS_POS + PANAS_NEG},
    ).reset_index()
    print(f"  after 4h block agg: {agg.shape}")

    # ---- 5. Compute derived features ----
    agg["panas_PA"] = agg[PANAS_POS].mean(axis=1)
    agg["panas_NA"] = agg[PANAS_NEG].mean(axis=1)
    agg["mood_raw"] = agg["panas_PA"] - agg["panas_NA"]

    # Stress: z-merge stress_ema + panas_NA + vr_downhearted
    agg["stress_raw"] = (
        z(agg["stress_ema"]).fillna(0)
        + z(agg["panas_NA"]).fillna(0)
        + z(agg["vr_downhearted"]).fillna(0)
    )

    agg["activity_raw"] = agg["active_ratio"].fillna(0)
    agg["social_raw"] = (
        agg["call_count"].fillna(0) + agg["sms_count"].fillna(0)
    )
    agg["screen_raw"] = agg["screen_log"].fillna(0)
    agg["sleep_raw"] = agg["sleep_hours"]

    # ---- 6. Median-fill leftover NaNs in raw feature columns ----
    raw_cols = ["sleep_raw", "activity_raw", "screen_raw", "social_raw", "mood_raw", "stress_raw"]
    for c in raw_cols:
        med = agg[c].median()
        n_miss = agg[c].isna().sum()
        agg[c] = agg[c].fillna(med)
        if n_miss:
            print(f"  median-filled {n_miss} NaN in {c} (med={med:.3f})")

    # ---- 7. Drop users with <50 blocks ----
    user_counts = agg.groupby("uid").size()
    keep_users = user_counts[user_counts >= 50].index
    before = len(agg)
    agg = agg[agg["uid"].isin(keep_users)].reset_index(drop=True)
    print(f"  kept {len(keep_users)}/{len(user_counts)} users, dropped {before - len(agg)} rows")

    # ---- 8. Cyclic encode block (metadata only, not a BN node) ----
    agg["block_sin"] = np.sin(2 * np.pi * agg["block"] / 6)
    agg["block_cos"] = np.cos(2 * np.pi * agg["block"] / 6)

    # ---- 9. K-means cluster each feature with elbow-selected k ----
    print("\nClustering features:")
    cluster_info = []
    nodes = pd.DataFrame({
        "uid": agg["uid"],
        "date": agg["date"],
        "block": agg["block"].astype(int),
        "block_sin": agg["block_sin"],
        "block_cos": agg["block_cos"],
    })
    name_to_raw = {
        "sleep": "sleep_raw",
        "activity": "activity_raw",
        "screen_time": "screen_raw",
        "social": "social_raw",
        "mood": "mood_raw",
        "stress": "stress_raw",
    }
    for node_name in FEATURES:
        labels, info = cluster_feature(agg[name_to_raw[node_name]], node_name)
        nodes[node_name] = labels
        cluster_info.append(info)
        print(f"  {node_name:12s}  k={info['k']}  centers={info['centers_original_units']}")

    # ---- 10. Sanity: show distribution per node ----
    print("\nState distributions:")
    for node_name in FEATURES:
        dist = nodes[node_name].value_counts(normalize=True).sort_index()
        print(f"  {node_name:12s}  " + "  ".join(f"{int(k)}:{v:.2f}" for k, v in dist.items()))

    # ---- 11. Save ----
    nodes.to_csv(OUT_CSV, index=False)
    with open(OUT_INFO, "w") as f:
        json.dump({
            "features": FEATURES,
            "cluster_info": cluster_info,
            "n_rows": len(nodes),
            "n_users": int(nodes["uid"].nunique()),
        }, f, indent=2)
    print(f"\nSaved {len(nodes)} rows -> {OUT_CSV}")
    print(f"Saved cluster info -> {OUT_INFO}")


if __name__ == "__main__":
    main()
