import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { DraftOut } from "../api";
import { DraftView, toMarkdown } from "./DraftView";

const data: DraftOut = {
  notice: "> AI-assisted first draft. Human review and rewrite required before submission.",
  ai_policy_warnings: ['No AI-developed applications ("substantially developed by AI", p. 2)'],
  paragraphs: [
    { text: "We balanced cells to 1.5%.", sources: ["project-report-01.md"], supported: true },
    { text: "<script>alert(1)</script> We store hydrogen.", sources: [], supported: false },
  ],
  gaps: ["Describe hydrogen facilities."],
};

describe("DraftView", () => {
  it("puts the notice first and marks unsupported paragraphs", () => {
    const { container } = render(<DraftView data={data} title="Facilities" />);
    expect(container.firstElementChild?.textContent).toContain("AI-assisted first draft");
    expect(container.querySelectorAll(".unsupported")).toHaveLength(1);
    expect(screen.getByText("Unsupported: check before use")).toBeTruthy();
    expect(screen.getByText("Describe hydrogen facilities.")).toBeTruthy();
    expect(screen.getByText(/substantially developed by AI/)).toBeTruthy();
  });
  it("renders model text as text, never HTML", () => {
    const { container } = render(<DraftView data={data} title="Facilities" />);
    expect(container.querySelector("script")).toBeNull();
    expect(screen.getByText(/<script>alert\(1\)<\/script>/)).toBeTruthy();
  });
  it("markdown starts with the notice and lists gaps", () => {
    const md = toMarkdown(data, "Facilities");
    expect(md.startsWith("> AI-assisted first draft")).toBe(true);
    expect(md).toContain("## Facilities");
    expect(md).toContain("- Describe hydrogen facilities.");
  });
});
