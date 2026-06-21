"""
Parking Violation Intelligence - Data Pipeline

Reads the raw police violation CSV, cleans it, runs DBSCAN hotspot clustering,
and computes the congestion-impact severity score per hotspot.

Run from the project root:
    python3 pipeline/build_pipeline.py

Produces (in project root):
    cleaned_base.parquet      (intermediate checkpoint, not used by the backend)
    clustered.parquet         (required by backend)
    hotspot_scores_v2.parquet (required by backend)
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN

ROOT = Path(__file__).resolve().parent.parent
RAW_VIOLATIONS_CSV = ROOT / "data" / "jan_to_may_police_violation_anonymized791b166.csv"

# ---- Config ----
DBSCAN_EPS_KM = 0.08       # ~80 meters
DBSCAN_MIN_SAMPLES = 10
KMS_PER_RADIAN = 6371.0088

VIOLATION_WEIGHTS = {
    "PARKING IN A MAIN ROAD": 3,
    "PARKING ON FOOTPATH": 3,
    "PARKING NEAR ROAD CROSSING": 3,
    "DOUBLE PARKING": 2.5,
    "PARKING NEAR BUSTOP/SCHOOL/HOSPITAL ETC": 2.5,
    "WRONG PARKING": 2,
    "NO PARKING": 1,
}
ROAD_BLOCKING_TYPES = {
    "PARKING IN A MAIN ROAD", "PARKING ON FOOTPATH",
    "PARKING NEAR ROAD CROSSING", "DOUBLE PARKING",
}


def parse_violation_list(x):
    try:
        return json.loads(x)
    except Exception:
        return []


def step1_clean():
    print("[1/3] Cleaning raw data...")
    df = pd.read_csv(RAW_VIOLATIONS_CSV, low_memory=False)
    df["created_datetime"] = pd.to_datetime(df["created_datetime"], errors="coerce", utc=True)
    df = df.dropna(subset=["created_datetime"])

    # Source timestamps are UTC; convert to IST so hour-of-day patterns are meaningful
    df["created_ist"] = df["created_datetime"].dt.tz_convert("Asia/Kolkata")
    df["hour"] = df["created_ist"].dt.hour
    df["dow"] = df["created_ist"].dt.day_name()
    df["violation_list"] = df["violation_type"].apply(parse_violation_list)

    out = ROOT / "cleaned_base.parquet"
    df.to_parquet(out)
    print(f"      saved {out} ({len(df)} rows)")
    return df


def step2_cluster(df):
    print("[2/3] Running DBSCAN hotspot clustering...")
    coords = df[["latitude", "longitude"]].to_numpy()
    eps = DBSCAN_EPS_KM / KMS_PER_RADIAN
    db = DBSCAN(eps=eps, min_samples=DBSCAN_MIN_SAMPLES, metric="haversine").fit(np.radians(coords))
    df["cluster_id"] = db.labels_

    n_clusters = len(set(db.labels_)) - (1 if -1 in db.labels_ else 0)
    noise = (db.labels_ == -1).sum()
    print(f"      {n_clusters} clusters, {noise} noise points ({noise/len(df)*100:.1f}%)")

    out = ROOT / "clustered.parquet"
    df.to_parquet(out)
    print(f"      saved {out}")
    return df


def step3_score(df):
    print("[3/3] Computing congestion-impact severity scores...")
    df = df[df["cluster_id"] != -1].copy()

    def viol_weight(vlist):
        return sum(VIOLATION_WEIGHTS.get(v, 1) for v in vlist)

    def has_road_blocking(vlist):
        return any(v in ROAD_BLOCKING_TYPES for v in vlist)

    df["viol_weight"] = df["violation_list"].apply(viol_weight)
    df["is_road_blocking"] = df["violation_list"].apply(has_road_blocking)

    agg = df.groupby("cluster_id").agg(
        violation_count=("id", "count"),
        total_weight=("viol_weight", "sum"),
        unique_vehicles=("vehicle_number", lambda x: x.nunique()),
        lat=("latitude", "mean"),
        lon=("longitude", "mean"),
        top_station=("police_station", lambda x: x.mode().iloc[0] if not x.mode().empty else None),
        junction_ratio=("junction_name", lambda x: (x != "No Junction").mean()),
        road_block_ratio=("is_road_blocking", "mean"),
    ).reset_index()

    agg["repeat_ratio"] = 1 - (agg["unique_vehicles"] / agg["violation_count"])

    def time_concentration(g):
        hc = g["hour"].value_counts(normalize=True)
        return hc.nlargest(3).sum()

    tc = df.groupby("cluster_id").apply(time_concentration, include_groups=False)
    agg = agg.merge(tc.rename("time_concentration"), on="cluster_id")

    norm_cols = ["violation_count", "total_weight", "repeat_ratio", "time_concentration", "junction_ratio", "road_block_ratio"]
    for col in norm_cols:
        rng = agg[col].max() - agg[col].min()
        agg[col + "_norm"] = (agg[col] - agg[col].min()) / rng if rng > 0 else 0.0

    # Severity score: general "how big a problem is this" signal
    agg["severity_score"] = (
        0.40 * agg["violation_count_norm"]
        + 0.30 * agg["total_weight_norm"]
        + 0.15 * agg["repeat_ratio_norm"]
        + 0.15 * agg["time_concentration_norm"]
    )

    # Congestion-impact proxy: weighted toward signals that plausibly reflect
    # actual traffic-flow disruption (road-blocking type + junction presence),
    # not just raw ticket volume
    agg["congestion_impact_score"] = (
        0.30 * agg["violation_count_norm"]
        + 0.25 * agg["road_block_ratio_norm"]
        + 0.25 * agg["junction_ratio_norm"]
        + 0.10 * agg["repeat_ratio_norm"]
        + 0.10 * agg["time_concentration_norm"]
    )

    agg = agg.sort_values("congestion_impact_score", ascending=False)
    out = ROOT / "hotspot_scores_v2.parquet"
    agg.to_parquet(out)
    print(f"      saved {out} ({len(agg)} hotspot clusters)")
    return agg


if __name__ == "__main__":
    df = step1_clean()
    df = step2_cluster(df)
    scores = step3_score(df)
    print("\nDone. Top 5 priority zones:")
    print(scores[["cluster_id", "top_station", "violation_count", "congestion_impact_score"]].head(5).to_string(index=False))
