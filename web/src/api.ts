export type ApiError = { error: string; hint: string };
export type Live<T> = T & { cost_usd: number; cached: boolean; session_spent_usd: number };
export type Candidate = { opportunity_id: string; title: string; agency: string; close_at: string | null; eligibility: string; why: string };
export type DiscoverOut = { plan: { intent: string; queries: { text: string }[] }; candidates: Candidate[]; iterations: number };
export type Citation = { document_id: string; page: number; quote: string };
export type Item = { text?: string; name?: string; title?: string; label?: string; when?: string; citation: Citation };
export type Brief = { opportunity_id: string; requirements: Item[]; evaluation_criteria: Item[]; required_sections: Item[]; deadlines: Item[]; ai_policy: Item[] };
export type AnalyzeOut = { verdict: string; deciding_clauses: { reason?: string; clause: { citation: Citation } }[]; brief: Brief };
export type DraftOut = { notice: string; ai_policy_warnings: string[]; paragraphs: { text: string; sources: string[]; supported: boolean | null }[]; gaps: string[] };

export const isError = (x: unknown): x is ApiError => typeof x === "object" && x !== null && "error" in x;

async function call<T>(path: string, body?: unknown): Promise<T | ApiError> {
  try {
    const res = await fetch(path, body === undefined ? undefined : {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
    return (await res.json()) as T | ApiError;
  } catch {
    return { error: "The API is not running.", hint: "Start it: uv run uvicorn api.main:app --host 127.0.0.1 --port 8080" };
  }
}

export const discover = (request: string) => call<Live<DiscoverOut>>("/api/discover", { request });
export const analyze = (id: string) => call<Live<AnalyzeOut>>("/api/analyze", { opportunity_id: id });
export const getBrief = (id: string) => call<Brief>(`/api/brief/${encodeURIComponent(id)}`);
export const draft = (id: string, sectionTitle: string) => call<Live<DraftOut>>("/api/draft", { opportunity_id: id, section_title: sectionTitle });
export const session = () => call<{ spent_usd: number; budget_usd: number }>("/api/session");
