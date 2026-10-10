import { useEffect, useState } from "react";
import { type AnalyzeOut, analyze, type ApiError, type Brief, type Candidate, getBrief, isError, type Item, type Live } from "../api";
import { CitationChip } from "../components/CitationChip";
import { ErrorBox } from "../components/ErrorBox";

type Props = { c: Candidate; onDraft: (sections: string[]) => void; onCost: (cost: number, cached: boolean, spent: number) => void };

function List({ title, items }: { title: string; items: Item[] }) {
  if (!items.length) return null;
  return (
    <div>
      <h3>{title}</h3>
      <ul>
        {items.map((it, i) => (
          <li key={i}>
            {it.text ?? it.name ?? it.title ?? `${it.label}: ${it.when}`} <CitationChip c={it.citation} />
          </li>
        ))}
      </ul>
    </div>
  );
}

export function OpportunityPage({ c, onDraft, onCost }: Props) {
  const [brief, setBrief] = useState<Brief | null>(null);
  const [verdict, setVerdict] = useState<Live<AnalyzeOut> | null>(null);
  const [err, setErr] = useState<ApiError | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getBrief(c.opportunity_id).then((b) => { if (!isError(b)) setBrief(b); });
  }, [c.opportunity_id]);

  async function run() {
    setBusy(true);
    setErr(null);
    const r = await analyze(c.opportunity_id);
    setBusy(false);
    if (isError(r)) return setErr(r);
    if (!r.verdict || !r.brief) {
      return setErr({ error: "Analyze returned no verdict.", hint: "This opportunity may have no documents to read; open another one." });
    }
    setVerdict(r);
    setBrief(r.brief);
    onCost(r.cost_usd, r.cached, r.session_spent_usd);
  }

  return (
    <section>
      <h2>{c.title}</h2>
      <div className="muted">{`${c.agency} · closes ${c.close_at ?? "n/a"}`}</div>
      <div className="row">
        <button disabled={busy} onClick={run}>{busy ? "Analyzing… (about 1 min)" : "Analyze eligibility (≈ $0.04)"}</button>
        {brief && <button onClick={() => onDraft(brief.required_sections.map((s) => s.title ?? "").filter(Boolean))}>Draft a section</button>}
      </div>
      <ErrorBox e={err} />
      {verdict && <div className={`pill big ${verdict.verdict.toLowerCase()}`}>{verdict.verdict}</div>}
      {brief && (
        <>
          {brief.ai_policy.length > 0 && <div className="warn"><List title="AI-use rules" items={brief.ai_policy} /></div>}
          <List title="Requirements" items={brief.requirements} />
          <List title="Evaluation criteria" items={brief.evaluation_criteria} />
          <List title="Required sections" items={brief.required_sections} />
          <List title="Deadlines" items={brief.deadlines} />
        </>
      )}
      {!brief && !busy && <p className="muted">Not analyzed yet. Analyze to see eligibility, requirements and page citations.</p>}
    </section>
  );
}
