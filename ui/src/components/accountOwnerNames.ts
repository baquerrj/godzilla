/**
 * Helpers for rendering account owner metadata in the accounts table.
 *
 * REQ: ACC-ACCT-009, TECH-ACCT-009-UI
 */

import type { AccountOwner } from "../api/types";

export function formatOwnerNames(owners: AccountOwner[]): string | null {
  const names = owners
    .flatMap((owner) => (Array.isArray(owner.names) ? owner.names : []))
    .map((name) => name.trim())
    .filter(Boolean);
  if (names.length === 0) {
    return null;
  }
  return names.join(", ");
}
