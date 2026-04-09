"""
slm.py
Local SLM wrapper around Ollama. Maps free-form user text to DBN evidence.

The SLM is prompted to return strict JSON:
    {
      "evidence": [
        {"node": "sleep", "state": 2, "confidence": 0.9},
        ...
      ],
      
    }

Node vocabulary and state meanings are injected into the prompt from
dbn_model.ks (cluster count per node) and cluster_info.json (centers).

Usage:
    from slm import SLMClient
    slm = SLMClient(model="phi3:mini")
    result = slm.parse("slept 9 hours and went hiking")
    # -> {"evidence": {"sleep": 2, "activity": 2},  "mappings": [...]}
"""

import json
import os
import re
from pathlib import Path

import requests

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "phi3:mini")
CLUSTER_INFO_PATH = Path(__file__).parent / "cluster_info.json"
REQUEST_TIMEOUT = 300


# Human-readable state descriptions for each node, indexed by k.
# Used to build the prompt so the SLM knows what "state 2" means for "sleep".
STATE_HINTS_3 = {
    0: "low",
    1: "medium",
    2: "high",
}
STATE_HINTS_4 = {
    0: "very low",
    1: "low",
    2: "high",
    3: "very high",
}

# Per-node natural descriptions. Feeds into the prompt.
NODE_DESCRIPTIONS = {
    "sleep":       "hours of sleep last night",
    "activity":    "physical activity / movement during the day",
    "screen_time": "time spent looking at phone/screen",
    "social":      "social interaction (calls, texts, meeting people)",
    "mood":        "emotional mood (positive vs negative affect)",
    "stress":      "perceived stress level",
}


def _load_cluster_centers() -> dict:
    """Read cluster_info.json and return {feature: [centers...]}."""
    if not CLUSTER_INFO_PATH.exists():
        return {}
    with open(CLUSTER_INFO_PATH) as f:
        info = json.load(f)
    return {c["feature"]: c["centers_original_units"] for c in info.get("cluster_info", [])}


def _build_schema_block(ks: dict[str, int]) -> str:
    """
    Render the node/state vocabulary as a plain-text block for the prompt.
    Example line:
      sleep (hours of sleep last night): 0=low (~2.4h), 1=medium (~7h), 2=high (~10.3h)
    """
    centers = _load_cluster_centers()
    lines = []
    for node, k in ks.items():
        hints = STATE_HINTS_3 if k == 3 else STATE_HINTS_4
        desc = NODE_DESCRIPTIONS.get(node, node)
        parts = []
        for state_idx in range(k):
            label = hints.get(state_idx, str(state_idx))
            if node in centers and state_idx < len(centers[node]):
                parts.append(f"{state_idx}={label} (~{centers[node][state_idx]})")
            else:
                parts.append(f"{state_idx}={label}")
        lines.append(f"- {node} ({desc}): {', '.join(parts)}")
    return "\n".join(lines)


def _build_prompt(user_text: str, ks: dict[str, int]) -> str:
    schema = _build_schema_block(ks)
    return f"""You are a strict JSON parser for a wellbeing tracking app.

Map the user's message to one or more of these nodes. Each node has discrete states.

NODES AND STATES:
{schema}

RULES:
1. Only map to a node if the user message gives clear evidence for it.
2. If unsure, DO NOT include the node. Never guess.
3. Confidence must be between 0.0 and 1.0.
4. Produce a "summary": a terse note capturing medically or habitually
   relevant facts. Strip filler, opinions, greetings. Use clinical phrasing
   (sentence fragments OK). Be aggressively brief — write the shortest
   possible string that preserves meaning. ALWAYS produce a summary if the
   message contains anything observable about the user's day, habits, body,
   or behavior — even if no node was confidently mapped. Empty string only
   if the message is pure greeting/noise.
5. Output ONLY valid JSON. No preamble, no markdown, no code fences.

OUTPUT SCHEMA:
{{
  "evidence": [
    {{"node": "<node_name>", "state": <integer>, "confidence": <float 0..1>}}
  ],
  "summary": "<terse note, as short as possible>"
}}

EXAMPLES:

User: "I slept 9 hours and went on a long hike"
Output: {{"evidence":[{{"node":"sleep","state":2,"confidence":0.95}},{{"node":"activity","state":2,"confidence":0.9}}],"summary":"Sleep 9h. Vigorous exercise: long hike."}}

User: "Barely slept, doomscrolled all morning, feel awful"
Output: {{"evidence":[{{"node":"sleep","state":0,"confidence":0.95}},{{"node":"screen_time","state":2,"confidence":0.9}},{{"node":"mood","state":0,"confidence":0.85}}],"summary":"Insufficient sleep. Excessive AM screen exposure. Low mood."}}

User: "I drank a lot of water today"
Output: {{"evidence":[],"summary":"High fluid intake."}}

User: "had coffee with a friend, feeling good"
Output: {{"evidence":[{{"node":"social","state":2,"confidence":0.8}},{{"node":"mood","state":2,"confidence":0.75}}],"summary":"Caffeine intake. Positive social interaction."}}

User: "I think I rested okay maybe"
Output: {{"evidence":[{{"node":"sleep","state":1,"confidence":0.4}}],"summary":"Self-reported moderate rest, uncertain."}}

User: "ugh whatever, hi"
Output: {{"evidence":[],"summary":""}}

Now parse this message:
User: "{user_text}"
Output:"""


