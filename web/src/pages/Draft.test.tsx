import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DraftPage } from "./Draft";

describe("DraftPage", () => {
  it("lets the user type a section when the brief lists none", () => {
    render(<DraftPage opportunityId="x" sections={[]} onCost={() => {}} />);
    expect(screen.getByLabelText("Section title")).toBeTruthy();
    expect(screen.queryByRole("combobox")).toBeNull();
  });
  it("offers the brief's required sections", () => {
    render(<DraftPage opportunityId="x" sections={["Technical Approach", "Budget"]} onCost={() => {}} />);
    expect(screen.getByRole("combobox")).toBeTruthy();
  });
});
