import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("../api", async (orig) => ({
  ...(await orig<typeof import("../api")>()),
  getBrief: vi.fn(async () => ({ error: "No brief yet", hint: "Analyze first" })),
  analyze: vi.fn(async () => ({ status: "odd", cost_usd: 0, cached: false, session_spent_usd: 0 })),
}));

import { OpportunityPage } from "./Opportunity";

const c = { opportunity_id: "x", title: "T", agency: "A", close_at: null, eligibility: "unchecked", why: "" };

describe("OpportunityPage", () => {
  it("does not crash when the analyze response has no verdict", async () => {
    render(<OpportunityPage c={c} onDraft={() => {}} onCost={() => {}} />);
    fireEvent.click(screen.getByText(/Analyze eligibility/));
    await waitFor(() => expect(screen.getByRole("alert")).toBeTruthy());
    expect(screen.getByText("T")).toBeTruthy();
  });
});
