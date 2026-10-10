import type { DraftOut } from "../api";

export function toMarkdown(d: DraftOut, title: string): string {
  const lines = [d.notice, "", `## ${title}`, ""];
  if (d.ai_policy_warnings.length) lines.push("**AI-use rules:**", ...d.ai_policy_warnings.map((w) => `- ${w}`), "");
  for (const p of d.paragraphs) {
    const flag = p.supported === false ? " **[unsupported: check before use]**" : "";
    lines.push(`${p.text}${flag} _(sources: ${p.sources.join(", ") || "none"})_`, "");
  }
  if (d.gaps.length) lines.push("**Gaps (no evidence found):**", ...d.gaps.map((g) => `- ${g}`), "");
  return lines.join("\n");
}

export function DraftView({ data, title }: { data: DraftOut; title: string }) {
  return (
    <div className="draft">
      <p className="notice">{data.notice.replace(/^>\s*/, "")}</p>
      {data.ai_policy_warnings.length > 0 && (
        <div className="warn">
          <strong>AI-use rules in this solicitation</strong>
          <ul>{data.ai_policy_warnings.map((w) => <li key={w}>{w}</li>)}</ul>
        </div>
      )}
      <h2>{title}</h2>
      {data.paragraphs.map((p, i) => (
        <div key={i} className={p.supported === false ? "para unsupported" : "para"}>
          {p.supported === false && <div className="flag">Unsupported: check before use</div>}
          <p>{p.text}</p>
          <div className="sources">{p.sources.length ? `Sources: ${p.sources.join(", ")}` : "No sources"}</div>
        </div>
      ))}
      {data.gaps.length > 0 && (
        <div className="gaps">
          <strong>Gaps: no evidence in the company's documents</strong>
          <ul>{data.gaps.map((g) => <li key={g}>{g}</li>)}</ul>
        </div>
      )}
    </div>
  );
}
