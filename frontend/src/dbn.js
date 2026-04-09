// src/dbn.js
// DBN structure constants, mirrored from backend/dbn_model.py

export const NODES = ["sleep", "activity", "screen_time", "social", "mood", "stress"];

export const EDGES = [
  ["sleep", "mood"],
  ["activity", "mood"],
  ["screen_time", "mood"],
  ["social", "mood"],
  ["sleep", "stress"],
  ["activity", "stress"],
  ["screen_time", "stress"],
  ["mood", "stress"],
];

export const NODE_POSITIONS = {
  sleep:       { x:  40, y:  40 },
  activity:    { x:  40, y: 140 },
  screen_time: { x:  40, y: 240 },
  social:      { x:  40, y: 340 },
  mood:        { x: 280, y: 140 },
  stress:      { x: 520, y: 240 },
};

export const NODE_LABELS = {
  sleep: "Sleep",
  activity: "Activity",
  screen_time: "Screen Time",
  social: "Social",
  mood: "Mood",
  stress: "Stress",
};

export const STATE_LABELS_3 = { 0: "low", 1: "med", 2: "high" };
export const STATE_LABELS_4 = { 0: "very low", 1: "low", 2: "high", 3: "very high" };

export function stateLabel(k, stateIdx) {
  if (k === 3) return STATE_LABELS_3[stateIdx] ?? String(stateIdx);
  if (k === 4) return STATE_LABELS_4[stateIdx] ?? String(stateIdx);
  return String(stateIdx);
}

// Colors tuned for CREAM (#FAF6EF) background. Saturated to pop.
// Outcome nodes (stress/mood): low=sage, mid=honey, high=coral (hero).
// Input nodes: sage→honey gradient (no coral — reserved for outcomes).
export function stateColor(k, stateIdx, isOutcome = false) {
  const ratio = stateIdx / (k - 1);
  if (isOutcome) {
    if (ratio < 0.34) return "#2F8559"; // deep sage
    if (ratio < 0.67) return "#E89C20"; // honey
    return "#FF5A3C";                   // CORAL — the hero
  }
  if (ratio < 0.34) return "#4FA77C";
  if (ratio < 0.67) return "#F5B947";
  return "#E89C20";
}

// Handles both response shapes: {0: 0.5} and {0: {p: 0.5, delta: 0.1}}
export function argmax(dist) {
  if (!dist) return { state: 0, prob: 0, delta: 0 };
  let best = 0;
  let bestP = -1;
  let bestDelta = 0;
  for (const [k, v] of Object.entries(dist)) {
    const p = typeof v === "number" ? v : (v?.p ?? 0);
    const d = typeof v === "number" ? 0 : (v?.delta ?? 0);
    if (p > bestP) {
      bestP = p;
      best = parseInt(k, 10);
      bestDelta = d;
    }
  }
  return { state: best, prob: bestP < 0 ? 0 : bestP, delta: bestDelta };
}

export function toPlainDist(dist) {
  if (!dist) return {};
  const out = {};
  for (const [k, v] of Object.entries(dist)) {
    out[parseInt(k, 10)] = typeof v === "number" ? v : (v?.p ?? 0);
  }
  return out;
}
