import { useState } from "react";
import { type ApiError, type Candidate, discover, type DiscoverOut, isError, type Live } from "../api";
import { ErrorBox } from "../components/ErrorBox";

type Props = { onOpen: (c: Candidate) => void; onCost: (cost: number, cached: boolean, spent: number) => void };

export function SearchPage({ onOpen, onCost }: Props) {
  const [q, setQ] = useState("");
  const [out, setOut] = useState<Live<DiscoverOut> | null>(null);
  const [err, setErr] = useState<ApiError | null>(null);
  const [busy, setBusy] = useState(false);

  async function run() {
    setBusy(true);
    setErr(null);
    const r = await discover(q);
    setBusy(false);
    if (isError(r)) return setErr(r);
    setOut(r);
    onCost(r.cost_usd, r.cached, r.session_spent_usd);
  }

  return (
    <section>
      <div className="row">
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="e.g. SBIR work on grid-forming inverters" />
        <button disabled={busy || !q.trim()} onClick={run}>{busy ? "Searching…" : "Search (≈ $0.003)"}</button>
      </div>
      <ErrorBox e={err} />
      {out && (
        <>
          <p className="muted">{`Plan: ${out.plan.intent} — queries: ${out.plan.queries.map((x) => x.text).join(" · ")}`}</p>
          <div className="cards">
            {out.candidates.map((c) => (
              <article key={c.opportunity_id} className="card">
                <div className={`pill ${c.eligibility.toLowerCase()}`}>{c.eligibility}</div>
                <h3>{c.title}</h3>
                <div className="muted">{`${c.agency} · closes ${c.close_at ?? "n/a"}`}</div>
                <p>{c.why || "No quoted reason (weak match)."}</p>
                <button onClick={() => onOpen(c)}>Open</button>
              </article>
            ))}
          </div>
        </>
      )}
    </section>
  );
}
