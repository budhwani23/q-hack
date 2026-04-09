"""
main.py
FastAPI backend — DBN inference + SLM parsing + SQLite event log.

Endpoints:
    POST /predict      — stateless DBN: send evidence + optional user_text, get posteriors
    POST /parse        — SLM only: send text, get parsed evidence + summary
    POST /chat         — SLM + DBN combined: text -> parse -> predict -> log
    GET  /history      — last N days of logged events (default 7, max 90)
    GET  /labels       — full column_name -> human label mapping
    GET  /labels/{col} — single label lookup
    GET  /slm/health   — check if Ollama is reachable

Run:
    uvicorn main:app --reload --port 8000
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from dbn_model import DBNModel
from db import init_db, log_event, get_events, get_label, get_all_labels, get_summaries
from slm import SLMClient

DBN: DBNModel | None = None
SLM: SLMClient | None = None

# In-memory prior tracking. Reset via POST /predict/reset.
# Stores last call's posteriors for slice-0 and slice-1 so each new call can
# report deltas. Single-process only — fine for the demo, not for prod.
LAST_POSTERIORS: dict | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global DBN, SLM
    init_db()
    DBN = DBNModel().load()
    SLM = SLMClient()
    if SLM.health():
        print(f"SLM ready (Ollama at {SLM.url}, model={SLM.model}).")
    else:
        print(f"WARNING: Ollama not reachable at {SLM.url}. /parse and /chat will fail until it's running.")
    print("DBN loaded, server ready.")
    yield


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class PredictIn(BaseModel):
    # Evidence from SLM or passive sensors.
    # Keys are node names ("sleep", "activity", "screen_time", "social", "mood", "stress").
    # Values are integer states (0..k-1 per node, see dbn_model.cluster_info.json).
    evidence: dict[str, int] = {}
    # Optional raw text that produced this evidence (logged for audit, not used by DBN)
    user_text: str | None = None


def _format_dist(dist) -> dict[int, float]:
    return {int(s): float(p) for s, p in dist.items()}


def _diff_posteriors(curr: dict, prev: dict | None) -> dict:
    """
    Compute change vs prev. Returns same shape as curr but each state holds
    {p, delta}. If prev is None, delta = 0.
    """
    out = {}
    for slice_key, nodes in curr.items():
        out[slice_key] = {}
        for node, dist in nodes.items():
            prev_dist = (prev or {}).get(slice_key, {}).get(node, {})
            out[slice_key][node] = {
                int(s): {
                    "p": float(p),
                    "delta": float(p - prev_dist.get(int(s), p)),
                }
                for s, p in dist.items()
            }
    return out


def _run_dbn(evidence: dict[str, int]) -> dict:
    """
    Validate evidence, run DBN query for BOTH slices.
    Slice 0 captures reverse inference on parents; slice 1 captures forward predictions.
    Observed slice-0 nodes are returned as degenerate distributions (p=1 on observed state).
    """
    assert DBN is not None
    dbn_features = set(DBN.ks.keys())

    evidence_dbn = {}
    for node, state in evidence.items():
        if node not in dbn_features:
            return {"error": f"unknown node '{node}'. Valid: {sorted(dbn_features)}"}
        k = DBN.ks[node]
        if not (0 <= state < k):
            return {"error": f"state {state} out of range for '{node}' (k={k})"}
        evidence_dbn[(node, 0)] = int(state)

    # Slice 0: query unobserved nodes (reverse inference on parents/siblings)
    slice0_targets = [(feat, 0) for feat in dbn_features if (feat, 0) not in evidence_dbn]
    # Slice 1: query all nodes (forward predictions)
    slice1_targets = [(feat, 1) for feat in dbn_features]

    try:
        raw0 = DBN.query(evidence_dbn, slice0_targets) if slice0_targets else {}
        raw1 = DBN.query(evidence_dbn, slice1_targets)
    except Exception as e:
        return {"error": f"DBN query failed: {type(e).__name__}: {e}"}

    slice0 = {}
    for (feat, _), dist in raw0.items():
        slice0[feat] = _format_dist(dist)
    # Inject observed slice-0 nodes as degenerate distributions
    for (feat, _), state in evidence_dbn.items():
        slice0[feat] = {i: (1.0 if i == state else 0.0) for i in range(DBN.ks[feat])}

    slice1 = {feat: _format_dist(dist) for (feat, _), dist in raw1.items()}

    return {"posteriors": {"slice_0": slice0, "slice_1": slice1}}


@app.post("/predict")
def predict(body: PredictIn):
    """
    Stateless DBN query.
    Evidence is applied to the current time block (slice 0).
    Returns posterior distributions for all nodes at the NEXT time block (slice 1).
    Every call is logged to the SQLite event_log table.
    Returns posteriors for both slice 0 (reverse inference on parents)
    and slice 1 (forward predictions), with deltas vs the previous call.
    """
    global LAST_POSTERIORS
    result = _run_dbn(body.evidence)
    if "error" in result:
        return result

    posteriors = result["posteriors"]
    diffed = _diff_posteriors(posteriors, LAST_POSTERIORS)
    LAST_POSTERIORS = posteriors

    try:
        log_event(body.user_text, body.evidence, posteriors)
    except Exception as e:
        print(f"WARN: failed to log event: {e}")

    return {
        "evidence": body.evidence,
        "user_text": body.user_text,
        "posteriors": diffed,
        "k_per_node": DBN.ks,
    }


@app.post("/predict/reset")
def predict_reset():
    """Clear the in-memory prior so the next /predict call has delta=0."""
    global LAST_POSTERIORS
    LAST_POSTERIORS = None
    return {"ok": True}


class ParseIn(BaseModel):
    text: str


@app.post("/parse")
def parse(body: ParseIn):
    """
    SLM-only endpoint. Takes free-form text, returns parsed evidence + summary.
    Does NOT run the DBN and does NOT log. Use /chat for the full pipeline.
    """
    assert SLM is not None and DBN is not None
    result = SLM.parse(body.text, DBN.ks)
    return {
        "text": body.text,
        "evidence": result["evidence"],
        "mappings": result["mappings"],
        "summary": result.get("summary", ""),
        "error": result.get("error"),
    }


class ChatIn(BaseModel):
    text: str


@app.post("/chat")
def chat(body: ChatIn):
    """
    Full pipeline: SLM parses text -> DBN predicts -> event is logged.
    Use this when you want one round-trip for both.
    """
    assert SLM is not None and DBN is not None

    slm_result = SLM.parse(body.text, DBN.ks)
    if slm_result.get("error"):
        return {
            "text": body.text,
            "evidence": {},
            "mappings": [],
            "summary": slm_result.get("summary", ""),
            "posteriors": None,
            "error": f"SLM: {slm_result['error']}",
        }

    evidence = slm_result["evidence"]
    summary = slm_result.get("summary", "")

    # Low-confidence path: no node passed the threshold, so DBN has nothing to update.
    # Store the summary and return a simple acknowledgement.
    if not evidence:
        try:
            log_event(summary, {}, {})
        except Exception as e:
            print(f"WARN: failed to log event: {e}")
        return {
            "text": body.text,
            "evidence": {},
            "mappings": slm_result["mappings"],
            "summary": summary,
            "posteriors": None,
            "acknowledgement": "Got it — I've noted this in your log.",
            "k_per_node": DBN.ks,
        }

    dbn_result = _run_dbn(evidence)
    if "error" in dbn_result:
        return {
            "text": body.text,
            "evidence": evidence,
            "mappings": slm_result["mappings"],
            "summary": summary,
            "posteriors": None,
            "error": f"DBN: {dbn_result['error']}",
        }

    global LAST_POSTERIORS
    posteriors = dbn_result["posteriors"]
    diffed = _diff_posteriors(posteriors, LAST_POSTERIORS)
    LAST_POSTERIORS = posteriors

    try:
        log_event(summary, evidence, posteriors)
    except Exception as e:
        print(f"WARN: failed to log event: {e}")

    # Pick the node with the highest total shift in slice_1 to explain
    primary_node = None
    best_shift = -1.0
    for node in evidence:
        if node in diffed.get("slice_1", {}):
            shift = _node_total_shift(diffed["slice_1"][node])
            if shift > best_shift:
                best_shift = shift
                primary_node = node

    explanation = ""
    if primary_node:
        top_parents, top_children = _top_contributors(primary_node, diffed["slice_0"], k=2)
        recent = get_summaries(days=7, limit=10)
        slm_out = SLM.explain(primary_node, top_parents, top_children, recent)
        explanation = slm_out.get("explanation", "")

    return {
        "text": body.text,
        "evidence": evidence,
        "mappings": slm_result["mappings"],
        "summary": summary,
        "explanation": explanation,
        "posteriors": diffed,
        "k_per_node": DBN.ks,
    }


@app.get("/slm/health")
def slm_health():
    """Quick check for whether Ollama is reachable."""
    assert SLM is not None
    return {
        "ok": SLM.health(),
        "url": SLM.url,
        "model": SLM.model,
    }


# ---- /explain helpers ----

# Per-node state label tables (mirror slm.py)
_STATE_LABELS_3 = {0: "low", 1: "medium", 2: "high"}
_STATE_LABELS_4 = {0: "very low", 1: "low", 2: "high", 3: "very high"}


def _state_label(k: int, state: int) -> str:
    if k == 3:
        return _STATE_LABELS_3.get(state, str(state))
    if k == 4:
        return _STATE_LABELS_4.get(state, str(state))
    return str(state)


def _node_total_shift(diffed_node: dict) -> float:
    """Sum of |delta| across all states of one node — measures total movement."""
    return sum(abs(s.get("delta", 0.0)) for s in diffed_node.values())


def _argmax_state(diffed_node: dict) -> tuple[int, float]:
    """Return (most_likely_state_int, its_p)."""
    best_state, best_p = 0, -1.0
    for s, payload in diffed_node.items():
        p = payload.get("p", 0.0)
        if p > best_p:
            best_p = p
            best_state = int(s)
    return best_state, best_p


def _top_contributors(
    changed_node: str,
    diffed_slice0: dict,
    k: int = 2,
) -> tuple[list[dict], list[dict]]:
    """
    Find parents and children of changed_node in the DBN, rank by total |delta|
    in the slice-0 diffed posteriors, return top-k of each.
    Each item: {node, state_label, p, delta_sum}.
    """
    assert DBN is not None
    model = DBN.model

    # pgmpy returns DynamicNode objects; cast to (name, slice) tuples
    parent_nodes = [tuple(p) for p in model.get_parents((changed_node, 0))]
    child_nodes = [tuple(c) for c in model.get_children((changed_node, 0))]

    # Filter to slice-0 only (cross-slice children like (mood, 1) excluded — they're predictions, not effects in current block)
    parent_names = [n for (n, s) in parent_nodes if s == 0 and n != changed_node]
    child_names = [n for (n, s) in child_nodes if s == 0 and n != changed_node]

    def rank(names):
        scored = []
        for name in names:
            if name not in diffed_slice0:
                continue
            node_dist = diffed_slice0[name]
            shift = _node_total_shift(node_dist)
            top_state, top_p = _argmax_state(node_dist)
            # Use the dominant state's signed delta as the headline
            top_delta = node_dist[top_state].get("delta", 0.0) if top_state in node_dist else 0.0
            scored.append({
                "node": name,
                "state_label": _state_label(DBN.ks[name], top_state),
                "state": top_state,
                "p": float(top_p),
                "delta": float(top_delta),
                "shift_total": float(shift),
            })
        scored.sort(key=lambda x: x["shift_total"], reverse=True)
        return scored[:k]

    return rank(parent_names), rank(child_names)


class ExplainIn(BaseModel):
    # Node whose state changed (e.g. result of /chat or /predict)
    node: str
    # Current evidence for the DBN (same shape as /predict)
    evidence: dict[str, int] = {}


@app.post("/explain")
def explain(body: ExplainIn):
    """
    Generate cause/effect narrative + relevant past references for a changed node.

    Pipeline:
      1. Run DBN with evidence -> diffed posteriors (slice 0 + slice 1)
      2. Find top-2 parents and top-2 children of `node` by absolute delta
      3. Pull last 7 days of non-empty medical summaries from SQLite
      4. Send all of the above to the SLM, get back {cause, effect, referenced}
    """
    assert DBN is not None and SLM is not None

    if body.node not in DBN.ks:
        raise HTTPException(
            status_code=400,
            detail=f"unknown node '{body.node}'. Valid: {sorted(DBN.ks.keys())}",
        )

    # 1. DBN inference with deltas
    global LAST_POSTERIORS
    dbn_result = _run_dbn(body.evidence)
    if "error" in dbn_result:
        return dbn_result
    posteriors = dbn_result["posteriors"]
    diffed = _diff_posteriors(posteriors, LAST_POSTERIORS)
    LAST_POSTERIORS = posteriors

    # 2. Top contributors from slice-0 diffed view
    top_parents, top_children = _top_contributors(body.node, diffed["slice_0"], k=2)

    # 3. Recent summaries
    recent = get_summaries(days=7, limit=20)

    # 4. SLM call
    slm_out = SLM.explain(body.node, top_parents, top_children, recent)

    return {
        "node": body.node,
        "evidence": body.evidence,
        "bayesian_graph": {
            "parents": top_parents,
            "target": body.node,
            "children": top_children,
        },
        "graph_summary": {
            "parent_nodes": [p["node"] for p in top_parents],
            "child_nodes": [c["node"] for c in top_children],
        },
        "top_parents": top_parents,
        "top_children": top_children,
        "history_used": len(recent),
        "explanation": slm_out.get("explanation", ""),
        "error": slm_out.get("error"),
    }


@app.get("/history")
def history(days: int = 7):
    """Return logged events from the last N days (1..90), newest first."""
    if not (1 <= days <= 90):
        raise HTTPException(status_code=400, detail="days must be between 1 and 90")
    return {"days": days, "events": get_events(days=days)}


@app.get("/labels")
def labels():
    """Return the full column_name -> human label mapping."""
    return get_all_labels()


@app.get("/labels/{column_name}")
def label_one(column_name: str):
    """Look up a single column label. 404 if not found."""
    lbl = get_label(column_name)
    if lbl is None:
        raise HTTPException(status_code=404, detail=f"no label for column '{column_name}'")
    return {"column_name": column_name, "label": lbl}