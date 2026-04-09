// src/App.jsx
import { useEffect, useState } from "react";
import { api } from "./api";
import NodeGraph from "./NodeGraph";
import ChatPanel from "./ChatPanel";
import HistoryPanel from "./HistoryPanel";
import { Brain, Sparkles, Network } from "lucide-react";

export default function App() {
  const [messages, setMessages] = useState([]);
  const [posteriors, setPosteriors] = useState(null);
  const [evidence, setEvidence] = useState({});
  const [kPerNode, setKPerNode] = useState(null);
  const [loading, setLoading] = useState(false);
  const [slmOk, setSlmOk] = useState(false);
  const [historyRefresh, setHistoryRefresh] = useState(0);

  useEffect(() => {
    api.slmHealth().then((r) => setSlmOk(r.ok)).catch(() => setSlmOk(false));
  }, []);

  useEffect(() => {
    api.predict({}, null)
      .then((r) => {
        if (r.error) return;
        setPosteriors(r.posteriors);
        setKPerNode(r.k_per_node);
      })
      .catch(() => {});
  }, []);

  const handleSend = async (text) => {
    setMessages((m) => [...m, { role: "user", text }]);
    setLoading(true);
    try {
      const r = await api.chat(text);
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          mappings: r.mappings || [],
          summary: r.summary || "",
          explanation: r.explanation || "",
          acknowledgement: r.acknowledgement,
          posteriors: r.posteriors || null,
          error: r.error,
        },
      ]);
      if (r.posteriors) {
        setPosteriors(r.posteriors);
        setEvidence(r.evidence || {});
        setKPerNode(r.k_per_node);
      }
      setHistoryRefresh((x) => x + 1);
    } catch (e) {
      setMessages((m) => [...m, { role: "assistant", error: `request failed: ${e.message}` }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="h-screen w-full flex flex-col">
      <Header slmOk={slmOk} />

      <main className="flex-1 min-h-0 grid grid-cols-12 gap-4 p-4">
        {/* Chat — left */}
        <section className="col-span-4 bg-cream-50 border-[2.5px] border-ink-950 rounded-2xl overflow-hidden shadow-pop">
          <ChatPanel
            messages={messages}
            onSend={handleSend}
            loading={loading}
            slmOk={slmOk}
          />
        </section>

        {/* Graph — center, the hero */}
        <section className="col-span-5 bg-cream-50 border-[2.5px] border-ink-950 rounded-2xl overflow-hidden shadow-pop-coral flex flex-col">
          <div className="flex items-center justify-between px-5 py-3 border-b-2 border-ink-950 bg-cream-100">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-lg bg-coral-500 border-2 border-ink-950 flex items-center justify-center shadow-pop-sm">
                <Network className="w-4 h-4 text-cream-50" strokeWidth={2.5} />
              </div>
              <div>
                <div className="font-display text-xl text-ink-950 font-semibold">
                  Bayesian State Graph
                </div>
                <div className="text-[11px] text-ink-700 font-mono uppercase tracking-wider">
                  Next 4-hour block · inferred locally
                </div>
              </div>
            </div>
            <Legend />
          </div>
          <div className="flex-1 min-h-0 relative">
            {posteriors ? (
              <NodeGraph
                posteriors={posteriors}
                evidence={evidence}
                kPerNode={kPerNode}
              />
            ) : (
              <div className="absolute inset-0 flex items-center justify-center text-ink-600 text-sm font-mono">
                loading model…
              </div>
            )}
          </div>
        </section>

        {/* History — right */}
        <section className="col-span-3 bg-cream-50 border-[2.5px] border-ink-950 rounded-2xl overflow-hidden shadow-pop">
          <HistoryPanel refreshKey={historyRefresh} />
        </section>
      </main>
    </div>
  );
}

function Header({ slmOk }) {
  return (
    <header className="px-6 py-4 flex items-center justify-between border-b-2 border-ink-950 bg-cream-100">
      <div className="flex items-center gap-3">
        <div className="w-11 h-11 rounded-xl bg-coral-500 border-[2.5px] border-ink-950 flex items-center justify-center shadow-pop-sm">
          <Brain className="w-6 h-6 text-cream-50" strokeWidth={2.5} />
        </div>
        <div>
          <div className="font-display text-3xl font-bold text-ink-950 tracking-tight leading-none">
            U-THRYV
          </div>
          <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-ink-700 mt-1">
            Sovereign Wellbeing Companion
          </div>
        </div>
      </div>
      <div className="flex items-center gap-4">
        <div
          className={`
            flex items-center gap-2 px-3 py-1.5 rounded-full border-2 border-ink-950
            ${slmOk ? "bg-sage-400" : "bg-rose-400"}
            shadow-pop-sm text-cream-50 text-[10px] font-mono uppercase tracking-wider font-bold
          `}
        >
          <Sparkles className="w-3 h-3" strokeWidth={2.5} />
          {slmOk ? "SLM Online" : "SLM Offline"}
        </div>
        <div className="hidden md:flex items-center gap-2 text-[10px] font-mono uppercase tracking-wider text-ink-800 font-semibold">
          <div className="w-2 h-2 rounded-full bg-sage-500 animate-pulse" />
          on device · no cloud
        </div>
      </div>
    </header>
  );
}

function Legend() {
  return (
    <div className="flex items-center gap-2 text-[10px] font-mono uppercase tracking-wider text-ink-800 font-semibold">
      <LegendDot color="#2F8559" label="low" />
      <LegendDot color="#E89C20" label="med" />
      <LegendDot color="#FF5A3C" label="high" />
    </div>
  );
}

function LegendDot({ color, label }) {
  return (
    <div className="flex items-center gap-1.5">
      <div
        className="w-2.5 h-2.5 rounded-full border border-ink-950"
        style={{ backgroundColor: color }}
      />
      <span>{label}</span>
    </div>
  );
}
