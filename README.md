# 🚦 Parking Violation Intelligence & Enforcement Prioritization System

Secure. Intelligent. Actionable. An AI-powered parking intelligence platform that detects illegal parking hotspots, quantifies their traffic impact, validates findings against real-world congestion events, and recommends targeted enforcement strategies — built for the Flipkart 2.0 Hackathon.

![Python](https://img.shields.io/badge/Python-3.11-blue?style=for-the-badge)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688?style=for-the-badge)
![React](https://img.shields.io/badge/React-Frontend-61DAFB?style=for-the-badge)
![Vite](https://img.shields.io/badge/Vite-Build_Tool-646CFF?style=for-the-badge)
![Leaflet](https://img.shields.io/badge/Leaflet-Mapping-199900?style=for-the-badge)
![Pandas](https://img.shields.io/badge/Pandas-Data_Processing-150458?style=for-the-badge)
![Scikit--Learn](https://img.shields.io/badge/Scikit--Learn-ML-F7931E?style=for-the-badge)
![DBSCAN](https://img.shields.io/badge/DBSCAN-Spatial_Clustering-red?style=for-the-badge)
![Parquet](https://img.shields.io/badge/Parquet-Analytics-purple?style=for-the-badge)
![MIT License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)

### 🏆 Flipkart 2.0 Hackathon — Round 2
**Theme:** Poor Visibility on Parking-Induced Congestion

🌐 **Live Dashboard:** [Add Deployment Link Here]

---

## 📌 About the Project

Parking violations are more than isolated incidents—they are often indicators of larger traffic bottlenecks. This project transforms over **298,000 parking violation records** into an intelligent enforcement-planning system that identifies congestion-prone hotspots, measures their likely impact on traffic flow, validates predictions against real-world congestion reports, and generates prioritized enforcement recommendations.

Instead of relying on reactive patrols, authorities can use data-driven insights to deploy enforcement resources where they will have the greatest impact on reducing congestion.

> For step-by-step installation, see [SETUP.md](SETUP.md).
> For the full methodology and pitch writeup, see [CONCEPT_NOTE.md](CONCEPT_NOTE.md).

---

## Table of Contents

- [The Problem](#the-problem)
- [Our Approach](#our-approach)
- [Live Dashboard Features](#live-dashboard-features)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [About the `.parquet` Files](#about-the-parquet-files)
- [Quick Start](#quick-start)
- [API Reference](#api-reference)
- [Key Results](#key-results)
- [What's a Proxy vs. What's Validated](#whats-a-proxy-vs-whats-validated)
- [Roadmap](#roadmap)

---

## The Problem

On-street illegal parking and spillover parking near commercial areas, metro
stations, and events chokes carriageways and intersections. Enforcement today
is patrol-based and reactive:

- No heatmap connects parking violations to their actual impact on traffic flow
- Resource deployment decisions are experience-driven, not data-driven
- There's no way to prioritize which zones to enforce first

**Problem statement direction:** *How can AI-driven parking intelligence detect
illegal parking hotspots and quantify their impact on traffic flow to enable
targeted enforcement?*

## Our Approach

We built a four-stage pipeline, each stage answering one part of the problem
statement directly:

1. **Detect** — spatial clustering of 298,445 geocoded parking-violation records
   into 654 real-world hotspot clusters using DBSCAN (80m radius), filtering out
   GPS noise so clusters represent genuine chokepoints.
2. **Quantify impact** — a composite congestion-impact proxy score per hotspot,
   weighted toward signals that plausibly reflect real traffic-flow disruption
   (road-blocking violation types, junction presence, repeat-offender density,
   time-of-day concentration) — not just raw ticket count.
3. **Validate** — cross-checked our top predicted hotspots against independently
   reported congestion/road-condition events from the Astram event dataset.
   **36% of our top-50 hotspots fall within 500m of a real reported congestion
   event**, despite such events being rare (306 total across 5 months). This is
   evidence the proxy captures genuine signal, not arbitrary clustering.
4. **Recommend** — patrol-window recommendations per priority zone (peak
   hour/day), with a confidence flag so small-sample zones don't get
   over-trusted, falsely precise recommendations.

## Live Dashboard Features

The dashboard ("Traffic Ops Console") is a single-page React app that turns the
processed data into something an enforcement planner can actually act on:

| Feature | What it does |
|---|---|
| **KPI strip** | Citywide stats at a glance: total violations, hotspot count, peak hour, top violation type, congestion match rate, and the Pareto efficiency stat (see below) |
| **Hotspot map** | Live map with severity-colored markers (red = high impact, amber = medium, teal = low), sized by violation volume. Click any marker to drill into that zone. |
| **Congestion event overlay** | A toggleable layer plotting the 306 real reported congestion/road-condition events as blue diamonds, so the validation claim is visually checkable against the hotspot markers, not just a number |
| **Priority Zones panel** | Ranked list of hotspots by congestion-impact score — read top to bottom for enforcement deployment order |
| **Volume vs. Impact comparison toggle** | Switches the Priority Zones list to show each zone's rank under naive volume-sorting vs. our impact score, with delta arrows. Makes the "impact ≠ volume" argument concrete — e.g. Magadi Road jumps from rank #486 by volume to rank #2 by impact |
| **Zone detail drill-down** | Click a hotspot to see its violation-type breakdown, hourly pattern, vehicle types, and distance to the nearest real congestion event |
| **Hourly violation pattern chart** | Citywide time-of-day distribution, peak hour highlighted |
| **Ground-Truth Validation card** | The 36% match-rate statistic with a plain-language explanation, live from the API |
| **Recommended Patrol Schedule panel** | Per-zone patrol window + day-of-week pattern, with a HIGH CONF / LOW CONF flag depending on whether the zone has enough data (≥30 violations) for a statistically meaningful hour-level recommendation |
| **Pareto efficiency KPI** | "Top 10% Zones Cover 86.5%" — shows that patrolling a small fraction of zones covers most of the citywide violation volume, a direct resource-allocation argument |
| **Map legend & error handling** | Legend explaining marker colors/shapes; a visible warning banner if the backend API is unreachable, instead of a silently empty dashboard |

## Architecture

```
┌──────────────────┐      ┌──────────────────┐      ┌──────────────────┐
│  Data Pipeline   │ ───▶│ FastAPI Backend   │ ───▶│ React Dashboard  │
├──────────────────┤      ├──────────────────┤      ├──────────────────┤
│ Data Cleaning    │      │ Hotspots API     │      │ Interactive Map  │
│ DBSCAN Clusters  │      │ Validation API   │      │ Rankings         │
│ Severity Scores  │      │ Statistics API   │      │ Zone Analytics   │
│ Validation       │      │ Enforcement API  │      │ Validation View  │
│ Pareto Analysis  │      │ Congestion API   │      │ Patrol Planner   │
└──────────────────┘      └──────────────────┘      └──────────────────┘
```

**Stack:** Python (pandas, scikit-learn) for the pipeline · FastAPI for the
backend · React + Vite + Leaflet + Recharts for the frontend.

## Project Structure

```
parking_intel/
├── README.md                  <- you are here
├── SETUP.md                   <- detailed setup/installation instructions
├── CONCEPT_NOTE.md             <- full methodology & pitch writeup
├── screenshots/
│   └── dashboard-overview.png  <- dashboard screenshot (shown above)
├── clustered.parquet            <- cleaned violations + DBSCAN cluster_id per row (used by backend)
├── hotspot_scores_v2.parquet    <- 654 hotspot clusters with all computed scores (used by backend)
├── pipeline/
│   └── build_pipeline.py       <- full data pipeline: clean → cluster → score. Run to regenerate the parquet files.
├── backend/
│   └── main.py                  <- FastAPI app, all REST endpoints
├── frontend/
│   ├── src/
│   │   ├── App.jsx              <- dashboard (all components)
│   │   └── index.css            <- design tokens / styling ("Traffic Ops Console" theme)
│   └── package.json
└── data/
    └── Astram_event_data...csv  <- ground-truth congestion/event data, used by backend for validation
```

## About the `.parquet` Files

Parquet is just a compressed, columnar file format for storing dataframes —
think of it as a faster, smaller alternative to CSV that pandas reads/writes
natively. Two of them are **required for the app to run**, one is **safe to
delete**:

| File | Required? | What it is |
|---|---|---|
| `clustered.parquet` | **Yes — required by backend** | The full cleaned violation dataset (298,445 rows) with a `cluster_id` column assigned by DBSCAN. The backend loads this directly to serve zone detail breakdowns, hourly patterns, and the violations sample endpoint. |
| `hotspot_scores_v2.parquet` | **Yes — required by backend** | The aggregated, scored output: one row per hotspot cluster (654 rows) with every computed metric (severity score, congestion-impact score, junction ratio, etc). The backend loads this for almost every endpoint. |
| `cleaned_base.parquet` | **No — already removed** | An intermediate checkpoint written partway through the pipeline (cleaned data, before clustering). Nothing reads it back — it was just useful for debugging during development. It's been deleted from this repo; running the pipeline script will recreate it as a byproduct, harmlessly. |

**Bottom line:** don't delete `clustered.parquet` or `hotspot_scores_v2.parquet`
— the backend won't start without them. If you ever do delete them by mistake,
just re-run `python3 pipeline/build_pipeline.py` (see [SETUP.md](SETUP.md)) to
regenerate everything from the raw CSV.

## Quick Start

See [SETUP.md](SETUP.md) for full details. The short version:

```bash
# Backend
cd backend
pip install fastapi uvicorn pandas pyarrow --break-system-packages
uvicorn main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

Then open the URL Vite prints (default `http://localhost:5173`).

## API Reference

All endpoints are served from the FastAPI backend at `http://localhost:8000`.

| Endpoint | Description |
|---|---|
| `GET /api/health` | Sanity check — confirms data is loaded |
| `GET /api/hotspots` | Ranked list of hotspot clusters. Params: `limit`, `sort_by` (`congestion_impact_score` \| `severity_score` \| `violation_count`), `min_violations` |
| `GET /api/hotspots/{cluster_id}` | Drill-down detail: violation-type breakdown, hourly pattern, vehicle types, nearest real congestion event |
| `GET /api/hotspots/rank-comparison` | Each hotspot's rank under volume-sort vs. impact-score-sort, with the delta — powers the comparison toggle |
| `GET /api/stats/overview` | Citywide summary stats (totals, date range, top violation types, top stations) |
| `GET /api/stats/hourly` | Citywide hourly violation distribution |
| `GET /api/stats/pareto` | Resource-allocation efficiency stats — what % of zones account for what % of violations |
| `GET /api/validation/congestion-correlation` | The ground-truth validation check — what % of top hotspots match a real reported congestion event within a given radius |
| `GET /api/enforcement/recommendations` | Per-zone recommended patrol window, day pattern, and confidence flag |
| `GET /api/events/congestion` | Raw coordinates of real reported congestion/road-condition events, for the map overlay |
| `GET /api/violations/sample` | Sampled raw violation points (lat/lon), for any future raw heatmap rendering |

## Key Results

| Metric | Value |
|---|---|
| Violations analyzed | 298,445 (Jan–May) |
| Hotspot clusters identified | 654 |
| Noise points filtered out | 1.9% |
| Top-50 hotspots matched to real congestion events (within 500m) | 36% |
| Random-baseline match rate (300 trials, same sample size) | 24.7% (95th percentile: 34%) |
| Lift vs. random baseline | 1.46x |
| Total ground-truth congestion events in period | 306 |
| Top 10% of zones (65) account for | 86.5% of all violations |
| Biggest volume→impact rank jump (Magadi Road) | #486 by volume → #2 by impact |

**On the validation number specifically:** a bare match-rate percentage is easy
to misread as proof when it isn't one — congestion events and violation
hotspots both naturally concentrate in dense urban zones, so *any* set of
hotspots could show a deceptively high match rate by geographic coincidence
alone. To check this, we ran 300 trials of randomly selecting 50 clusters
(instead of our top-ranked ones) and checking their match rate against the
same ground-truth events. Random selection averages 24.7% (95th percentile:
34%) — our top-50 by congestion-impact score hits 36%, beating roughly 95% of
random draws. That's a real, repeatable signal, not noise, though we want to
be precise about the size of the effect: it's a meaningful 1.46x lift, not an
overwhelming one, given only 306 ground-truth events exist to validate
against. We also checked this holds across radii from 200m–2000m, not just at
500m, to rule out a cherry-picked threshold.

## What's a Proxy vs. What's Validated

We're upfront about this distinction: there's no direct real-time traffic-speed
dataset in the provided data, so "impact on traffic flow" is estimated via a
proxy (violation density × road-blocking type × junction presence × time
concentration). We validated this proxy against independently reported
congestion events — but a bare match-rate number isn't proof on its own,
since both violations and congestion events naturally cluster in dense urban
areas regardless of any scoring logic. So we benchmarked against a random
baseline (see [Key Results](#key-results) above): our top-50 hotspots match
ground-truth events at 36%, vs. a 24.7% average for randomly selected
clusters — a 1.46x lift that holds consistently across match radii from
200m–2000m. That's the actual evidence behind the score, not the bare
percentage alone. In production, this proxy would be replaced/calibrated
against a live traffic-speed API (Google Maps/HERE).

## Roadmap

- Replace the congestion-impact proxy with live traffic-speed API correlation
- Real-time violation ingestion (vs. batch Jan–May historical data)
- Auto-generated, exportable weekly enforcement deployment plans (CSV/PDF)
- Mobile companion app for patrol officers showing live priority zones
