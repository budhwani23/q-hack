import { useState, useEffect } from "react";
import "./App.css";

function App() {
  const [health, setHealth] = useState(null);
  const [message, setMessage] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function fetchData() {
      try {
        const [healthRes, msgRes] = await Promise.all([
          fetch("/api/health"),
          fetch("/api/hello"),
        ]);
        const healthData = await healthRes.json();
        const msgData = await msgRes.json();
        setHealth(healthData);
        setMessage(msgData);
      } catch (err) {
        setError("Failed to reach the API. Is the backend running?");
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, []);

  return (
    <div className="app">
      <header className="app-header">
        <h1>⚡ React + FastAPI</h1>
        <p className="subtitle">A full-stack starter — ready for Koyeb</p>
      </header>

      <main className="app-main">
        <section className="card">
          <h2>API Health</h2>
          {loading && <p className="muted">Checking…</p>}
          {error && <p className="error">{error}</p>}
          {health && (
            <div className="badge badge--green">
              ✅ {health.status} — {health.environment}
            </div>
          )}
        </section>

        <section className="card">
          <h2>Message from Backend</h2>
          {loading && <p className="muted">Loading…</p>}
          {message && <p className="message">{message.message}</p>}
        </section>

        <section className="card stack">
          <h2>Stack</h2>
          <ul>
            <li>
              <span className="tech">Frontend</span> React 18 + Vite
            </li>
            <li>
              <span className="tech">Backend</span> FastAPI + Uvicorn
            </li>
            <li>
              <span className="tech">Deploy</span> Single Docker image → Koyeb
            </li>
          </ul>
        </section>
      </main>
    </div>
  );
}

export default App;