def _extract_json(text: str) -> dict | None:
    """Pull a JSON object out of the SLM's response, tolerating stray text."""
    text = text.strip()
    # Strip code fences if the model ignored instructions
    text = re.sub(r"^```(?:json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    # Greedy match the first {...} block
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


class SLMClient:
    def __init__(self, model: str = DEFAULT_MODEL, url: str = OLLAMA_URL):
        self.model = model
        self.url = url.rstrip("/")

    def health(self) -> bool:
        try:
            r = requests.get(f"{self.url}/api/tags", timeout=5)
            return r.status_code == 200
        except Exception:
            return False

    def parse(self, user_text: str, ks: dict[str, int]) -> dict:
        """
        Call Ollama, parse JSON, validate against ks, return normalized result.

        Returns:
            {
                "evidence": {node: state, ...},          # for DBN consumption
                "mappings": [{node, state, confidence}], # detailed per-mapping info
                
                "raw": "...",                            # raw SLM output for debugging
                "error": "..." (only if parsing failed)
            }
        """
        if not user_text or not user_text.strip():
            return {"evidence": {}, "mappings": [], "summary": "", "raw": "", "error": "empty input"}

        prompt = _build_prompt(user_text, ks)

        try:
            response = requests.post(
                f"{self.url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,  # deterministic
                        "num_predict": 300,
                    },
                },
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
        except requests.exceptions.ConnectionError:
            return {
                "evidence": {}, "mappings": [], "summary": "", "raw": "",
                "error": f"Cannot reach Ollama at {self.url}. Is it running?",
            }
        except requests.exceptions.Timeout:
            return {
                "evidence": {}, "mappings": [], "summary": "", "raw": "",
                "error": f"Ollama timed out after {REQUEST_TIMEOUT}s",
            }
        except Exception as e:
            return {
                "evidence": {}, "mappings": [], "summary": "", "raw": "",
                "error": f"{type(e).__name__}: {e}",
            }

        raw_output = response.json().get("response", "")
        parsed = _extract_json(raw_output)

        if parsed is None:
            return {
                "evidence": {}, "mappings": [], "summary": "", "raw": raw_output,
                "error": "SLM returned unparseable output",
            }

        # Validate each mapping against ks
        # Mappings with confidence < CONFIDENCE_THRESHOLD are kept in `mappings`
        # for transparency but excluded from `evidence` so the DBN ignores them.
        CONFIDENCE_THRESHOLD = 0.7
        mappings = []
        evidence = {}
        for item in parsed.get("evidence", []):
            if not isinstance(item, dict):
                continue
            node = item.get("node")
            state = item.get("state")
            conf = item.get("confidence", 0.5)

            if node not in ks:
                continue
            if not isinstance(state, int) or not (0 <= state < ks[node]):
                continue
            try:
                conf = float(conf)
            except (TypeError, ValueError):
                conf = 0.5
            conf = max(0.0, min(1.0, conf))

            mappings.append({"node": node, "state": state, "confidence": conf})
            if conf >= CONFIDENCE_THRESHOLD:
                evidence[node] = state  # last one wins if duplicate

        summary = parsed.get("summary", "")
        if not isinstance(summary, str):
            summary = str(summary)
        summary = summary.strip()

        return {
            "evidence": evidence,
            "mappings": mappings,
            "summary": summary,
            "raw": raw_output,
        }

    def explain(
        self,
        changed_node: str,
        top_parents: list[dict],
        top_children: list[dict],
        recent_summaries: list[dict],
    ) -> dict:
        """
        Generate cause/effect narrative for a changed node as a single paragraph.

        Args:
            changed_node: name of the node whose state was just observed
            top_parents:  [{node, state_label, p, delta}, ...] up to 2 entries
            top_children: same shape, up to 2
            recent_summaries: [{ts, summary}, ...] from last 7 days

        Returns:
            {
              "explanation": "...",  # single paragraph combining cause, effect, and references
              "raw": "...",
              "error": "..." (only on failure)
            }
        """
        prompt = _build_explain_prompt(
            changed_node, top_parents, top_children, recent_summaries
        )

        try:
            response = requests.post(
                f"{self.url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.1, "num_predict": 150},
                    "keep_alive": "10m",
                },
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
        except requests.exceptions.ConnectionError:
            return {
                "explanation": "", "raw": "",
                "error": f"Cannot reach Ollama at {self.url}",
            }
        except requests.exceptions.Timeout:
            return {
                "explanation": "", "raw": "",
                "error": f"Ollama timed out after {REQUEST_TIMEOUT}s",
            }
        except Exception as e:
            return {
                "explanation": "", "raw": "",
                "error": f"{type(e).__name__}: {e}",
            }

        raw_output = response.json().get("response", "")
        explanation = raw_output.strip()
        if not explanation:
            return {
                "explanation": "", "raw": raw_output,
                "error": "SLM returned empty output",
            }

        return {
            "explanation": explanation,
            "raw": raw_output,
        }


