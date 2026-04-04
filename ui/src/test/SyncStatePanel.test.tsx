/**
 * Tests for SyncStatePanel: connect, sync actions, state display.
 *
 * REQ: ACC-ACCT-001, ACC-ACCT-002, ACC-ACCT-004, ACC-ACCT-005,
 * REQ: ACC-ACCT-008, ACC-SYNC-001
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SyncStatePanel } from "../components/SyncStatePanel";

vi.mock("../api/client", async () => {
  const actual =
    await vi.importActual<typeof import("../api/client")>("../api/client");
  return {
    ...actual,
    GodzillaApi: {
      getSyncState: vi.fn(),
      plaidLink: vi.fn(),
      plaidSync: vi.fn(),
      unlinkItem: vi.fn(),
      getAccounts: vi.fn(),
      getTransactions: vi.fn(),
      getBalances: vi.fn(),
    },
  };
});

import { GodzillaApi } from "../api/client";
const mockGetSyncState = vi.mocked(GodzillaApi.getSyncState);
const mockPlaidLink = vi.mocked(GodzillaApi.plaidLink);
const mockPlaidSync = vi.mocked(GodzillaApi.plaidSync);
const mockUnlinkItem = vi.mocked(GodzillaApi.unlinkItem);

const TOKEN = "tok";
const defaultProps = { token: TOKEN, refreshKey: 0, onRefresh: vi.fn() };

describe("SyncStatePanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(window, "confirm").mockReturnValue(true);
  });

  it("shows empty state when no items  REQ: ACC-ACCT-004", async () => {
    mockGetSyncState.mockResolvedValue([]);
    render(<SyncStatePanel {...defaultProps} />);
    await waitFor(() => {
      expect(screen.getByText(/no linked accounts/i)).toBeInTheDocument();
    });
  });

  it("displays sync state rows  REQ: ACC-ACCT-004", async () => {
    mockGetSyncState.mockResolvedValue([
      {
        item_id: "item-abc-123",
        institution_id: "ins_1",
        status: "active",
        last_sync_at_utc: null,
        last_sync_at_tz: null,
        last_sync_at_offset_minutes: null,
        last_sync_status: null,
        cursor: null,
      },
    ]);
    render(<SyncStatePanel {...defaultProps} />);
    await waitFor(() => {
      expect(screen.getByTestId("sync-table")).toBeInTheDocument();
      expect(screen.getByText("ins_1")).toBeInTheDocument();
    });
  });

  it("calls plaidLink and onRefresh on connect  REQ: ACC-ACCT-001, ACC-ACCT-002", async () => {
    mockGetSyncState.mockResolvedValue([]);
    mockPlaidLink.mockResolvedValue({
      item_id: "new-item",
      institution_id: "ins_1",
      env: "sandbox",
    });
    const onRefresh = vi.fn();
    render(<SyncStatePanel {...defaultProps} onRefresh={onRefresh} />);
    await waitFor(() => screen.getByTestId("connect-btn"));

    await userEvent.click(screen.getByTestId("connect-btn"));
    await waitFor(() => {
      expect(mockPlaidLink).toHaveBeenCalledWith(TOKEN, {});
      expect(onRefresh).toHaveBeenCalled();
      expect(screen.getByTestId("link-success")).toBeInTheDocument();
    });
  });

  it("shows link error on failure  REQ: ACC-ACCT-001", async () => {
    mockGetSyncState.mockResolvedValue([]);
    mockPlaidLink.mockRejectedValue(new Error("Plaid unavailable"));
    render(<SyncStatePanel {...defaultProps} />);
    await waitFor(() => screen.getByTestId("connect-btn"));

    await userEvent.click(screen.getByTestId("connect-btn"));
    await waitFor(() => {
      expect(screen.getByTestId("link-error")).toBeInTheDocument();
    });
  });

  it("calls plaidSync and onRefresh on run sync  REQ: ACC-ACCT-005, ACC-SYNC-001", async () => {
    const item = {
      item_id: "item-xyz",
      institution_id: "ins_2",
      status: "active",
      last_sync_at_utc: null,
      last_sync_at_tz: null,
      last_sync_at_offset_minutes: null,
      last_sync_status: null,
      cursor: null,
    };
    mockGetSyncState.mockResolvedValue([item]);
    mockPlaidSync.mockResolvedValue({
      item_id: "item-xyz",
      added: 5,
      modified: 1,
      removed: 0,
      balance_accounts: 2,
      cursor: "cur123",
    });
    const onRefresh = vi.fn();
    render(<SyncStatePanel {...defaultProps} onRefresh={onRefresh} />);
    await waitFor(() => screen.getByTestId("sync-btn-item-xyz"));

    await userEvent.click(screen.getByTestId("sync-btn-item-xyz"));
    await waitFor(() => {
      expect(mockPlaidSync).toHaveBeenCalledWith(TOKEN, {
        item_id: "item-xyz",
      });
      expect(onRefresh).toHaveBeenCalled();
      expect(screen.getByTestId("sync-success")).toBeInTheDocument();
      expect(screen.getByText(/added 5/i)).toBeInTheDocument();
    });
  });

  it("calls unlink endpoint and refreshes on keep mode  REQ: ACC-ACCT-008", async () => {
    const item = {
      item_id: "item-xyz",
      institution_id: "ins_2",
      status: "linked",
      last_sync_at_utc: null,
      last_sync_at_tz: null,
      last_sync_at_offset_minutes: null,
      last_sync_status: null,
      cursor: null,
    };
    mockGetSyncState.mockResolvedValue([item]);
    mockUnlinkItem.mockResolvedValue({
      item_id: "item-xyz",
      mode: "keep",
      token_removed: true,
      remote_revoked: true,
      raw_payload_rows_deleted: 0,
      local_data_purged: false,
    });
    const onRefresh = vi.fn();
    render(<SyncStatePanel {...defaultProps} onRefresh={onRefresh} />);
    await waitFor(() => screen.getByTestId("unlink-keep-btn-item-xyz"));

    await userEvent.click(screen.getByTestId("unlink-keep-btn-item-xyz"));
    await waitFor(() => {
      expect(mockUnlinkItem).toHaveBeenCalledWith(TOKEN, "item-xyz", "keep");
      expect(onRefresh).toHaveBeenCalled();
      expect(screen.getByTestId("unlink-success")).toBeInTheDocument();
    });
  });
});
