import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, apiFetch } from "./client";

function mockFetch(status: number, body: unknown) {
  return vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    text: async () => JSON.stringify(body),
  } as Response);
}

afterEach(() => vi.restoreAllMocks());

describe("apiFetch", () => {
  it("unwraps the data envelope on success", async () => {
    vi.stubGlobal("fetch", mockFetch(200, { success: true, data: { x: 1 }, error: null }));
    const d = await apiFetch<{ x: number }>("/thing");
    expect(d.x).toBe(1);
  });

  it("throws ApiError with code on backend error envelope", async () => {
    vi.stubGlobal(
      "fetch",
      mockFetch(404, { success: false, data: null, error: { code: "NOT_FOUND", message: "gone" } }),
    );
    await expect(apiFetch("/missing")).rejects.toMatchObject({ code: "NOT_FOUND", status: 404 });
  });

  it("throws MALFORMED_RESPONSE on non-JSON body", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, status: 200, text: async () => "<html>oops" }),
    );
    await expect(apiFetch("/bad")).rejects.toBeInstanceOf(ApiError);
  });

  it("throws NETWORK_ERROR when fetch rejects", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("connection refused")));
    await expect(apiFetch("/down")).rejects.toMatchObject({ code: "NETWORK_ERROR" });
  });
});
