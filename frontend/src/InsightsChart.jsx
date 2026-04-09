// InsightsChart.jsx
// Pure SVG charts — no external lib required.
// Shows stress history, screen time & activity trends from logged events.

import { useMemo } from "react";
import { TrendingUp, TrendingDown, Minus, Zap } from "lucide-react";

// ─── helpers ─────────────────────────────────────────────────────────────────

/** Weighted average of a posterior distribution object: {0:p0, 1:p1, ...} */
function weightedAvg(dist) {
  if (!dist) return null;
  let score = 0, total = 0;
  for (const [k, v] of Object.entries(dist)) {
    score += Number(k) * v;
    total += v;
  }
  return total > 0 ? score / total : null;
}

/** Max key in a dist (= k-1) */
function maxK(dist) {
  if (!dist) return 2;
  const keys = Object.keys(dist).map(Number);
  return keys.length > 0 ? Math.max(...keys) : 2;
}

/** Normalize a raw state value to 0..1 given k */
function norm(val, k) {
  return k > 0 ? val / k : val;
}

/** Stress color based on normalized 0..1 value */
function stressColor(v) {
  if (v === null) return "#A2ABA1"; // ash
  if (v < 0.4) return "#A2ABA1"; // low -> Ash Gray
  if (v < 0.7) return "#758976"; // mid -> Reseda
  return "#5f6f5e"; // high -> darker Reseda
}

const STATE_LABELS = ["Low", "Med", "High", "V-High"];
const STATE_SHORT = ["L", "M", "H", "V"];

function stateLabel(val) {
  if (val === null || val === undefined) return "—";
  return STATE_LABELS[Math.round(val)] ?? `${val}`;
}

/** Format ts string to short display */
function fmtDate(ts) {
  const d = new Date(ts + "Z");
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function fmtTime(ts) {
  const d = new Date(ts + "Z");
  return d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

// ─── main component ───────────────────────────────────────────────────────────

export default function InsightsChart({ events, loading }) {
  // Sort oldest → newest for charting
  const sorted = useMemo(
    () => [...events].sort((a, b) => a.ts.localeCompare(b.ts)),
    [events]
  );

  // Build per-event point data
  const points = useMemo(() =>
    sorted.map((ev) => {
      const ps = ev.posteriors ?? {};
      const eg = ev.evidence ?? {};
      const kStress = maxK(ps.stress);

      // Stress: prefer observed evidence, fall back to posterior expectation
      const obsStress = eg.stress !== undefined ? eg.stress : null;
      const predStress = ps.stress ? weightedAvg(ps.stress) : null;
      const stressVal = obsStress !== null ? obsStress : predStress;

      return {
        ts: ev.ts,
        stressRaw: stressVal,
        stressNorm: stressVal !== null ? norm(stressVal, kStress) : null,
        hasObsStress: obsStress !== null,
        screenTime: eg.screen_time ?? null,
        activity: eg.activity ?? null,
        mood: eg.mood ?? null,
        sleep: eg.sleep ?? null,
        kStress,
      };
    }),
    [sorted]
  );

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <span className="text-ash text-xs font-mono">loading…</span>
      </div>
    );
  }

  if (points.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center gap-2 p-6">
        <Zap className="w-6 h-6 text-reseda-600" />
        <p className="text-ash text-xs italic text-center leading-relaxed">
          No data yet. Log your day in the chat to start seeing insights.
        </p>
      </div>
    );
  }

  // ── summary stats ──────────────────────────────────────────────────────────
  const stressNorms = points.map((p) => p.stressNorm).filter((v) => v !== null);
  const avgStress = stressNorms.length
    ? stressNorms.reduce((a, b) => a + b, 0) / stressNorms.length
    : null;

  const recent = stressNorms.slice(-3);
  const earlier = stressNorms.slice(0, -3);
  const recentAvg = recent.length ? recent.reduce((a, b) => a + b, 0) / recent.length : null;
  const earlierAvg = earlier.length ? earlier.reduce((a, b) => a + b, 0) / earlier.length : null;
  const trend =
    recentAvg !== null && earlierAvg !== null && stressNorms.length >= 4
      ? recentAvg > earlierAvg + 0.08
        ? "up"
        : recentAvg < earlierAvg - 0.08
        ? "down"
        : "stable"
      : "stable";

  const screenVals = points.map((p) => p.screenTime).filter((v) => v !== null);
  const actVals = points.map((p) => p.activity).filter((v) => v !== null);
  const sleepVals = points.map((p) => p.sleep).filter((v) => v !== null);
  const avgScreen = screenVals.length
    ? screenVals.reduce((a, b) => a + b, 0) / screenVals.length
    : null;
  const avgAct = actVals.length
    ? actVals.reduce((a, b) => a + b, 0) / actVals.length
    : null;
  const avgSleep = sleepVals.length
    ? sleepVals.reduce((a, b) => a + b, 0) / sleepVals.length
    : null;

  const stressPoints = points.filter((p) => p.stressNorm !== null);
  const hasActivityData = screenVals.length > 0 || actVals.length > 0;

  return (
    <div className="flex-1 overflow-y-auto px-3 py-3 space-y-4 min-h-0">
      {/* ── summary cards ───────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 gap-2">
        <StatCard
          label="Avg Stress"
          value={avgStress !== null ? stateLabel(Math.round(avgStress * 2)) : "—"}
          color={stressColor(avgStress)}
          sub={`${stressNorms.length} readings`}
          trend={trend}
        />
        <StatCard
          label="Sleep"
          value={avgSleep !== null ? stateLabel(Math.round(avgSleep)) : "—"}
          color="#A8B5A0"
          sub={`avg state`}
        />
        <StatCard
          label="Screen Time"
          value={avgScreen !== null ? stateLabel(Math.round(avgScreen)) : "—"}
          color="#A8B5A0"
          sub={`avg state`}
        />
        <StatCard
          label="Activity"
          value={avgAct !== null ? stateLabel(Math.round(avgAct)) : "—"}
          color="#B8C4B0"
          sub={`avg state`}
        />
      </div>

      {/* ── stress timeline ──────────────────────────────────────────────── */}
      {stressPoints.length >= 2 && (
        <ChartSection title="Stress Timeline">
          <StressLineChart points={stressPoints} />
        </ChartSection>
      )}

      {/* ── activity vs screen time ──────────────────────────────────────── */}
      {hasActivityData && (
        <ChartSection title="Activity vs Screen Time">
          <ActivityChart points={points} />
        </ChartSection>
      )}

    </div>
  );
}

