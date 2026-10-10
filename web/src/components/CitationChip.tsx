import type { Citation } from "../api";

export function CitationChip({ c }: { c: Citation }) {
  return <span className="chip" title={c.quote}>{`p. ${c.page}`}</span>;
}
