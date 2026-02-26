/**
 * Tests for AccountsTable component.
 *
 * Accounts data is provided by the parent as props; this component
 * only tests rendering behaviour given those props.
 *
 * REQ: FUNC-ACCT-003
 */

import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { AccountsTable } from "../components/AccountsTable";

const SAMPLE_ACCOUNT = {
  account_id: "acc1",
  provider_account_id: "prov-acc-1",
  item_id: "item-1",
  institution_id: "ins_1",
  name: "Plaid Checking",
  account_type: "depository",
  subtype: "checking",
  mask: "0000",
  balance: 1200.5,
  currency: "USD",
  owner_names: [],
};

describe("AccountsTable", () => {
  it("shows loading state  REQ: FUNC-ACCT-003", () => {
    render(<AccountsTable accounts={[]} loading={true} error={null} />);
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
    expect(screen.queryByTestId("accounts-table")).not.toBeInTheDocument();
  });

  it("shows empty state when no accounts  REQ: FUNC-ACCT-003", () => {
    render(<AccountsTable accounts={[]} loading={false} error={null} />);
    expect(screen.getByText(/no accounts/i)).toBeInTheDocument();
  });

  it("renders account rows  REQ: FUNC-ACCT-003", () => {
    render(<AccountsTable accounts={[SAMPLE_ACCOUNT]} loading={false} error={null} />);
    expect(screen.getByTestId("accounts-table")).toBeInTheDocument();
    expect(screen.getByText("Plaid Checking")).toBeInTheDocument();
    expect(screen.getByText("1200.50")).toBeInTheDocument();
    expect(screen.getByText("••••0000")).toBeInTheDocument();
  });

  it("shows error state  REQ: FUNC-ACCT-003", () => {
    render(<AccountsTable accounts={[]} loading={false} error="Network error" />);
    expect(screen.getByText(/failed to load accounts/i)).toBeInTheDocument();
  });
});