// ─── sub-components ──────────────────────────────────────────────────────────

function ChartSection({ title, children }) {
  return (
    <div>
      <div className="text-[10px] font-mono uppercase tracking-wider text-ash mb-1.5">
        {title}
      </div>
      {children}
    </div>
  );
}

function StatCard({ label, value, color, sub, trend }) {
  const TrendIcon =
    trend === "up" ? TrendingUp : trend === "down" ? TrendingDown : Minus;
  return (
    <div className="bg-white rounded-xl border border-[rgba(0,0,0,0.05)] p-2.5">
      <div className="text-[9px] font-mono uppercase tracking-wider text-ash mb-1">
        {label}
      </div>
      <div className="flex items-end justify-between gap-1">
        <span
          className="font-display text-lg font-semibold leading-none"
          style={{ color }}
        >
          {value}
        </span>
        {trend && (
          <TrendIcon
            className="w-3 h-3 mb-0.5"
            style={{
              color:
                trend === "up" ? "#ef4444" : trend === "down" ? "#10b981" : "#A2ABA1",
            }}
          />
        )}
      </div>
      <div className="text-[9px] text-ash mt-0.5">{sub}</div>
    </div>
  );
}

// ── Stress Line Chart (pure SVG) ────────────────────────────────────────────

function StressLineChart({ points }) {
  const W = 260,
    H = 90;
  const pad = { top: 8, right: 10, bottom: 22, left: 18 };
  const cW = W - pad.left - pad.right;
  const cH = H - pad.top - pad.bottom;

  const n = points.length;
  const xs = points.map((_, i) => pad.left + (n === 1 ? cW / 2 : (i / (n - 1)) * cW));
  const ys = points.map((p) => pad.top + (1 - p.stressNorm) * cH);

  // Line path
  const linePath = points
    .map((_, i) => `${i === 0 ? "M" : "L"}${xs[i].toFixed(1)},${ys[i].toFixed(1)}`)
    .join(" ");

  // Area fill
  const areaPath = `${linePath} L${xs[n - 1].toFixed(1)},${(pad.top + cH).toFixed(1)} L${xs[0].toFixed(1)},${(pad.top + cH).toFixed(1)} Z`;

  // Grid lines at L/M/H thresholds
  const gridLevels = [
    { v: 1, label: "H" },
    { v: 0.5, label: "M" },
    { v: 0, label: "L" },
  ];

  // X axis: show first and last date labels
  const firstDate = fmtDate(points[0].ts);
  const lastDate = fmtDate(points[n - 1].ts);
  const showMid = n > 4;
  const midIdx = Math.floor(n / 2);
  const midDate = showMid ? fmtDate(points[midIdx].ts) : null;

  return (
    <div className="bg-white/95 rounded-xl border border-sage-200 p-2">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full"
        style={{ height: "90px" }}
        aria-label="Stress timeline"
      >
        <defs>
          <linearGradient id="sg" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#758976" stopOpacity="0.36" />
            <stop offset="100%" stopColor="#758976" stopOpacity="0" />
          </linearGradient>
        </defs>

        {/* Grid */}
        {gridLevels.map(({ v, label }) => {
          const y = pad.top + (1 - v) * cH;
          return (
            <g key={label}>
              <line
                x1={pad.left}
                x2={pad.left + cW}
                y1={y}
                y2={y}
                stroke="#E8E3D8"
                strokeWidth="1"
              />
              <text
                x={pad.left - 4}
                y={y + 3}
                textAnchor="end"
                fontSize="7"
                fill="#A2ABA1"
              >
                {label}
              </text>
            </g>
          );
        })}

        {/* Area */}
        <path d={areaPath} fill="url(#sg)" />

        {/* Line */}
        <path
          d={linePath}
          fill="none"
          stroke="#758976"
          strokeWidth="1.5"
          strokeLinejoin="round"
          strokeLinecap="round"
        />

        {/* Dots */}
        {points.map((p, i) => (
          <circle
            key={i}
            cx={xs[i]}
            cy={ys[i]}
            r={p.hasObsStress ? 3.5 : 2.5}
            fill={stressColor(p.stressNorm)}
            stroke="#758976"
            strokeWidth="1"
          >
            <title>{`${fmtDate(p.ts)} ${fmtTime(p.ts)}\nStress: ${stateLabel(Math.round(p.stressNorm * 2))} (${p.hasObsStress ? "observed" : "predicted"})`}</title>
          </circle>
        ))}

        {/* X axis labels */}
        <text
          x={xs[0]}
          y={H - 2}
          textAnchor="middle"
          fontSize="7"
          fill="#758976"
        >
          {firstDate}
        </text>
        {showMid && midDate && (
          <text
            x={xs[midIdx]}
            y={H - 2}
            textAnchor="middle"
            fontSize="7"
            fill="#758976"
          >
            {midDate}
          </text>
        )}
        {n > 1 && (
          <text
            x={xs[n - 1]}
            y={H - 2}
            textAnchor="middle"
            fontSize="7"
            fill="#758976"
          >
            {lastDate}
          </text>
        )}
      </svg>

      {/* Legend */}
      <div className="flex items-center gap-3 mt-1 px-1">
        <div className="flex items-center gap-1">
          <circle className="inline-block w-2.5 h-2.5 rounded-full" style={{ display: "inline-block", width: 8, height: 8, borderRadius: 999, backgroundColor: "#758976", border: "1.5px solid #758976" }} />
          <span className="text-[9px]" style={{ color: 'var(--color-ash)' }}>observed</span>
        </div>
        <div className="flex items-center gap-1">
          <div style={{ display: "inline-block", width: 8, height: 8, borderRadius: 999, backgroundColor: "#758976", border: "1.5px solid #758976", opacity: 0.5 }} />
          <span className="text-[9px]" style={{ color: 'var(--color-ash)' }}>predicted</span>
        </div>
      </div>
    </div>
  );
}

