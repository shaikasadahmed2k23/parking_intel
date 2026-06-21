# Concept Note: Parking Violation Intelligence & Enforcement Prioritization System

**Theme:** Poor Visibility on Parking-Induced Congestion
**Track:** Flipkart 2.0 Hackathon — Round 2

---

## 1. The Problem

On-street illegal parking and spillover parking near commercial areas, metro
stations, and event venues choke carriageways and intersections. Today's
enforcement is patrol-based and reactive: there is no heatmap connecting parking
violations to their actual impact on traffic flow, so enforcement zones can't be
prioritized — officers patrol on experience and instinct, not data.

## 2. Our Solution, in One Line

A system that turns 5 months of raw parking-violation records into a **ranked,
explainable list of enforcement priority zones**, each with a quantified
congestion-impact score, validated against real-world reported congestion
incidents, and paired with a recommended patrol window.

## 3. Methodology

### Step 1 — Detect: Spatial Hotspot Clustering
We don't look at violations as isolated points; we cluster them. Using DBSCAN with
an 80-meter radius on the 298,445 geocoded violation records, we identify 654
distinct hotspot clusters — real-world chokepoints, not GPS noise (only 1.9% of
points were unclustered noise).

### Step 2 — Quantify: Congestion-Impact Proxy
The provided dataset has no direct traffic-speed or congestion-sensor data, so we
built a composite proxy score per hotspot, deliberately weighted toward signals
that plausibly reflect actual carriageway disruption rather than just ticket
volume:

| Signal | Weight | Why it matters |
|---|---|---|
| Violation volume | 30% | Baseline activity level |
| Road-blocking violation ratio (main-road/footpath/double parking vs. generic no-parking) | 25% | A car blocking a main road disrupts flow far more than one in a quiet no-parking zone |
| Junction presence | 25% | Violations at named junctions affect intersection throughput, not just a single lane |
| Repeat-offender ratio | 10% | Chronic, structural problem locations vs. one-off incidents |
| Time-of-day concentration | 10% | Predictable peak-hour patrol value |

This is an explicit design choice: **volume alone is a misleading metric.** A
junction with 50 violations, all main-road-blocking, at peak hour, is a bigger
congestion risk than a back-street with 500 generic no-parking tickets spread
across the day. Our top-ranked zones by this score include several junctions
(Magadi Road, Chamarajpet, Jayanagara) that don't even appear in a pure
volume-ranking — this is the core value-add over naive "most tickets" heatmaps.

### Step 3 — Validate: Ground-Truth Cross-Check, With a Baseline
To test whether our proxy actually means something, we cross-referenced our
top-50 predicted hotspots against the Astram event dataset's independently
reported `congestion` and `road_conditions` events — data our scoring model never
saw.

**Raw result: 36% of our top-50 predicted hotspots fall within 500m of a real
reported congestion event.** But a bare match-rate number isn't proof on its
own — congestion events and violation hotspots both naturally concentrate in
dense urban zones, so almost *any* set of hotspots could show a deceptively
high match rate purely from geographic overlap, with no real signal in the
ranking at all. We treated this as the single most important number to stress-test
before trusting it.

**The check:** we ran 300 trials of randomly selecting 50 clusters (out of all
654, ignoring our ranking entirely) and computed their match rate against the
same ground-truth events. Random selection averages **24.7%** (95th percentile:
34%). Our top-50 by congestion-impact score hits **36%** — beating roughly 95%
of random draws, a **1.46x lift** over chance. We also confirmed this holds
across match radii from 200m to 2,000m (not just at exactly 500m), so the
result isn't an artifact of one cherry-picked threshold:

| Radius | Our Top-50 | Random-50 Baseline |
|---|---|---|
| 200m | 14.0% | 10.0% |
| 300m | 24.0% | 15.2% |
| 500m | 36.0% | 24.9% |
| 750m | 50.0% | 39.5% |
| 1000m | 64.0% | 50.6% |

**Honest framing:** this is a real, statistically meaningful signal — not
noise — but it's a moderate lift, not an overwhelming one, given only 306
ground-truth events exist citywide to validate against. We'd rather present
that precisely than oversell a bare percentage.

