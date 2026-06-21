# Deployment Guide — Render (Backend) + Vercel (Frontend)

This mirrors the setup used for ExamFort: FastAPI backend on Render, React
frontend on Vercel. Total time: ~15-20 minutes if nothing goes wrong, longer if
you hit the gotchas listed below (which we've pre-fixed where possible).

---

## Before You Start

Push the project to GitHub first (Render and Vercel both deploy from a repo,
not a zip upload).

```bash
cd parking_intel
git init
git add .
git commit -m "Initial commit: Parking Violation Intelligence"
git branch -M main
git remote add origin https://github.com/<your-username>/<repo-name>.git
git push -u origin main
```

Double-check `clustered.parquet` and `hotspot_scores_v2.parquet` actually got
committed (they're force-included in `.gitignore` via the `!` rule) — run:

```bash
git ls-files | grep parquet
```

You should see both files listed. If not, your `.gitignore` isn't being
respected correctly — re-check the parquet section.

---

## Part 1: Backend on Render

1. Go to [render.com](https://render.com) → **New** → **Web Service**
2. Connect your GitHub repo
3. Configure:
   | Setting | Value |
   |---|---|
   | **Root Directory** | `backend` |
   | **Runtime** | Python 3 |
   | **Build Command** | `pip install -r requirements.txt` |
   | **Start Command** | `uvicorn main:app --host 0.0.0.0 --port $PORT` |
   | **Instance Type** | Free (fine for a hackathon demo) |

4. `runtime.txt` (already included, pins Python 3.11.9) tells Render which
   Python version to use — this avoids the version-incompatibility issues you
   hit with ExamFort.

5. Click **Create Web Service**. First deploy takes a few minutes — watch the
   build logs.

6. Once live, test it:
   ```
   https://<your-service-name>.onrender.com/api/health
   ```
   Should return `{"status":"ok","hotspots_loaded":654,...}`.

> **Note on file paths:** `main.py` locates the parquet files using
> `Path(__file__).resolve().parent.parent` — an absolute path computed at
> runtime, not relative to Render's "Root Directory" setting. Render checks
> out your *entire* repo to disk regardless of that setting (it only affects
> where build/start commands run from), so `clustered.parquet` and
> `hotspot_scores_v2.parquet` at the repo root will still be found correctly
> even with Root Directory set to `backend`. If you do hit a file-not-found
> error on deploy, check the Render build logs for the actual resolved path
> first before assuming this is the cause.

7. Render free-tier services sleep after inactivity and take ~30-50 seconds to
   wake up on the first request — mention this to judges if they hit a slow
   first load, it's not a bug.

---

## Part 2: Frontend on Vercel

1. Go to [vercel.com](https://vercel.com) → **Add New** → **Project**
2. Import the same GitHub repo
3. Configure:
   | Setting | Value |
   |---|---|
   | **Root Directory** | `frontend` |
   | **Framework Preset** | Vite |
   | **Build Command** | `npm run build` (default, already in `vercel.json`) |
   | **Output Directory** | `dist` (default, already in `vercel.json`) |

4. **Critical step** — add an environment variable before deploying:
   | Key | Value |
   |---|---|
   | `VITE_API_URL` | `https://<your-render-service>.onrender.com/api` |

   This is the fix for the "trailing slash env var bug" you hit with
   ExamFort — make sure there's **no trailing slash** after `/api`, and that
   it's `https://`, not `http://`. Vite only picks up env vars prefixed with
   `VITE_` and only at build time, so if you add/change this after the first
   deploy, you need to **redeploy** (not just refresh) for it to take effect.

5. Click **Deploy**. A few minutes later you'll have a live URL like
   `https://parking-intel.vercel.app`.

6. Open it and confirm the dashboard loads real data (not the red "Cannot
   reach the API" banner). If you see that banner, it means `VITE_API_URL`
   either wasn't set correctly or the Render backend isn't awake yet — wait
   ~40 seconds and refresh.

---

## Part 3: Final CORS Check

The backend currently allows all origins (`allow_origins=["*"]`) in
`backend/main.py` — fine for a hackathon demo, no auth/sensitive data
involved. If you want to lock it down to just your Vercel domain before
submission, change it to:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://parking-intel.vercel.app"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Not required, but tidier if a judge inspects the code.

---

## Quick Troubleshooting

| Symptom | Fix |
|---|---|
| Render build fails on `pandas`/`pyarrow` install | Confirm `runtime.txt` (Python 3.11.9) is in the `backend/` folder and being picked up |
| Render deploy succeeds but `/api/health` 500s | Check Render's build/runtime logs for the actual file path it tried to resolve — confirm `clustered.parquet` and `hotspot_scores_v2.parquet` were committed to the repo (see the `git ls-files` check above) |
| Vercel deploy succeeds but dashboard shows the red error banner | `VITE_API_URL` is wrong, has a trailing slash, or you forgot to redeploy after setting it |
| Dashboard loads but map markers are missing | Backend is awake but congestion events/hotspots endpoints might be erroring — check Render logs |
| First load after idle takes 30-50 seconds | Normal for Render free tier — the service was asleep |

---

## What to Submit

Once both are live:
- **Demo Link**: your Vercel frontend URL
- **Repository URL**: your GitHub repo URL
- **Video URL**: record a walkthrough of the live Vercel URL (not localhost) so judges see the actual deployed product
