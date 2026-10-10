import { useState } from "react";
import { type ApiError, type DraftOut, draft, isError, type Live } from "../api";
import { DraftView, toMarkdown } from "../components/DraftView";
import { ErrorBox } from "../components/ErrorBox";

type Props = { opportunityId: string; sections: string[]; onCost: (cost: number, cached: boolean, spent: number) => void };

export function DraftPage({ opportunityId, sections, onCost }: Props) {
  const [title, setTitle] = useState(sections[0] ?? "");
  const [out, setOut] = useState<Live<DraftOut> | null>(null);
  const [err, setErr] = useState<ApiError | null>(null);
  const [busy, setBusy] = useState(false);

  async function run() {
    setBusy(true);
    setErr(null);
    const r = await draft(opportunityId, title);
    setBusy(false);
    if (isError(r)) return setErr(r);
    setOut(r);
    onCost(r.cost_usd, r.cached, r.session_spent_usd);
  }

  function download() {
    if (!out) return;
    const blob = new Blob([toMarkdown(out, title)], { type: "text/markdown" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `draft-${title.replace(/[^a-z0-9]+/gi, "-").toLowerCase() || "section"}.md`;
    a.click();
  }

  return (
    <section>
      <div className="row">
        {sections.length > 0 ? (
          <select value={title} onChange={(e) => setTitle(e.target.value)}>
            {sections.map((s) => <option key={s}>{s}</option>)}
          </select>
        ) : (
          <label>
            Section title
            <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Technical Approach" />
          </label>
        )}
        <button disabled={busy || !title.trim()} onClick={run}>{busy ? "Drafting…" : "Draft section (≈ $0.03-0.08)"}</button>
      </div>
      <ErrorBox e={err} />
      {out && (
        <>
          <DraftView data={out} title={title} />
          <button onClick={download}>Download Markdown</button>
        </>
      )}
    </section>
  );
}
