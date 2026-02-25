/**
 * Tests for AuthGatePanel setup/unlock workflow.
 *
 * REQ: SEC-ACC-001, SEC-ACC-003
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AuthGatePanel } from "../components/AuthGatePanel";

vi.mock("../api/client", async () => {
  const actual =
    await vi.importActual<typeof import("../api/client")>("../api/client");
  return {
    ...actual,
    GodzillaApi: {
      getAuthStatus: vi.fn(),
      setupPin: vi.fn(),
      unlock: vi.fn(),
    },
  };
});

import { GodzillaApi } from "../api/client";

const mockGetAuthStatus = vi.mocked(GodzillaApi.getAuthStatus);
const mockSetupPin = vi.mocked(GodzillaApi.setupPin);
const mockUnlock = vi.mocked(GodzillaApi.unlock);

describe("AuthGatePanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows setup flow and saves new pin  REQ: SEC-ACC-003", async () => {
    mockGetAuthStatus
      .mockResolvedValueOnce({
        pin_configured: false,
        setup_required: true,
        locked: true,
        auto_lock_minutes: 15,
        unlock_expires_at_utc: null,
        dev_bypass_enabled: false,
        tls: { enabled: true, cert_fingerprint_sha256: "ABC" },
      })
      .mockResolvedValueOnce({
        pin_configured: true,
        setup_required: false,
        locked: true,
        auto_lock_minutes: 15,
        unlock_expires_at_utc: null,
        dev_bypass_enabled: false,
        tls: { enabled: true, cert_fingerprint_sha256: "ABC" },
      });
    mockSetupPin.mockResolvedValue({ pin_configured: true });
    const onAuthenticated = vi.fn();

    render(<AuthGatePanel token="tok" onAuthenticated={onAuthenticated} />);

    await waitFor(() => {
      expect(screen.getByTestId("auth-setup-panel")).toBeInTheDocument();
    });
    await userEvent.type(screen.getByPlaceholderText("New PIN"), "123456");
    await userEvent.type(screen.getByPlaceholderText("Confirm PIN"), "123456");
    await userEvent.click(screen.getByTestId("setup-pin-btn"));

    await waitFor(() => {
      expect(mockSetupPin).toHaveBeenCalledWith("tok", { new_pin: "123456" });
      expect(mockGetAuthStatus).toHaveBeenCalledTimes(2);
    });
  });

  it("unlocks when valid pin is submitted  REQ: SEC-ACC-001", async () => {
    mockGetAuthStatus.mockResolvedValue({
      pin_configured: true,
      setup_required: false,
      locked: true,
      auto_lock_minutes: 15,
      unlock_expires_at_utc: null,
      dev_bypass_enabled: false,
      tls: { enabled: true, cert_fingerprint_sha256: "ABC" },
    });
    mockUnlock.mockResolvedValue({
      unlock_token: "unlock-123",
      expires_at_utc: "2026-01-01T00:00:00",
    });
    const onAuthenticated = vi.fn();

    render(<AuthGatePanel token="tok" onAuthenticated={onAuthenticated} />);
    await waitFor(() => {
      expect(screen.getByTestId("auth-unlock-panel")).toBeInTheDocument();
    });

    await userEvent.type(screen.getByTestId("unlock-pin-input"), "123456");
    await userEvent.click(screen.getByTestId("unlock-btn"));

    await waitFor(() => {
      expect(mockUnlock).toHaveBeenCalledWith("tok", { pin: "123456" });
      expect(onAuthenticated).toHaveBeenCalledWith("unlock-123");
    });
  });

  it("auto-authenticates when already unlocked  REQ: SEC-ACC-001", async () => {
    mockGetAuthStatus.mockResolvedValue({
      pin_configured: false,
      setup_required: false,
      locked: false,
      auto_lock_minutes: 15,
      unlock_expires_at_utc: null,
      dev_bypass_enabled: true,
      tls: { enabled: false, cert_fingerprint_sha256: null },
    });
    const onAuthenticated = vi.fn();

    render(<AuthGatePanel token="tok" onAuthenticated={onAuthenticated} />);

    await waitFor(() => {
      expect(onAuthenticated).toHaveBeenCalledWith(null);
    });
  });
});
