/**
 * API transport behavior tests for browser and Tauri runtimes.
 *
 * REQ: SEC-NET-001, SEC-NET-002
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@tauri-apps/api/core", () => ({
  invoke: vi.fn(),
}));

import { invoke } from "@tauri-apps/api/core";
import { ApiError, GodzillaApi } from "../api/client";

const mockInvoke = vi.mocked(invoke);
const tauriWindow = window as Window & { __TAURI_INTERNALS__?: unknown };

describe("api/client transport", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    GodzillaApi.setUnlockToken(null);
    delete tauriWindow.__TAURI_INTERNALS__;
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("uses fetch transport when tauri runtime is unavailable  REQ: SEC-NET-002", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response("[]", {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const accounts = await GodzillaApi.getAccounts("tok");

    expect(accounts).toEqual([]);
    expect(fetch).toHaveBeenCalledOnce();
    expect(mockInvoke).not.toHaveBeenCalled();
  });

  it("uses tauri proxy transport when tauri runtime is available  REQ: SEC-NET-001", async () => {
    tauriWindow.__TAURI_INTERNALS__ = {};
    mockInvoke.mockResolvedValue({
      status: 200,
      headers: [{ name: "content-type", value: "application/json" }],
      bodyBase64: btoa("[]"),
    });

    const accounts = await GodzillaApi.getAccounts("tok");

    expect(accounts).toEqual([]);
    expect(mockInvoke).toHaveBeenCalledWith(
      "api_request",
      expect.objectContaining({
        request: expect.objectContaining({
          method: "GET",
          path: "/accounts",
        }),
      }),
    );
  });

  it("surfaces pin mismatch from tauri proxy request failures  REQ: SEC-NET-001", async () => {
    tauriWindow.__TAURI_INTERNALS__ = {};
    mockInvoke.mockRejectedValue(new Error("TLS certificate pin mismatch"));

    await expect(GodzillaApi.getAccounts("tok")).rejects.toSatisfy(
      (error: unknown) =>
        error instanceof ApiError &&
        error.statusCode === 0 &&
        error.message.includes("pin mismatch"),
    );
  });

  it("dispatches lock event on tauri proxy 423 responses  REQ: SEC-ACC-002", async () => {
    tauriWindow.__TAURI_INTERNALS__ = {};
    GodzillaApi.setUnlockToken("unlock-token");
    mockInvoke.mockResolvedValue({
      status: 423,
      headers: [{ name: "content-type", value: "application/json" }],
      bodyBase64: btoa('{"detail":"App is locked"}'),
    });

    let didLock = false;
    const onLock = () => {
      didLock = true;
    };
    window.addEventListener("godzilla-lock", onLock);
    try {
      await expect(GodzillaApi.getAccounts("tok")).rejects.toSatisfy(
        (error: unknown) =>
          error instanceof ApiError &&
          error.statusCode === 423 &&
          error.message === "App is locked",
      );
    } finally {
      window.removeEventListener("godzilla-lock", onLock);
    }
    expect(didLock).toBe(true);
  });
});
