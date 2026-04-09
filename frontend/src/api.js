// src/lib/api.js
// All backend calls go through /api/* (Vite proxies to http://localhost:8000)

const base = "/api";

async function post(path, body) {
  const r = await fetch(`${base}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body ?? {}),
  });
  if (!r.ok) throw new Error(`${path} ${r.status}`);
  return r.json();
}

async function get(path) {
  const r = await fetch(`${base}${path}`);
  if (!r.ok) throw new Error(`${path} ${r.status}`);
  return r.json();
}

export const api = {
  chat: (text) => post("/chat", { text }),
  parse: (text) => post("/parse", { text }),
  predict: (evidence, user_text = null) =>
    post("/predict", { evidence, user_text }),
  explain: (node, evidence = {}) => post("/explain", { node, evidence }),
  history: (days = 7) => get(`/history?days=${days}`),
  labels: () => get("/labels"),
  slmHealth: () => get("/slm/health"),
};
