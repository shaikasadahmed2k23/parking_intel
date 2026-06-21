"""
Parking Violation Intelligence & Enforcement Prioritization System
FastAPI backend

Run with: uvicorn main:app --reload --port 8000
Requires: cleaned_base.parquet, clustered.parquet, hotspot_scores_v2.parquet
          (one level up, in ../ relative to this file) plus the Astram event CSV.
"""

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import numpy as np
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

app = FastAPI(title="Parking Violation Intelligence API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Load data once at startup ----
scores_df = pd.read_parquet(BASE_DIR / "hotspot_scores_v2.parquet")
clustered_df = pd.read_parquet(BASE_DIR / "clustered.parquet")
clustered_df = clustered_df[clustered_df["cluster_id"] != -1]

events_df = pd.read_csv(
    BASE_DIR / "data" / "Astram_event_data_anonymized_-_Astram_event_data_anonymizedb40ac87.csv",
    low_memory=False,
)
congestion_events = events_df[
    events_df["event_cause"].isin(["congestion", "road_conditions"])
].dropna(subset=["latitude", "longitude"])
congestion_events = congestion_events[congestion_events["latitude"] != 0]


def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 2 * R * np.arcsin(np.sqrt(a))


@app.get("/api/health")
def health():
    return {"status": "ok", "hotspots_loaded": len(scores_df), "violations_loaded": len(clustered_df)}


@app.get("/api/hotspots")
def get_hotspots(
    limit: int = Query(50, le=654),
    sort_by: str = Query("congestion_impact_score", enum=["congestion_impact_score", "severity_score", "violation_count"]),
    min_violations: int = Query(0),
):
    """Ranked list of hotspot clusters for the map / priority panel."""
    df = scores_df[scores_df["violation_count"] >= min_violations]
    df = df.sort_values(sort_by, ascending=False).head(limit)
    cols = [
        "cluster_id", "top_station", "lat", "lon", "violation_count",
        "unique_vehicles", "repeat_ratio", "junction_ratio", "road_block_ratio",
        "time_concentration", "severity_score", "congestion_impact_score",
    ]
    return df[cols].round(4).to_dict(orient="records")


@app.get("/api/hotspots/rank-comparison")
def rank_comparison(top_n: int = Query(30, le=200)):
    """
    Compares each hotspot's rank under naive volume-sort vs. our congestion-impact
    score, to make visible which zones are under/over-rated by raw ticket count.
    """
    by_volume = scores_df.sort_values("violation_count", ascending=False).reset_index(drop=True)
    by_volume["volume_rank"] = by_volume.index + 1

    by_impact = scores_df.sort_values("congestion_impact_score", ascending=False).reset_index(drop=True)
    by_impact["impact_rank"] = by_impact.index + 1

    merged = by_impact.merge(by_volume[["cluster_id", "volume_rank"]], on="cluster_id")
    merged["rank_delta"] = merged["volume_rank"] - merged["impact_rank"]  # positive = promoted by our model
    merged = merged.head(top_n)

    cols = ["cluster_id", "top_station", "violation_count", "congestion_impact_score", "impact_rank", "volume_rank", "rank_delta"]
    return merged[cols].round(4).to_dict(orient="records")


@app.get("/api/hotspots/{cluster_id}")
def get_hotspot_detail(cluster_id: int):
    """Detail view: violation type breakdown + hourly pattern for one hotspot."""
    row = scores_df[scores_df["cluster_id"] == cluster_id]
    if row.empty:
        raise HTTPException(404, "cluster not found")

    sub = clustered_df[clustered_df["cluster_id"] == cluster_id]

    # violation type breakdown
    type_counts = {}
    for vlist in sub["violation_list"]:
        for v in vlist:
            type_counts[v] = type_counts.get(v, 0) + 1
    type_counts = dict(sorted(type_counts.items(), key=lambda x: -x[1])[:10])

    # hourly pattern
    hourly = sub["hour"].value_counts().sort_index().to_dict()
    hourly = {int(k): int(v) for k, v in hourly.items()}

    # nearest congestion event
    dists = haversine(row.iloc[0]["lat"], row.iloc[0]["lon"], congestion_events["latitude"].values, congestion_events["longitude"].values)
    nearest_m = float(dists.min() * 1000) if len(dists) else None

    row_dict = row.iloc[0].to_dict()
    for k, v in row_dict.items():
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            row_dict[k] = round(float(v), 4)

    return {
        **row_dict,
        "violation_type_breakdown": type_counts,
        "hourly_pattern": hourly,
        "nearest_congestion_event_m": round(nearest_m, 0) if nearest_m is not None else None,
        "vehicle_types": sub["vehicle_type"].value_counts().head(5).to_dict(),
    }


@app.get("/api/stats/overview")
def stats_overview():
    return {
        "total_violations": int(len(clustered_df)),
        "total_hotspots": int(len(scores_df)),
        "noise_points_excluded": int(298445 - len(clustered_df)),
        "date_range": {
            "start": str(clustered_df["created_ist"].min()),
            "end": str(clustered_df["created_ist"].max()),
        },
        "top_violation_types": clustered_df["violation_list"].explode().value_counts().head(8).to_dict(),
        "top_stations_by_volume": clustered_df["police_station"].value_counts().head(8).to_dict(),
    }


@app.get("/api/stats/hourly")
def stats_hourly():
    return clustered_df["hour"].value_counts().sort_index().to_dict()


def _match_rate(df, radius_km):
    matches = 0
    for _, row in df.iterrows():
        d = haversine(row["lat"], row["lon"], congestion_events["latitude"].values, congestion_events["longitude"].values)
        if len(d) and d.min() <= radius_km:
            matches += 1
    return matches / len(df) * 100 if len(df) else 0.0


def _compute_validation_baseline(n_trials: int = 300, sample_size: int = 50, radius_km: float = 0.5):
    """
    Precomputed once at startup: how often does a RANDOM set of hotspot clusters
    (not ranked by our score) land within radius_km of a real congestion event?
    This is the honest comparison point for our top-N match rate — without it,
    a bare match-rate number can't be distinguished from chance, since congestion
    events and violation hotspots both naturally concentrate in dense urban zones.
    """
    rng = np.random.default_rng(42)
    rates = []
    n = len(scores_df)
    for _ in range(n_trials):
        idx = rng.choice(n, size=min(sample_size, n), replace=False)
        sample = scores_df.iloc[idx]
        rates.append(_match_rate(sample, radius_km))
    rates = np.array(rates)
    return {
        "trials": n_trials,
        "sample_size": sample_size,
        "mean_pct": round(float(rates.mean()), 1),
        "std_pct": round(float(rates.std()), 1),
        "p95_pct": round(float(np.percentile(rates, 95)), 1),
    }


# Precomputed once at startup (not per-request) since the underlying data is static
_VALIDATION_BASELINE = _compute_validation_baseline()
_ALL_CLUSTERS_MATCH_RATE = round(_match_rate(scores_df, 0.5), 1)


@app.get("/api/validation/congestion-correlation")
def validation_correlation(top_n: int = Query(50, le=654), radius_m: int = Query(500)):
    """
    Validates predicted hotspots against real Astram congestion/road-condition events,
    WITH a random-baseline comparison so the match rate is interpretable rather than
    a bare number that could be mistaken for proof on its own.
    """
    top = scores_df.sort_values("congestion_impact_score", ascending=False).head(top_n)
    matches = []
    for _, r in top.iterrows():
        dists = haversine(r["lat"], r["lon"], congestion_events["latitude"].values, congestion_events["longitude"].values)
        if len(dists) and dists.min() * 1000 <= radius_m:
            matches.append({"cluster_id": int(r["cluster_id"]), "station": r["top_station"], "distance_m": round(float(dists.min() * 1000), 0)})

    our_rate = round(len(matches) / top_n * 100, 1)

    # Use precomputed baseline directly when params match the precomputed defaults
    # (top_n=50, radius_m=500); otherwise compute a fresh one on the fly for this request.
    if top_n == 50 and radius_m == 500:
        baseline = _VALIDATION_BASELINE
        all_clusters_rate = _ALL_CLUSTERS_MATCH_RATE
    else:
        baseline = _compute_validation_baseline(n_trials=100, sample_size=top_n, radius_km=radius_m / 1000)
        all_clusters_rate = round(_match_rate(scores_df, radius_m / 1000), 1)

    lift_x = round(our_rate / baseline["mean_pct"], 2) if baseline["mean_pct"] > 0 else None

    return {
        "top_n_checked": top_n,
        "radius_m": radius_m,
        "total_congestion_events_in_dataset": int(len(congestion_events)),
        "matched_hotspots": len(matches),
        "match_rate_pct": our_rate,
        "random_baseline": baseline,
        "all_clusters_match_rate_pct": all_clusters_rate,
        "lift_vs_random_baseline_x": lift_x,
        "matches": matches,
    }


DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def time_bucket(hour: int) -> str:
    if 6 <= hour < 11:
        return "Morning (06:00-11:00)"
    if 11 <= hour < 15:
        return "Midday (11:00-15:00)"
    if 15 <= hour < 19:
        return "Evening (15:00-19:00)"
    return "Night (19:00-06:00)"


@app.get("/api/enforcement/recommendations")
def enforcement_recommendations(top_n: int = Query(20, le=100)):
    """
    Recommended patrol windows per priority zone.
    Uses precise peak-hour windows when a zone has enough data to be statistically
    meaningful (>=30 violations); otherwise falls back to a broader time-of-day
    bucket plus a low-confidence flag, since hour-level peaks on small samples
    are noise, not signal.
    """
    top = scores_df.sort_values("congestion_impact_score", ascending=False).head(top_n)
    recs = []
    for _, row in top.iterrows():
        sub = clustered_df[clustered_df["cluster_id"] == row["cluster_id"]].copy()
        sub["dow_num"] = sub["created_ist"].dt.dayofweek
        n = len(sub)
        confident = n >= 30

        if confident:
            hour_counts = sub["hour"].value_counts()
            peak_hours = sorted(hour_counts.nlargest(2).index.tolist())
            window = f"{peak_hours[0]:02d}:00-{peak_hours[-1]+1:02d}:00"
        else:
            top_bucket = sub["hour"].apply(time_bucket).value_counts().idxmax()
            window = top_bucket

        dow_counts = sub["dow_num"].value_counts(normalize=True)
        top_days = sorted(dow_counts.nlargest(3).index.tolist())
        days = [DAY_NAMES[d] for d in top_days]

        recs.append({
            "cluster_id": int(row["cluster_id"]),
            "station": row["top_station"],
            "lat": round(float(row["lat"]), 5),
            "lon": round(float(row["lon"]), 5),
            "violation_count": int(row["violation_count"]),
            "congestion_impact_score": round(float(row["congestion_impact_score"]), 4),
            "recommended_window": window,
            "recommended_days": days,
            "confidence": "high" if confident else "low (small sample, monitor before committing resources)",
        })

    return {"top_n": top_n, "recommendations": recs}


@app.get("/api/events/congestion")
def congestion_event_locations():
    """Real reported congestion/road-condition events for map overlay (validates hotspots visually)."""
    out = congestion_events[["latitude", "longitude", "event_cause", "start_datetime"]].copy()
    out = out.rename(columns={"latitude": "lat", "longitude": "lon"})
    return out.to_dict(orient="records")


@app.get("/api/stats/pareto")
def pareto_efficiency():
    """
    Resource-allocation efficiency stat: what fraction of hotspot zones account for
    what fraction of total violations. Powers the 'patrol fewer zones, cover most
    of the problem' argument.
    """
    df = scores_df.sort_values("violation_count", ascending=False).reset_index(drop=True)
    total = df["violation_count"].sum()
    df["cum_pct"] = df["violation_count"].cumsum() / total * 100
    df["zone_pct"] = (df.index + 1) / len(df) * 100

    n10 = max(1, int(len(df) * 0.10))
    top10_cum_pct = float(df.loc[n10 - 1, "cum_pct"])

    milestones = {}
    for target in [50, 80, 90]:
        idx = int((df["cum_pct"] >= target).idxmax())
        milestones[f"top_{target}pct_violations"] = {
            "zones_needed": idx + 1,
            "pct_of_all_zones": round(float(df.loc[idx, "zone_pct"]), 1),
        }

    return {
        "total_zones": len(df),
        "total_violations": int(total),
        "top_10pct_zone_count": n10,
        "top_10pct_violation_coverage_pct": round(top10_cum_pct, 1),
        "milestones": milestones,
        "curve": df[["zone_pct", "cum_pct"]].round(2).iloc[::max(1, len(df)//60)].to_dict(orient="records"),
    }


@app.get("/api/violations/sample")
def violations_sample(n: int = Query(2000, le=20000)):
    """Lightweight sampled raw points for heatmap rendering (avoids sending all 298k points)."""
    sample = clustered_df.sample(min(n, len(clustered_df)), random_state=42)
    return sample[["latitude", "longitude", "police_station", "hour"]].to_dict(orient="records")
