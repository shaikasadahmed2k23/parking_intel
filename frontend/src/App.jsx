import { useEffect, useState, useRef, useMemo } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
} from 'recharts';
import './index.css';

// const API = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';
const API = import.meta.env.VITE_API_URL ?? "http://localhost:8000/api";

function severityColor(score) {
  if (score >= 0.5) return '#EF4444';
  if (score >= 0.3) return '#F2A93B';
  return '#34D399';
}

function fmt(n) {
  if (n === null || n === undefined) return '—';
  return Number(n).toLocaleString();
}

export default function App() {
  const [hotspots, setHotspots] = useState([]);
  const [overview, setOverview] = useState(null);
  const [hourly, setHourly] = useState({});
  const [validation, setValidation] = useState(null);
  const [recommendations, setRecommendations] = useState([]);
  const [congestionEvents, setCongestionEvents] = useState([]);
  const [pareto, setPareto] = useState(null);
  const [showComparison, setShowComparison] = useState(false);
  const [rankComparison, setRankComparison] = useState([]);
  const [showCongestionLayer, setShowCongestionLayer] = useState(true);
  const [selected, setSelected] = useState(null);
  const [detail, setDetail] = useState(null);
  const [sortBy, setSortBy] = useState('congestion_impact_score');
  const [loading, setLoading] = useState(true);
  const [apiError, setApiError] = useState(false);

  const mapRef = useRef(null);
  const mapInstance = useRef(null);
  const markersLayer = useRef(null);
  const congestionLayer = useRef(null);

  useEffect(() => {
    setLoading(true);
    setApiError(false);
    Promise.all([
      fetch(`${API}/hotspots?limit=80&sort_by=${sortBy}`).then(r => r.json()),
      fetch(`${API}/stats/overview`).then(r => r.json()),
      fetch(`${API}/stats/hourly`).then(r => r.json()),
      fetch(`${API}/validation/congestion-correlation?top_n=50`).then(r => r.json()),
      fetch(`${API}/enforcement/recommendations?top_n=12`).then(r => r.json()),
      fetch(`${API}/events/congestion`).then(r => r.json()),
      fetch(`${API}/stats/pareto`).then(r => r.json()),
      fetch(`${API}/hotspots/rank-comparison?top_n=40`).then(r => r.json()),
    ]).then(([hs, ov, hr, val, rec, cev, par, rcomp]) => {
      setHotspots(hs);
      setOverview(ov);
      setHourly(hr);
      setValidation(val);
      setRecommendations(rec.recommendations || []);
      setCongestionEvents(cev);
      setPareto(par);
      setRankComparison(rcomp);
      setLoading(false);
    }).catch(() => { setLoading(false); setApiError(true); });
  }, [sortBy]);

  useEffect(() => {
    if (!mapRef.current || mapInstance.current) return;
    const map = L.map(mapRef.current, {
      zoomControl: true,
      attributionControl: false,
    }).setView([12.9716, 77.5946], 12);

    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      maxZoom: 19,
    }).addTo(map);

    markersLayer.current = L.layerGroup().addTo(map);
    congestionLayer.current = L.layerGroup().addTo(map);
    mapInstance.current = map;
  }, []);

  useEffect(() => {
    if (!mapInstance.current || !markersLayer.current) return;
    markersLayer.current.clearLayers();

    hotspots.forEach((h) => {
      const radius = 5 + Math.min(h.violation_count, 5000) / 5000 * 14;
      const color = severityColor(h.congestion_impact_score);
      const marker = L.circleMarker([h.lat, h.lon], {
        radius,
        color,
        fillColor: color,
        fillOpacity: 0.35,
        weight: 2,
      });
      marker.on('click', () => setSelected(h.cluster_id));
      marker.addTo(markersLayer.current);
    });
  }, [hotspots]);

  // congestion event overlay layer
  useEffect(() => {
    if (!mapInstance.current || !congestionLayer.current) return;
    congestionLayer.current.clearLayers();
    if (!showCongestionLayer) return;

    congestionEvents.forEach((ev) => {
      const icon = L.divIcon({
        className: 'congestion-marker',
        html: `<div style="
          width: 10px; height: 10px; background: #5EC9F2; border: 1.5px solid #0d1014;
          transform: rotate(45deg); box-shadow: 0 0 4px rgba(94,201,242,0.7);
        "></div>`,
        iconSize: [10, 10],
        iconAnchor: [5, 5],
      });
      L.marker([ev.lat, ev.lon], { icon })
        .bindTooltip(`Reported: ${ev.event_cause}`, { direction: 'top' })
        .addTo(congestionLayer.current);
    });
  }, [congestionEvents, showCongestionLayer]);

  useEffect(() => {
    if (selected === null) { setDetail(null); return; }
    fetch(`${API}/hotspots/${selected}`).then(r => r.json()).then(setDetail);
    const h = hotspots.find(x => x.cluster_id === selected);
    if (h && mapInstance.current) {
      mapInstance.current.flyTo([h.lat, h.lon], 15, { duration: 0.6 });
    }
  }, [selected]);

  const hourlyChartData = useMemo(() => {
    return Array.from({ length: 24 }, (_, h) => ({
      hour: h,
      count: hourly[h] || hourly[String(h)] || 0,
    }));
  }, [hourly]);

  const peakHour = useMemo(() => {
    if (!hourlyChartData.length) return null;
    return hourlyChartData.reduce((a, b) => (b.count > a.count ? b : a));
  }, [hourlyChartData]);

  return (
    <div className="app">
      <header className="header">
        <div>
          <div className="header-title"><span className="pulse" /> Parking Violation Intelligence</div>
          <div className="header-sub">Enforcement Prioritization Console — Bengaluru</div>
        </div>
        <div className="header-meta">
          {overview && `${overview.date_range.start.slice(0,10)} — ${overview.date_range.end.slice(0,10)}`}
          <br />
          DATASET: JAN–MAY POLICE VIOLATIONS
        </div>
      </header>

      {apiError && (
        <div style={{
          background: 'rgba(239,68,68,0.12)', borderBottom: '1px solid var(--red)',
          color: '#FCA5A5', fontFamily: 'var(--font-mono)', fontSize: 12,
          padding: '10px 28px',
        }}>
          ⚠ Cannot reach the API at {API}. Make sure the backend is running:
          <code style={{marginLeft: 6}}>cd backend && uvicorn main:app --reload --port 8000</code>
        </div>
      )}

      <div className="kpi-strip">
        <div className="kpi">
          <div className="kpi-label">Total Violations</div>
          <div className="kpi-value">{overview ? fmt(overview.total_violations) : '—'}</div>
        </div>
        <div className="kpi">
          <div className="kpi-label">Hotspot Clusters</div>
          <div className="kpi-value accent">{overview ? fmt(overview.total_hotspots) : '—'}</div>
        </div>
        <div className="kpi">
          <div className="kpi-label">Peak Hour</div>
          <div className="kpi-value">{peakHour ? `${String(peakHour.hour).padStart(2,'0')}:00` : '—'}</div>
        </div>
        <div className="kpi">
          <div className="kpi-label">Top Violation</div>
          <div className="kpi-value" style={{fontSize: 16}}>
            {overview ? Object.keys(overview.top_violation_types)[0] : '—'}
          </div>
        </div>
        <div className="kpi">
          <div className="kpi-label">Congestion Match Rate</div>
          <div className="kpi-value teal">{validation ? `${validation.match_rate_pct}%` : '—'}</div>
        </div>
        <div className="kpi">
          <div className="kpi-label">Top 10% Zones Cover</div>
          <div className="kpi-value teal">{pareto ? `${pareto.top_10pct_violation_coverage_pct}%` : '—'}</div>
        </div>
      </div>

      <div className="main">
        <div className="panel">
          <div className="panel-header">
            <div className="panel-title">Hotspot Map <span className="count">({hotspots.length})</span></div>
            <div style={{display: 'flex', gap: 8, alignItems: 'center'}}>
              <button
                onClick={() => setShowCongestionLayer(s => !s)}
                style={{
                  background: showCongestionLayer ? 'rgba(94,201,242,0.15)' : 'var(--surface-raised)',
                  color: showCongestionLayer ? '#5EC9F2' : 'var(--text-muted)',
                  border: `1px solid ${showCongestionLayer ? '#5EC9F2' : 'var(--border)'}`,
                  borderRadius: 4, fontFamily: 'var(--font-mono)', fontSize: 11,
                  padding: '4px 8px', cursor: 'pointer',
                }}
              >
                ◆ Congestion Events ({congestionEvents.length})
              </button>
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
                style={{
                  background: 'var(--surface-raised)', color: 'var(--text)',
                  border: '1px solid var(--border)', borderRadius: 4,
                  fontFamily: 'var(--font-mono)', fontSize: 11, padding: '4px 8px',
                }}
              >
                <option value="congestion_impact_score">Sort: Congestion Impact</option>
                <option value="severity_score">Sort: Severity</option>
                <option value="violation_count">Sort: Volume</option>
              </select>
            </div>
          </div>
          <div id="map" ref={mapRef} />
          <div style={{
            display: 'flex', gap: 16, padding: '8px 20px', borderTop: '1px solid var(--border)',
            fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-muted)', alignItems: 'center',
          }}>
            <span><span style={{color: '#EF4444'}}>●</span> High impact</span>
            <span><span style={{color: '#F2A93B'}}>●</span> Medium impact</span>
            <span><span style={{color: '#34D399'}}>●</span> Low impact</span>
            <span style={{marginLeft: 8}}><span style={{color: '#5EC9F2'}}>◆</span> Reported congestion event (ground truth)</span>
            <span style={{marginLeft: 'auto'}}>marker size = violation volume</span>
          </div>
        </div>

        <div className="panel">
          <div className="panel-header">
            <div className="panel-title">Priority Zones</div>
            <button
              onClick={() => setShowComparison(s => !s)}
              style={{
                background: showComparison ? 'rgba(242,169,59,0.15)' : 'var(--surface-raised)',
                color: showComparison ? 'var(--amber)' : 'var(--text-muted)',
                border: `1px solid ${showComparison ? 'var(--amber)' : 'var(--border)'}`,
                borderRadius: 4, fontFamily: 'var(--font-mono)', fontSize: 10,
                padding: '4px 8px', cursor: 'pointer',
              }}
            >
              {showComparison ? 'Show Impact Rank' : 'Compare vs. Volume Rank'}
            </button>
          </div>
          <div className="priority-list">
            {!showComparison && hotspots.map((h, i) => (
              <div
                key={h.cluster_id}
                className={`priority-item ${selected === h.cluster_id ? 'active' : ''}`}
                onClick={() => setSelected(h.cluster_id)}
              >
                <div className="priority-rank">{String(i + 1).padStart(2, '0')}</div>
                <div className="priority-info">
                  <div className="priority-station">{h.top_station}</div>
                  <div className="priority-meta">{fmt(h.violation_count)} violations · {(h.junction_ratio*100).toFixed(0)}% junction</div>
                </div>
                <div
                  className="severity-ring"
                  style={{
                    border: `2px solid ${severityColor(h.congestion_impact_score)}`,
                    color: severityColor(h.congestion_impact_score),
                  }}
                >
                  {(h.congestion_impact_score * 100).toFixed(0)}
                </div>
              </div>
            ))}

            {showComparison && rankComparison.map((r) => (
              <div
                key={r.cluster_id}
                className="priority-item"
                onClick={() => setSelected(r.cluster_id)}
              >
                <div className="priority-rank">#{r.impact_rank}</div>
                <div className="priority-info">
                  <div className="priority-station">{r.top_station}</div>
                  <div className="priority-meta">
                    volume rank #{r.volume_rank} → impact rank #{r.impact_rank}
                  </div>
                </div>
                <div
                  className="severity-ring"
                  style={{
                    border: `2px solid ${r.rank_delta > 0 ? 'var(--teal)' : 'var(--text-faint)'}`,
                    color: r.rank_delta > 0 ? 'var(--teal)' : 'var(--text-faint)',
                    fontSize: 10,
                  }}
                >
                  {r.rank_delta > 0 ? `↑${r.rank_delta}` : r.rank_delta}
                </div>
              </div>
            ))}
            {loading && <div className="loading-text">LOADING HOTSPOT DATA…</div>}
          </div>
        </div>
      </div>

      <div className="bottom-row">
        <div className="bottom-panel">
          <div className="panel-title" style={{marginBottom: 14}}>
            {detail ? `Zone Detail — ${detail.top_station}` : 'Hourly Violation Pattern (Citywide)'}
          </div>

          {!detail && (
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={hourlyChartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2C3640" vertical={false} />
                <XAxis dataKey="hour" tick={{ fill: '#8B95A1', fontSize: 10, fontFamily: 'JetBrains Mono' }} tickFormatter={h => String(h).padStart(2,'0')} />
                <YAxis tick={{ fill: '#8B95A1', fontSize: 10, fontFamily: 'JetBrains Mono' }} />
                <Tooltip
                  contentStyle={{ background: '#1B2128', border: '1px solid #2C3640', fontFamily: 'JetBrains Mono', fontSize: 12 }}
                  labelFormatter={h => `${String(h).padStart(2,'0')}:00`}
                />
                <Bar dataKey="count" radius={[3,3,0,0]}>
                  {hourlyChartData.map((d, i) => (
                    <Cell key={i} fill={d.hour === peakHour?.hour ? '#F2A93B' : '#3A4452'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}

          {detail && (
            <>
              <div className="detail-grid">
                <div>
                  <div className="detail-stat-label">Violations</div>
                  <div className="detail-stat-value">{fmt(detail.violation_count)}</div>
                </div>
                <div>
                  <div className="detail-stat-label">Unique Vehicles</div>
                  <div className="detail-stat-value">{fmt(detail.unique_vehicles)}</div>
                </div>
                <div>
                  <div className="detail-stat-label">Repeat Offender Ratio</div>
                  <div className="detail-stat-value">{(detail.repeat_ratio*100).toFixed(0)}%</div>
                </div>
                <div>
                  <div className="detail-stat-label">Nearest Congestion Event</div>
                  <div className="detail-stat-value">
                    {detail.nearest_congestion_event_m !== null ? `${detail.nearest_congestion_event_m.toFixed(0)} m` : '—'}
                  </div>
                </div>
              </div>
              <div className="detail-stat-label" style={{marginBottom: 4}}>Top Violation Types</div>
              <div className="tag-row">
                {Object.entries(detail.violation_type_breakdown || {}).slice(0,6).map(([k,v]) => (
                  <span className="tag" key={k}>{k} · {v}</span>
                ))}
              </div>
              <div
                style={{marginTop: 12, fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-faint)', cursor: 'pointer'}}
                onClick={() => setSelected(null)}
              >
                ← back to citywide pattern
              </div>
            </>
          )}
        </div>

        <div className="bottom-panel">
          <div className="panel-title" style={{marginBottom: 14}}>Ground-Truth Validation</div>
          {validation && (
            <div className="validation-card">
              <div style={{display: 'flex', alignItems: 'baseline', gap: 10}}>
                <div className="validation-headline">{validation.match_rate_pct}%</div>
                <div style={{fontFamily: 'var(--font-mono)', fontSize: 13, color: 'var(--amber)', fontWeight: 600}}>
                  ({validation.lift_vs_random_baseline_x}x random baseline)
                </div>
              </div>
              <div className="validation-text">
                Of our top {validation.top_n_checked} predicted hotspots, {validation.matched_hotspots} sit within {validation.radius_m}m
                of a real reported congestion/road-condition event. We compared this against a random baseline — picking{' '}
                {validation.random_baseline.sample_size} random clusters instead of our top-ranked ones — across {validation.random_baseline.trials}{' '}
                trials, which lands at {validation.random_baseline.mean_pct}% on average (95th percentile: {validation.random_baseline.p95_pct}%).
                Our score beats random selection, not just chance geographic overlap.
              </div>

              <div style={{marginTop: 4}}>
                <div style={{display: 'flex', justifyContent: 'space-between', fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-muted)', marginBottom: 3}}>
                  <span>OUR TOP-{validation.top_n_checked}</span>
                  <span>{validation.match_rate_pct}%</span>
                </div>
                <div className="validation-bar-track">
                  <div className="validation-bar-fill" style={{width: `${validation.match_rate_pct}%`}} />
                </div>
              </div>

              <div style={{marginTop: 8}}>
                <div style={{display: 'flex', justifyContent: 'space-between', fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-faint)', marginBottom: 3}}>
                  <span>RANDOM BASELINE (AVG)</span>
                  <span>{validation.random_baseline.mean_pct}%</span>
                </div>
                <div className="validation-bar-track">
                  <div
                    className="validation-bar-fill"
                    style={{width: `${validation.random_baseline.mean_pct}%`, background: 'var(--text-faint)'}}
                  />
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="bottom-panel" style={{maxHeight: 320, overflowY: 'auto'}}>
          <div className="panel-title" style={{marginBottom: 14}}>Recommended Patrol Schedule</div>
          {recommendations.map((r) => (
            <div key={r.cluster_id} style={{
              padding: '8px 0', borderBottom: '1px solid var(--border)',
              fontSize: 12,
            }}>
              <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'baseline'}}>
                <span style={{fontWeight: 600, color: 'var(--text)'}}>{r.station}</span>
                <span style={{
                  fontFamily: 'var(--font-mono)', fontSize: 10,
                  color: r.confidence === 'high' ? 'var(--teal)' : 'var(--text-faint)',
                }}>
                  {r.confidence === 'high' ? 'HIGH CONF' : 'LOW CONF'}
                </span>
              </div>
              <div style={{fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)', marginTop: 2}}>
                {r.recommended_window} · {r.recommended_days.join('/')}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
