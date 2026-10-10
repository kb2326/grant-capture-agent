type Props = { last: number | null; cached: boolean; spent: number; budget: number };

export function CostMeter({ last, cached, spent, budget }: Props) {
  const lastText = last === null ? "Last action: none yet" : cached ? "Last action: cached (free)" : `Last action: $${last.toFixed(3)}`;
  return (
    <div className="cost-meter" aria-live="polite">
      <span>{lastText}</span>
      <span>{`Session: $${spent.toFixed(3)} of $${budget.toFixed(2)}`}</span>
    </div>
  );
}
