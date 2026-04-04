/**
 * Download and save helpers for generated/exported blobs.
 *
 * REQ: ACC-EXP-001, ACC-EXP-002, ACC-AUD-004, ACC-BKP-001
 */

function hasTauriRuntime(): boolean {
  return (
    typeof window !== "undefined"
    && "__TAURI_INTERNALS__" in (window as unknown as Record<string, unknown>)
  );
}

export function downloadBlob(blob: Blob, filename: string): void {
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = filename;
  anchor.style.display = "none";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(objectUrl);
}

export async function saveBlob(blob: Blob, filename: string): Promise<boolean> {
  // REQ: ACC-EXP-001, ACC-EXP-002, ACC-AUD-004, ACC-BKP-001
  // Desktop runtime uses an explicit native save destination.
  if (hasTauriRuntime()) {
    const [{ save }, { writeFile }] = await Promise.all([
      import("@tauri-apps/plugin-dialog"),
      import("@tauri-apps/plugin-fs"),
    ]);
    const destination = await save({
      defaultPath: filename,
      filters: [{ name: "Godzilla Backup", extensions: ["gzbk"] }],
    });
    if (!destination) {
      return false;
    }
    await writeFile(destination, new Uint8Array(await blob.arrayBuffer()));
    return true;
  }

  downloadBlob(blob, filename);
  return true;
}
