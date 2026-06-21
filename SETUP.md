# Setup & Installation Guide

This document walks through getting the Parking Violation Intelligence dashboard
running from a fresh clone, end to end.

## Prerequisites

| Tool | Version | Check with |
|---|---|---|
| Python | 3.10+ | `python3 --version` |
| pip | any recent | `pip --version` |
| Node.js | 18+ | `node --version` |
| npm | comes with Node | `npm --version` |

No database is required — all data is served from local Parquet/CSV files.

---

## 1. Backend Setup

The backend is a FastAPI app that loads two pre-built Parquet files
(`clustered.parquet`, `hotspot_scores_v2.parquet`) and the Astram event CSV at
startup, then serves them via REST endpoints.

### 1.1 Install dependencies

```bash
cd backend
pip install fastapi uvicorn pandas pyarrow --break-system-packages
```

> If you're on a system where `pip install` works without the
> `--break-system-packages` flag (e.g. inside a virtual environment), you can
> drop it:
> ```bash
> python3 -m venv venv
> source venv/bin/activate        # on Windows: venv\Scripts\activate
> pip install fastapi uvicorn pandas pyarrow
> ```

### 1.2 Run the server

```bash
uvicorn main:app --reload --port 8000
```

You should see:

```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Application startup complete.
```

### 1.3 Verify it's working

```bash
curl http://localhost:8000/api/health
```

Expected response:

```json
{"status":"ok","hotspots_loaded":654,"violations_loaded":292880}
```

If you get a connection error, the server isn't running — check the terminal
for errors. If you get a 500 error or a file-not-found error, check that
`clustered.parquet`, `hotspot_scores_v2.parquet` (project root) and the Astram
CSV (`data/` folder) are present — see [the parquet files section in
README.md](README.md#about-the-parquet-files).

---

## 2. Frontend Setup

The frontend is a Vite + React app that calls the backend API at
`http://localhost:8000`.

### 2.1 Install dependencies

```bash
cd frontend
npm install
```

This installs React, Leaflet (for the map), and Recharts (for the charts),
among others. Takes a minute or two the first time.

### 2.2 Run the dev server

```bash
npm run dev
```

You should see:

```
VITE ready in ### ms
➜  Local:   http://localhost:5173/
```

Open that URL in a browser. You should see the full dashboard load within a
couple of seconds — KPI strip populated, map with markers, priority list,
charts, and the validation card.

### 2.3 If the dashboard loads but shows no data

This means the frontend can't reach the backend. Check:
1. Is the backend still running on port 8000? (`curl http://localhost:8000/api/health`)
2. The dashboard itself will show a red warning banner at the top if it can't
   reach the API — read the message, it tells you the exact command to run.
3. If your backend runs on a different host/port, update the `API` constant at
   the top of `frontend/src/App.jsx`.

### 2.4 Building for production (optional)

```bash
npm run build
```

Output goes to `frontend/dist/` — a static site you can deploy anywhere
(Vercel, Netlify, S3, etc). You'd still need the backend running somewhere
reachable, and you'd update the `API` constant in `App.jsx` to point at that
backend's public URL before building.

---

## 3. Regenerating the Data Pipeline (optional)

The pre-built `clustered.parquet` and `hotspot_scores_v2.parquet` files are
already included in this repo, so **you don't need to do this step to run the
dashboard.** Only do this if you want to regenerate the data from scratch (e.g.
you're using an updated/different raw dataset).

### 3.1 Get the raw data

Place the raw police violation CSV at:

```
data/jan_to_may_police_violation_anonymized791b166.csv
```

(This file is ~105MB and is **not** included in this repo — get it from the
original hackathon dataset link.) The Astram event CSV is already included at
`data/Astram_event_data_anonymized_-_Astram_event_data_anonymizedb40ac87.csv`.

### 3.2 Install pipeline dependencies

```bash
pip install pandas pyarrow scikit-learn --break-system-packages
```

### 3.3 Run the pipeline

From the project root (not inside `pipeline/`):

```bash
python3 pipeline/build_pipeline.py
```

This will print progress for each of the three stages and take roughly
30–90 seconds depending on your machine:

```
[1/3] Cleaning raw data...
      saved .../cleaned_base.parquet (298445 rows)
[2/3] Running DBSCAN hotspot clustering...
      654 clusters, 5565 noise points (1.9%)
      saved .../clustered.parquet
[3/3] Computing congestion-impact severity scores...
      saved .../hotspot_scores_v2.parquet (654 hotspot clusters)
```

Restart the backend afterward (`Ctrl+C` then re-run `uvicorn main:app
--reload --port 8000`) so it picks up the freshly regenerated files.

---

## 4. Common Issues

| Symptom | Likely cause | Fix |
|---|---|---|
| `ModuleNotFoundError: No module named 'fastapi'` | Backend dependencies not installed | Re-run step 1.1 |
| Backend crashes on startup with a file-not-found error | Missing `clustered.parquet` / `hotspot_scores_v2.parquet` / Astram CSV | Make sure these weren't accidentally deleted; see README's parquet section |
| Frontend shows a red "Cannot reach the API" banner | Backend isn't running, or is running on a different port | Start/restart the backend; confirm `curl localhost:8000/api/health` works |
| `npm install` fails | Node version too old | Upgrade to Node 18+ |
| Map tiles don't load (blank/grey map) | No internet connection — map tiles are fetched live from a CDN | Connect to the internet; markers/data still work without tiles, just no basemap |
| Port 8000 or 5173 already in use | Another process is using the port | Kill it, or run on a different port: `uvicorn main:app --port 8001` (and update `API` in `App.jsx` to match) |

---

## 5. Project Layout Recap

```
parking_intel/
├── backend/main.py          <- run this with uvicorn
├── frontend/                <- run this with npm
├── pipeline/build_pipeline.py  <- optional, regenerates data
├── data/                    <- raw + ground-truth CSVs
├── clustered.parquet         <- pre-built data the backend needs
├── hotspot_scores_v2.parquet <- pre-built data the backend needs
└── screenshots/              <- README images
```

That's it — two terminals (`backend` + `frontend`), no database, no external
API keys required.
