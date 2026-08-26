import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "./api";

describe("owner-token API access", () => {
  afterEach(() => vi.restoreAllMocks());

  it("sends the owner token on analysis-scoped requests", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: async () => ({ analysis_id: "analysis_demo", status: "completed", repository: { name: "demo", source_type: "zip" } }),
    } as Response);

    await api.getAnalysis("analysis/demo", "owner-secret");

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/analysis/analysis%2Fdemo",
      expect.objectContaining({
        headers: expect.objectContaining({ "X-Owner-Token": "owner-secret" }),
      }),
    );
  });

  it("does not send an owner header when no token exists", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: async () => ({ analysis_id: "analysis_demo", status: "completed", repository: { name: "demo", source_type: "zip" } }),
    } as Response);

    await api.getAnalysis("analysis_demo");

    const [, options] = fetchMock.mock.calls[0];
    expect(options?.headers).not.toHaveProperty("X-Owner-Token");
  });
});
