# U-THRYV — Sovereign Wellbeing Companion

A fully on-device wellbeing tracking app that uses a **Dynamic Bayesian Network (DBN)** for probabilistic inference and a **local SLM via Ollama** for natural language understanding. No data leaves your machine.

---

## What it does

You describe your day in plain language. U-THRYV parses it locally, updates a Bayesian belief graph, and gives you an empathetic explanation of how your current state is likely to affect the next few hours — all without any cloud calls.

**Tracked nodes:** `sleep` · `activity` · `screen_time` · `social` · `mood` · `stress`

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                     Browser                         │
│  Chat Panel │ Bayesian State Graph │ History Panel  │
└──────────────────────┬──────────────────────────────┘
                       │ REST (localhost:8000)
┌──────────────────────▼──────────────────────────────┐
│               FastAPI Backend                       │
│                                                     │
│  /chat  →  SLM parse  →  DBN inference  →  SQLite  │
│  /history · /labels · /slm/health · /explain        │
└──────┬───────────────────────────┬──────────────────┘
       │                           │
┌──────▼──────┐           ┌────────▼────────┐
│  Ollama     │           │   pgmpy DBN     │
│  phi3:mini  │           │  (2-slice HMM)  │
└─────────────┘           └─────────────────┘
```

---

## Tech Stack

| Layer | Tech |
|---|---|
| Frontend | React 18, Vite, Tailwind CSS, ReactFlow |
| Backend | Python, FastAPI, uvicorn |
| Inference | pgmpy — Dynamic Bayesian Network |
| NLP | Ollama (`phi3:mini`) — runs fully locally |
| Storage | SQLite (event log) |

---

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+
- [Ollama](https://ollama.com) installed and running

### 1. Pull the SLM model

```bash
ollama pull phi3:mini
```

### 2. Backend

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install fastapi uvicorn pgmpy pandas requests
uvicorn main:app --reload --port 8000
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173).

---

## Usage

1. Type how you're feeling or what you've been doing in the **Daily Log** chat panel.
2. The SLM maps your message to DBN nodes (`sleep`, `stress`, etc.).
3. The **Bayesian State Graph** updates in real time, showing inferred probabilities for the next 4-hour block.
4. Switch to the **History** tab to review past events, or **Insights** for trend charts.

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/chat` | Full pipeline: parse → infer → log → explain |
| `POST` | `/predict` | Stateless DBN query |
| `POST` | `/explain` | Cause/effect narrative for a changed node |
| `GET` | `/history` | Last N days of logged events |
| `GET` | `/slm/health` | Check if Ollama is reachable |

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `phi3:mini` | Model to use for parsing |

---

## Privacy

Everything runs locally. No API keys, no telemetry, no cloud. The SQLite database is stored at `backend/hopnote.db`.
