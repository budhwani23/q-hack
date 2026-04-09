// src/ChatPanel.jsx
import { useState, useRef, useEffect } from "react";
import { MessageCircle, Send } from "lucide-react";
import { argmax, stateLabel } from "./dbn";

export default function ChatPanel({ messages, onSend, loading, slmOk }) {
  const [text, setText] = useState("");
  const scrollRef = useRef(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages]);

  const submit = (e) => {
    e?.preventDefault();
    if (!text.trim() || loading) return;
    onSend(text.trim());
    setText("");
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-5 py-3 border-b-2 border-ink-950 bg-cream-100">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-coral-500 border-2 border-ink-950 flex items-center justify-center shadow-pop-sm">
            <MessageCircle className="w-4 h-4 text-cream-50" strokeWidth={2.5} />
          </div>
          <div>
            <div className="font-display text-xl text-ink-950 font-semibold">Daily Log</div>
            <div className="text-[11px] text-ink-700 font-mono uppercase tracking-wider">
              Talk, sense, or type what's on your mind
            </div>
          </div>
        </div>
        <div
          className={`
            flex items-center gap-1.5 px-2 py-1 rounded-full border-2 border-ink-950
            text-[9px] font-mono uppercase tracking-wider font-bold shadow-pop-sm
            ${slmOk ? "bg-sage-400 text-cream-50" : "bg-rose-400 text-cream-50"}
          `}
          title={slmOk ? "Local SLM reachable" : "SLM unreachable"}
        >
          <div className="w-1.5 h-1.5 rounded-full bg-cream-50 animate-pulse" />
          {slmOk ? "online" : "offline"}
        </div>
      </div>

      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto px-5 py-4 space-y-3"
      >
        {messages.length === 0 && (
          <div className="text-ink-700 text-sm leading-relaxed">
            <div className="italic mb-2">Tell me about your day. Try:</div>
            <ul className="space-y-2 not-italic">
              <li className="px-3 py-2 bg-cream-100 border-2 border-ink-950 rounded-lg shadow-pop-sm font-medium">
                "I slept 9 hours and went on a long hike"
              </li>
              <li className="px-3 py-2 bg-cream-100 border-2 border-ink-950 rounded-lg shadow-pop-sm font-medium">
                "Barely slept, doomscrolled all morning"
              </li>
              <li className="px-3 py-2 bg-cream-100 border-2 border-ink-950 rounded-lg shadow-pop-sm font-medium">
                "Met friends for dinner, feeling good"
              </li>
            </ul>
          </div>
        )}
        {messages.map((m, i) => (
          <MessageBubble key={i} msg={m} />
        ))}
        {loading && (
          <div className="flex items-center gap-2 text-ink-700 text-sm animate-fadeUp">
            <div className="flex gap-1">
              <div className="w-2 h-2 rounded-full bg-coral-500 animate-pulse" />
              <div className="w-2 h-2 rounded-full bg-coral-500 animate-pulse [animation-delay:150ms]" />
              <div className="w-2 h-2 rounded-full bg-coral-500 animate-pulse [animation-delay:300ms]" />
            </div>
            <span className="font-mono text-[11px] uppercase tracking-wider font-semibold">reasoning locally</span>
          </div>
        )}
      </div>

      <form
        onSubmit={submit}
        className="border-t-2 border-ink-950 px-4 py-3 flex gap-2 bg-cream-100"
      >
        <input
          type="text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="How are you today?"
          disabled={loading}
          className="
            flex-1 bg-cream-50 border-2 border-ink-950 rounded-lg px-4 py-2.5
            text-ink-950 text-sm placeholder:text-ink-600 font-medium
            focus:outline-none focus:shadow-pop-sm
            disabled:opacity-50 transition-all
          "
        />
        <button
          type="submit"
          disabled={loading || !text.trim()}
          className="
            px-4 py-2.5 rounded-lg bg-coral-500 text-cream-50 font-bold text-sm
            border-2 border-ink-950 shadow-pop-sm
            hover:bg-coral-400 hover:-translate-y-0.5 hover:shadow-[3px_3px_0_0_#1a1a1a]
            disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:translate-y-0
            transition-all flex items-center gap-2
          "
        >
          <Send className="w-4 h-4" strokeWidth={2.5} />
          Send
        </button>
      </form>
    </div>
  );
}

