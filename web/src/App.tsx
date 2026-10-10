import { useEffect, useState } from "react";
import { type Candidate, isError, session } from "./api";
import { CostMeter } from "./components/CostMeter";
import { DraftPage } from "./pages/Draft";
import { OpportunityPage } from "./pages/Opportunity";
import { SearchPage } from "./pages/Search";

type View = "search" | "opportunity" | "draft";

export default function App() {
  const [view, setView] = useState<View>("search");
  const [cand, setCand] = useState<Candidate | null>(null);
  const [sections, setSections] = useState<string[]>([]);
  const [last, setLast] = useState<number | null>(null);
  const [cached, setCached] = useState(false);
  const [spent, setSpent] = useState(0);
  const [budget, setBudget] = useState(0.5);

  useEffect(() => {
    session().then((s) => { if (!isError(s)) { setSpent(s.spent_usd); setBudget(s.budget_usd); } });
  }, []);

  const onCost = (cost: number, wasCached: boolean, total: number) => { setLast(cost); setCached(wasCached); setSpent(total); };

  return (
    <div className="app">
      <header>
        <h1 onClick={() => setView("search")}>Grant capture</h1>
        <nav>
          <button onClick={() => setView("search")}>Search</button>
          {cand && <button onClick={() => setView("opportunity")}>Opportunity</button>}
        </nav>
        <CostMeter last={last} cached={cached} spent={spent} budget={budget} />
      </header>
      <main>
        {view === "search" && <SearchPage onOpen={(c) => { setCand(c); setView("opportunity"); }} onCost={onCost} />}
        {view === "opportunity" && cand && <OpportunityPage c={cand} onDraft={(s) => { setSections(s); setView("draft"); }} onCost={onCost} />}
        {view === "draft" && cand && <DraftPage opportunityId={cand.opportunity_id} sections={sections} onCost={onCost} />}
      </main>
      <footer className="muted">Live: every action calls Gemini and shows its cost. Synthetic company data.</footer>
    </div>
  );
}