// ── Activity vs Screen Time Chart ────────────────────────────────────────────

function ActivityChart({ points }) {
  const W = 260,
    H = 80;
  const pad = { top: 8, right: 10, bottom: 22, left: 18 };
  const cW = W - pad.left - pad.right;
  const cH = H - pad.top - pad.bottom;

  // Filter points that have at least one of these
  const filtered = points.filter(
    (p) => p.screenTime !== null || p.activity !== null
  );
  if (filtered.length < 2) {
    return (
      <div className="text-ash text-[10px] italic px-1">
        Not enough data yet.
      </div>
    );
  }

  const n = filtered.length;
  const xs = filtered.map(
    (_, i) => pad.left + (n === 1 ? cW / 2 : (i / (n - 1)) * cW)
  );

  // Max state we ever see across both signals (usually 2)
  const allVals = [
    ...filtered.map((p) => p.screenTime).filter((v) => v !== null),
    ...filtered.map((p) => p.activity).filter((v) => v !== null),
  ];
  const maxVal = allVals.length ? Math.max(...allVals, 2) : 2;

  const toY = (v) =>
    v !== null ? pad.top + (1 - v / maxVal) * cH : null;

  const screenPath = filtered
    .map((p, i) => {
      const y = toY(p.screenTime);
      return y !== null ? `${i === 0 || toY(filtered[i - 1]?.screenTime) === null ? "M" : "L"}${xs[i].toFixed(1)},${y.toFixed(1)}` : null;
    })
    .filter(Boolean)
    .join(" ");

  const actPath = filtered
    .map((p, i) => {
      const y = toY(p.activity);
      return y !== null ? `${i === 0 || toY(filtered[i - 1]?.activity) === null ? "M" : "L"}${xs[i].toFixed(1)},${y.toFixed(1)}` : null;
    })
    .filter(Boolean)
    .join(" ");

  const gridLevels = [0, 1, 2].filter((v) => v <= maxVal);
  const firstDate = fmtDate(filtered[0].ts);
  const lastDate = fmtDate(filtered[n - 1].ts);

  return (
    <div className="bg-white rounded-xl border border-[rgba(0,0,0,0.05)] p-2">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full"
        style={{ height: "80px" }}
        aria-label="Activity and screen time"
      >
        {/* Grid */}
        {gridLevels.map((v) => {
          const y = pad.top + (1 - v / maxVal) * cH;
          return (
            <g key={v}>
              <line
                x1={pad.left}
                x2={pad.left + cW}
                y1={y}
                y2={y}
                stroke="#E8E3D8"
                strokeWidth="1"
              />
              <text x={pad.left - 4} y={y + 3} textAnchor="end" fontSize="7" fill="#9CAF88">
                {STATE_SHORT[v] ?? v}
              </text>
            </g>
          );
        })}

        {/* Screen time line */}
        {screenPath && (
          <path
            d={screenPath}
            fill="none"
            stroke="#A2ABA1"
            strokeWidth="1.5"
            strokeLinejoin="round"
            strokeDasharray="4 2"
            strokeLinecap="round"
          />
        )}

        {/* Activity line */}
        {actPath && (
          <path
            d={actPath}
            fill="none"
            stroke="#758976"
            strokeWidth="1.5"
            strokeLinejoin="round"
            strokeLinecap="round"
          />
        )}

        {/* Dots */}
        {filtered.map((p, i) => (
          <g key={i}>
            {p.screenTime !== null && (
              <circle
                cx={xs[i]}
                cy={toY(p.screenTime)}
                r="2.5"
                fill="#A2ABA1"
                stroke="#758976"
                strokeWidth="1"
              >
                <title>{`${fmtDate(p.ts)}\nScreen Time: ${stateLabel(p.screenTime)}`}</title>
              </circle>
            )}
            {p.activity !== null && (
              <circle
                cx={xs[i]}
                cy={toY(p.activity)}
                r="2.5"
                fill="#758976"
                stroke="#758976"
                strokeWidth="1"
              >
                <title>{`${fmtDate(p.ts)}\nActivity: ${stateLabel(p.activity)}`}</title>
              </circle>
            )}
          </g>
        ))}

        {/* X axis */}
        <text x={xs[0]} y={H - 2} textAnchor="middle" fontSize="7" fill="#9CAF88">
          {firstDate}
        </text>
        {n > 1 && (
          <text x={xs[n - 1]} y={H - 2} textAnchor="middle" fontSize="7" fill="#9CAF88">
            {lastDate}
          </text>
        )}
      </svg>

      {/* Legend */}
      <div className="flex items-center gap-4 mt-1 px-1">
        <div className="flex items-center gap-1">
          <svg width="16" height="8">
            <line x1="0" y1="4" x2="16" y2="4" stroke="#B8C4B0" strokeWidth="1.5" />
            <circle cx="8" cy="4" r="2" fill="#B8C4B0" />
          </svg>
          <span className="text-[9px]" style={{ color: 'var(--color-ash)' }}>Activity</span>
        </div>
        <div className="flex items-center gap-1">
          <svg width="16" height="8">
            <line x1="0" y1="4" x2="16" y2="4" stroke="#A8B5A0" strokeWidth="1.5" strokeDasharray="4 2" />
            <circle cx="8" cy="4" r="2" fill="#A8B5A0" />
          </svg>
          <span className="text-[9px]" style={{ color: 'var(--color-ash)' }}>Screen Time</span>
        </div>
      </div>
    </div>
  );
}