def _build_explain_prompt(
    changed_node: str,
    top_parents: list[dict],
    top_children: list[dict],
    recent_summaries: list[dict],
) -> str:
    def fmt_contributors(items, label):
        if not items:
            return f"{label}: none"
        lines = []
        for it in items:
            arrow = "↑" if it.get("delta", 0) > 0 else "↓"
            lines.append(
                f"  - {it['node']} → most likely '{it['state_label']}' "
                f"(prob {it['p']:.2f}, shifted {arrow}{abs(it['delta']):.2f})"
            )
        return f"{label}:\n" + "\n".join(lines)

    parents_block = fmt_contributors(top_parents, "PARENT NODES (possible causes)")
    children_block = fmt_contributors(top_children, "CHILD NODES (possible effects)")

    if recent_summaries:
        history_lines = []
        for s in recent_summaries[:15]:
            ts = s.get("ts", "")[:10]
            history_lines.append(f"  - [{ts}] {s.get('summary', '')}")
        history_block = "RECENT MEDICAL HISTORY (last 7 days):\n" + "\n".join(history_lines)
    else:
        history_block = "RECENT MEDICAL HISTORY: none"

    # Build Bayesian network graph visualization
    parent_names = ", ".join([p["node"] for p in top_parents]) if top_parents else "none"
    child_names = ", ".join([c["node"] for c in top_children]) if top_children else "none"
    
    graph = f"""BAYESIAN NETWORK STRUCTURE:
        
    [{parent_names}]
            ↓
        [{changed_node}] ← (OBSERVED)
            ↓
    [{child_names}]
"""

    return f"""You are a wellbeing assistant generating a gentle, empathetic explanation
for a user. The user's '{changed_node}' state just changed. Use the Bayesian
network's contributors and the user's recent medical history to explain what
likely caused this and what effects to expect.

{graph}

{parents_block}

{children_block}

{history_block}

RULES:
1. Output a single paragraph (max 100 words) explaining the likely cause based on parent nodes, the likely effect based on child nodes, and referencing relevant past summaries if they support the reasoning.
2. Tone: gentle, conversational, second person ("you"). Not clinical.
3. Weave in the referenced summaries naturally if they support the reasoning.
4. Output ONLY the paragraph. No preamble, no markdown, no JSON.

OUTPUT EXAMPLE:
Your stress likely rose because of poor sleep and heavy screen time, as seen in your late night coding session where you slept only 4 hours. This may carry into the next few hours unless you take a break.

Now generate the explanation:
Output:"""