// Extract a readable one-line prediction from the slice_1 posterior.
// Picks the "most certain" outcome node (stress or mood) to report.
function buildPrediction(posteriors) {
  if (!posteriors?.slice_1) return null;

  const stressDist = posteriors.slice_1.stress;
  const moodDist = posteriors.slice_1.mood;

  const pick = (dist, nodeName, k) => {
    if (!dist) return null;
    const { state, prob, delta } = argmax(dist);
    if (prob < 0.4) return null; // skip weak predictions
    return {
      node: nodeName,
      label: stateLabel(k, state),
      prob,
      delta,
    };
  };

  const stress = pick(stressDist, "stress", 3);
  const mood = pick(moodDist, "mood", 4);

  // Prefer whichever is more certain
  if (!stress && !mood) return null;
  if (!stress) return mood;
  if (!mood) return stress;
  return stress.prob >= mood.prob ? stress : mood;
}

function MessageBubble({ msg }) {
  if (msg.role === "user") {
    return (
      <div className="flex justify-end animate-fadeUp">
        <div className="max-w-[85%] bg-coral-500 text-cream-50 rounded-2xl rounded-br-md px-4 py-2.5 text-sm font-semibold border-2 border-ink-950 shadow-pop-sm">
          {msg.text}
        </div>
      </div>
    );
  }

  // Assistant bubble
  const prediction = buildPrediction(msg.posteriors);
  const hasContent =
    msg.summary ||
    msg.explanation ||
    msg.acknowledgement ||
    msg.error ||
    prediction;

  return (
    <div className="flex justify-start animate-fadeUp">
      <div className="max-w-[92%] bg-cream-100 border-2 border-ink-950 rounded-2xl rounded-bl-md px-4 py-3 text-sm space-y-2.5 shadow-pop-sm">
        {msg.error && (
          <div className="text-rose-600 text-xs font-mono bg-rose-400/20 px-2 py-1 rounded border border-rose-400">
            {msg.error}
          </div>
        )}

        {/* Primary conversational response from the explain model */}
        {msg.explanation && (
          <div className="text-ink-950 text-[14px] leading-relaxed">
            {msg.explanation}
          </div>
        )}

        {/* Low-confidence acknowledgement path (no DBN evidence) */}
        {msg.acknowledgement && !msg.explanation && (
          <div className="text-ink-900 text-[13px] italic">
            {msg.acknowledgement}
          </div>
        )}

        {/* Medical / habitual summary — terse clinical note */}
        {msg.summary && (
          <div className="text-ink-600 text-[11px] leading-relaxed font-mono border-t border-ink-200 pt-2">
            {msg.summary}
          </div>
        )}

        {/* Posterior one-liner: "Predicted stress is low ↓34%" */}
        {prediction && (
          <div className="pt-1.5 border-t-2 border-dashed border-ink-300 flex items-center gap-2 font-mono text-[11px]">
            <span className="text-ink-700 uppercase tracking-wider font-semibold">
              next · {prediction.node}
            </span>
            <span className="text-ink-950 font-bold uppercase">{prediction.label}</span>
            <span className="text-ink-600">({(prediction.prob * 100).toFixed(0)}%)</span>
            {Math.abs(prediction.delta) >= 0.01 && (
              <span
                className="font-bold"
                style={{ color: prediction.delta > 0 ? "#2F8559" : "#C92E3E" }}
              >
                {prediction.delta > 0 ? "↑" : "↓"}
                {(Math.abs(prediction.delta) * 100).toFixed(0)}%
              </span>
            )}
          </div>
        )}

        {/* Fallback for completely empty responses */}
        {!hasContent && (
          <div className="text-ink-700 text-[13px] italic">
            Noted — nothing new to infer.
          </div>
        )}
      </div>
    </div>
  );
}
