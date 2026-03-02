/**
 * Tests for DataManagementPanel component.
 *
 * REQ: FUNC-BKP-001, FUNC-BKP-003, FUNC-BKP-004, FUNC-BKP-006
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { DataManagementPanel } from "../components/DataManagementPanel";

vi.mock("../utils/download", () => ({
  saveBlob: vi.fn(),
}));

vi.mock("../api/client", async () => {
  const actual =
    await vi.importActual<typeof import("../api/client")>("../api/client");
  return {
    ...actual,
    GodzillaApi: {
      createBackup: vi.fn(),
      restoreBackup: vi.fn(),
      wipeData: vi.fn(),
      reinitializeDatabase: vi.fn(),
    },
  };
});

import { GodzillaApi } from "../api/client";
import { saveBlob } from "../utils/download";

const TOKEN = "tok";

const mockCreateBackup = vi.mocked(GodzillaApi.createBackup);
const mockRestoreBackup = vi.mocked(GodzillaApi.restoreBackup);
const mockWipeData = vi.mocked(GodzillaApi.wipeData);
const mockReinitializeDatabase = vi.mocked(GodzillaApi.reinitializeDatabase);
const mockSaveBlob = vi.mocked(saveBlob);

describe("DataManagementPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockCreateBackup.mockResolvedValue({
      blob: new Blob(["backup"], { type: "application/octet-stream" }),
      filename: "godzilla-backup.gzbk",
      contentType: "application/octet-stream",
    });
    mockSaveBlob.mockResolvedValue(true);
    mockRestoreBackup.mockResolvedValue({
      restored_database: true,
      restored_secrets: true,
      schema_version: 3,
    });
    mockWipeData.mockResolvedValue({
      deleted_files: ["/tmp/db"],
      missing_files: [],
      failed_files: [],
    });
    mockReinitializeDatabase.mockResolvedValue({
      schema_version: 3,
    });
  });

  it("downloads encrypted backup  REQ: FUNC-BKP-001", async () => {
    render(<DataManagementPanel token={TOKEN} onDataChanged={vi.fn()} />);

    fireEvent.change(screen.getByTestId("backup-passphrase-input"), {
      target: { value: "m5-passphrase" },
    });
    fireEvent.click(screen.getByTestId("backup-download-btn"));

    await waitFor(() => {
      expect(mockCreateBackup).toHaveBeenCalledWith(TOKEN, {
        passphrase: "m5-passphrase",
        include_secrets: true,
      });
      expect(mockSaveBlob).toHaveBeenCalledWith(expect.any(Blob), "godzilla-backup.gzbk");
      expect(screen.getByText("Backup saved.")).toBeInTheDocument();
    });
  });

  it("reports when backup save is canceled  REQ: FUNC-BKP-001", async () => {
    mockSaveBlob.mockResolvedValue(false);
    render(<DataManagementPanel token={TOKEN} onDataChanged={vi.fn()} />);

    fireEvent.change(screen.getByTestId("backup-passphrase-input"), {
      target: { value: "m5-passphrase" },
    });
    fireEvent.click(screen.getByTestId("backup-download-btn"));

    await waitFor(() => {
      expect(screen.getByText("Backup save canceled.")).toBeInTheDocument();
    });
  });

  it("restores backup file and notifies parent  REQ: FUNC-BKP-003", async () => {
    const onDataChanged = vi.fn();
    render(<DataManagementPanel token={TOKEN} onDataChanged={onDataChanged} />);

    // TODO: Add a restore error-path component test that asserts backend
    // validation/detail messages are rendered clearly in the panel UI.
    const file = new File(["payload"], "backup.gzbk", { type: "application/octet-stream" });
    fireEvent.change(screen.getByTestId("restore-passphrase-input"), {
      target: { value: "m5-passphrase" },
    });
    fireEvent.change(screen.getByTestId("restore-file-input"), {
      target: { files: [file] },
    });
    fireEvent.click(screen.getByTestId("restore-submit-btn"));

    await waitFor(() => {
      expect(mockRestoreBackup).toHaveBeenCalledWith(TOKEN, {
        passphrase: "m5-passphrase",
        file,
      });
      expect(onDataChanged).toHaveBeenCalled();
    });
  });

  it("requires confirmation token before wipe  REQ: FUNC-BKP-004", async () => {
    render(<DataManagementPanel token={TOKEN} onDataChanged={vi.fn()} />);

    const wipeButton = screen.getByTestId("wipe-submit-btn");
    expect(wipeButton).toBeDisabled();

    fireEvent.change(screen.getByTestId("wipe-confirm-input"), {
      target: { value: "WIPE_LOCAL_DATA" },
    });
    expect(wipeButton).toBeEnabled();

    fireEvent.click(wipeButton);

    await waitFor(() => {
      expect(mockWipeData).toHaveBeenCalledWith(TOKEN, { confirm: "WIPE_LOCAL_DATA" });
    });
  });

  it("re-initializes database and notifies parent  REQ: FUNC-BKP-006", async () => {
    const onDataChanged = vi.fn();
    render(<DataManagementPanel token={TOKEN} onDataChanged={onDataChanged} />);

    fireEvent.click(screen.getByTestId("reinitialize-submit-btn"));

    await waitFor(() => {
      expect(mockReinitializeDatabase).toHaveBeenCalledWith(TOKEN);
      expect(onDataChanged).toHaveBeenCalled();
      expect(screen.getByText(/Database re-initialized/i)).toBeInTheDocument();
    });
  });
});
