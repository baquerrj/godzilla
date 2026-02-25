/**
 * Browser download helper for generated/exported blobs.
 *
 * REQ: FUNC-EXP-001, FUNC-EXP-002, FUNC-AUD-004, FUNC-BKP-001
 */

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
