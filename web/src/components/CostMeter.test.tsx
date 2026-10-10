import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CostMeter } from "./CostMeter";

describe("CostMeter", () => {
  it("shows last action cost and session total against the budget", () => {
    render(<CostMeter last={0.042} cached={false} spent={0.07} budget={0.5} />);
    expect(screen.getByText("Last action: $0.042")).toBeTruthy();
    expect(screen.getByText("Session: $0.070 of $0.50")).toBeTruthy();
  });
  it("labels cached results as free", () => {
    render(<CostMeter last={0} cached={true} spent={0.07} budget={0.5} />);
    expect(screen.getByText("Last action: cached (free)")).toBeTruthy();
  });
});