### Step 4 — Recommend: Targeted Enforcement Windows
For each priority zone we compute a recommended patrol time window and day
pattern from historical peak activity. Crucially, we flag confidence: zones with
fewer than 30 violations get a broader time-of-day bucket and a "low confidence"
flag rather than a falsely precise hour-level recommendation — we don't want to
mislead patrol planning with noise from small samples.

### Step 5 — Prove the Value-Add: Volume vs. Impact Ranking
To make the "impact ≠ volume" argument concrete rather than asserted, the
dashboard includes a live toggle comparing each zone's rank under naive
volume-sorting vs. our congestion-impact score. The clearest example: **Magadi
Road ranks #486 by raw violation count (only 17 tickets) but #2 by congestion
impact** — because nearly all of its violations are at a named junction and are
road-blocking types. A volume-only heatmap would never surface this zone; our
model does, because we explicitly designed the score to capture structural
chokepoint risk rather than ticket volume alone.

### Step 6 — Resource-Allocation Efficiency (Pareto Analysis)
We computed what fraction of hotspot zones account for what fraction of total
violations: **the top 10% of hotspot zones (65 of 654) account for 86.5% of all
violations citywide.** This is a directly actionable resource-allocation
argument — a department patrolling these 65 zones covers the large majority of
the problem, instead of spreading resources thinly across 654 scattered
locations.

## 4. System Architecture

- **Data pipeline (Python/pandas/scikit-learn):** cleaning, DBSCAN clustering,
  scoring — runs offline/batch, outputs to Parquet.
- **Backend (FastAPI):** serves processed hotspot, validation, and recommendation
  data via REST endpoints.
- **Frontend (React):** a live "Traffic Ops Console" — map with severity-colored
  hotspot markers, ranked priority panel, zone drill-down with violation-type
  breakdown, hourly pattern chart, and the validation proof card front and
  center.

## 5. Impact

- Converts reactive, patrol-instinct enforcement into a **ranked, explainable
  priority list** enforcement planners can act on directly.
- Surfaces **structural chokepoints** (high repeat-offender, junction-heavy
  zones) that pure volume-based heatmaps miss.
- Gives a **validated** confidence signal (1.46x lift over random baseline,
  not just a bare match-rate percentage) instead of an unverifiable black-box
  score.
- Recommends **when**, not just **where** — directly actionable patrol windows.

## 6. Anticipated Questions

**Why 80m for the DBSCAN clustering radius?**
Domain-reasoned, not fit to data: 80m approximates a single street segment or
junction footprint in dense urban Bengaluru — small enough to avoid merging
distinct chokepoints, large enough to absorb GPS jitter in the source data. We
had no labeled ground-truth hotspots to grid-search a radius against, so we
chose a physically interpretable value rather than overfitting to an arbitrary
metric.

**Why those specific scoring weights (30% volume / 25% road-blocking type /
25% junction presence / 10% repeat-offender / 10% time-concentration)?**
Same reasoning — domain-weighted, not fit to data, since we had no labeled
congestion-severity targets to optimize weights against. Volume and
road-blocking type got the highest weight because they're the most direct
proxies for carriageway disruption; repeat-offender ratio and time
concentration are secondary refinements. Critically, we validated the
*output* of these weights against ground truth (the baseline comparison in
Step 3) rather than fitting the weights themselves to the validation set,
which would risk overfitting on only 306 ground-truth events.

**Is the 36% match rate cherry-picked at 500m?**
No — see the radius curve in Step 3. Our model beats the random baseline
consistently from 200m to 2,000m, not just at one threshold.

## 7. Honesty About Limitations & Roadmap

We're explicit that the congestion-impact score is a *proxy*, built because the
provided dataset has no direct traffic-speed/sensor feed. Production roadmap:

- Replace/calibrate the proxy against a live traffic-speed API (Google Maps/HERE)
  for real congestion-delay quantification.
- Move from batch (5-month historical) to real-time violation ingestion.
- Auto-generate weekly enforcement deployment plans, exportable to patrol
  scheduling systems.
- Mobile companion app for patrol officers showing live priority zones.

## 8. Why This Approach

We chose to build a complete, demonstrable pipeline on the provided dataset
rather than a slide-only concept, because the dataset (298K geocoded records)
was rich enough to support real clustering, real scoring, and — critically — real
validation against an independent ground-truth source already present in the
hackathon's own data. That validation step is what separates this from "just
another heatmap."
