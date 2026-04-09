// src/components/HistoryPanel.jsx
import { useEffect, useState } from "react";
import { api } from "./api";
import InsightsChart from "./InsightsChart";

export default function HistoryPanel({ refreshKey }) {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState(null);
  const [tab, setTab] = useState("insights");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api
      .history(7)
      .then((r) => {
        if (!cancelled) {
          setEvents(r.events || []);
          setErr(null);
        }
      })
      .catch((e) => !cancelled && setErr(e.message))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [refreshKey]);

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-5 py-3 border-b border-[rgba(0,0,0,0.05)]">
        <div className="flex items-center justify-between mb-2">
          <div className="font-display text-lg text-reseda-600">
            {tab === "insights" ? "Insights" : "History"}
          </div>
          <div className="text-[10px] font-mono" style={{ color: 'var(--color-ash)' }}>
            {events.length} {events.length === 1 ? "event" : "events"}
          </div>
        </div>
        {/* Tabs */}
        <div className="flex gap-1 rounded-lg p-0.5">
          <TabBtn active={tab === "insights"} onClick={() => setTab("insights")}>
            Insights
          </TabBtn>
          <TabBtn active={tab === "history"} onClick={() => setTab("history")}>
            History
          </TabBtn>
        </div>
      </div>

      {/* Content */}
      {tab === "history" ? (
        <HistoryList events={events} loading={loading} err={err} />
      ) : (
        <InsightsChart events={events} loading={loading} />
      )}
    </div>
  );
}

function TabBtn({ active, onClick, children }) {
  return (
    <button
      onClick={onClick}
      className={`flex-1 py-1 rounded-md text-[10px] font-mono uppercase tracking-wider transition-colors ${
        active
          ? "bg-thistle/30 text-nearblack border border-[rgba(0,0,0,0.04)]"
          : "text-ash hover:text-nearblack"
      }`}
    >
      {children}
    </button>
  );
}

function HistoryList({ events, loading, err }) {
  return (
    <div className="flex-1 overflow-y-auto px-4 py-3 space-y-2">
      {loading && (
        <div className="text-ash text-xs font-mono">loading…</div>
      )}
      {err && <div className="text-error text-xs font-mono">{err}</div>}
      {!loading && events.length === 0 && (
        <div className="text-ash text-xs italic">
          No events yet. Log your day in the chat.
        </div>
      )}
      {events.map((ev) => (
        <HistoryRow key={ev.id} ev={ev} />
      ))}
    </div>
  );
}

function HistoryRow({ ev }) {
  const ts = new Date(ev.ts + "Z");
  const timeStr = ts.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
  const evidenceEntries = Object.entries(ev.evidence || {});

  return (
    <div className="bg-white border border-[rgba(0,0,0,0.05)] rounded-lg px-3 py-2.5 animate-fadeUp shadow-card">
      <div className="flex items-center justify-between gap-2 mb-1">
        <div className="font-mono text-[10px] text-ash uppercase tracking-wider">
          {timeStr}
        </div>
        <div className="text-[10px] font-mono" style={{ color: 'var(--color-ash)' }}>#{ev.id}</div>
      </div>
      {ev.user_text && (
        <div className="text-nearblack text-[12px] leading-snug mb-1.5">
          {ev.user_text}
        </div>
      )}
      {evidenceEntries.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {evidenceEntries.map(([node, state]) => (
            <span
              key={node}
              className="px-1.5 py-0.5 rounded bg-thistle/30 text-nearblack font-mono text-[10px]"
            >
              {node}={state}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
