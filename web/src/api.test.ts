import { afterEach, describe, expect, it, vi } from "vitest";
import { discover, isError } from "./api";

const respond = (status: number, body: string, type = "application/json") =>
  vi.stubGlobal("fetch", vi.fn(async () => new Response(body, { status, headers: { "Content-Type": type } })));

afterEach(() => vi.unstubAllGlobals());

describe("api client", () => {
  it("turns a plain-text server error into an ApiError, not 'API is not running'", async () => {
    respond(500, "Internal Server Error", "text/plain");
    const r = await discover("x");
    expect(isError(r) && r.error).toMatch(/500/);
  });

  it("turns a validation error ({detail}) into an ApiError", async () => {
    respond(422, JSON.stringify({ detail: [{ msg: "String should have at most 1000 characters" }] }));
    const r = await discover("x");
    expect(isError(r) && r.error).toMatch(/at most 1000/);
  });
});
