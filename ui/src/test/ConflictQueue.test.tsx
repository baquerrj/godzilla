/**
 * Tests for ConflictQueue component.
 *
 * REQ: FUNC-SYNC-006, FUNC-SYNC-007
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { ConflictQueue } from "../components/ConflictQueue";
import type { Conflict } from "../api/types";

vi.mock("../api/client", async () => {
  const actual = await vi.importActual<typeof import("../api/client")>("../api/client");
  return {
    ...actual,
    GodzillaApi: {
      getAccounts: vi.fn(),
      getTransactions: vi.fn(),
      getTransaction: vi.fn(),
      patchTransaction: vi.fn(),
      postSplits: vi.fn(),
      getBalances: vi.fn(),
      getSyncState: vi.fn(),
      getCategories: vi.fn(),
      postCategory: vi.fn(),
      patchCategory: vi.fn(),
      getConflicts: vi.fn(),
      resolveConflict: vi.fn(),
      plaidLink: vi.fn(),
      plaidSync: vi.fn(),
    },
  };
});

import { GodzillaApi } from "../api/client";
const mockGetConflicts = vi.mocked(GodzillaApi.getConflicts);
const mockResolveConflict = vi.mocked(GodzillaApi.resolveConflict);

const TOKEN = "tok";

const makeConflict = (id: string): Conflict => ({
  conflict_id: id,
  entity_type: "transaction",
  entity_id: "txn-1",
  field_name: "display_name",
  local_value: "My Name",
  provider_value: "Provider Name",
  status: "open",
  resolution_choice: null,
});

describe("ConflictQueue", () => {
  beforeEach(() => vi.clearAllMocks());

  it("renders nothing when no open conflicts  REQ: FUNC-SYNC-006", async () => {
    mockGetConflicts.mockResolvedValue([]);
    const { container } = render(<ConflictQueue token={TOKEN} refreshKey={0} />);
    await waitFor(() => {
      // The component returns null when conflicts is empty
      expect(container.firstChild).toBeNull();
    });
  });

  it("shows conflict rows with local and provider values  REQ: FUNC-SYNC-006", async () => {
    mockGetConflicts.mockResolvedValue([makeConflict("conf-1")]);
    render(<ConflictQueue token={TOKEN} refreshKey={0} />);
    await waitFor(() => {
      expect(screen.getByTestId("conflict-table")).toBeInTheDocument();
      expect(screen.getByText("My Name")).toBeInTheDocument();
      expect(screen.getByText("Provider Name")).toBeInTheDocument();
    });
  });

  it("resolves conflict with local choice  REQ: FUNC-SYNC-007", async () => {
    const conflict = makeConflict("conf-2");
    mockGetConflicts.mockResolvedValue([conflict]);
    mockResolveConflict.mockResolvedValue({
      ...conflict,
      status: "resolved",
      resolution_choice: "local",
    });

    render(<ConflictQueue token={TOKEN} refreshKey={0} />);
    await waitFor(() => screen.getByTestId("keep-local-conf-2"));
    fireEvent.click(screen.getByTestId("keep-local-conf-2"));

    await waitFor(() => {
      expect(mockResolveConflict).toHaveBeenCalledWith(TOKEN, "conf-2", {
        resolution_choice: "local",
      });
    });
  });

  it("shows error on fetch failure  REQ: FUNC-SYNC-006", async () => {
    mockGetConflicts.mockRejectedValue(new Error("DB error"));
    render(<ConflictQueue token={TOKEN} refreshKey={0} />);
    await waitFor(() => {
      expect(screen.getByText(/failed to load conflicts/i)).toBeInTheDocument();
    });
  });
});
