/**
 * Tests for TransactionFilters component.
 *
 * REQ: ACC-TXN-002
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { TransactionFilters, EMPTY_FILTERS } from "../components/TransactionFilters";
import type { Account, Category } from "../api/types";

const makeCategory = (
  id: string,
  name: string,
  parentId: string | null = null,
  active = true,
): Category => ({
  category_id: id,
  name,
  parent_id: parentId,
  active,
});

const makeAccount = (id: string, name: string): Account => ({
  account_id: id,
  provider_account_id: `${id}-provider`,
  item_id: "item-1",
  institution_id: "ins_1",
  name,
  account_type: "depository",
  subtype: "checking",
  mask: "1234",
  balance: 100,
  currency: "USD",
  owner_names: [],
});

describe("TransactionFilters", () => {
  it("renders all filter inputs  REQ: ACC-TXN-002", () => {
    const onChange = vi.fn();
    render(
      <TransactionFilters
        values={EMPTY_FILTERS}
        accounts={[]}
        categories={[]}
        onChange={onChange}
        onReset={vi.fn()}
      />,
    );
    expect(screen.getByTestId("filter-account")).toBeInTheDocument();
    expect(screen.getByTestId("filter-date-from")).toBeInTheDocument();
    expect(screen.getByTestId("filter-date-to")).toBeInTheDocument();
    expect(screen.getByTestId("filter-merchant")).toBeInTheDocument();
    expect(screen.getByTestId("filter-amount-min")).toBeInTheDocument();
    expect(screen.getByTestId("filter-amount-max")).toBeInTheDocument();
    expect(screen.getByTestId("filter-category")).toBeInTheDocument();
  });

  it("shows only leaf active categories in dropdown  REQ: ACC-TXN-002", () => {
    const onChange = vi.fn();
    const cats: Category[] = [
      makeCategory("food", "Food"),
      makeCategory("food_coffee", "Coffee", "food"),
      makeCategory("income", "Income"),
    ];
    render(
      <TransactionFilters
        values={EMPTY_FILTERS}
        accounts={[]}
        categories={cats}
        onChange={onChange}
        onReset={vi.fn()}
      />,
    );
    // "Food" is a parent — should not appear; "Coffee" and "Income" are leaves
    const select = screen.getByTestId("filter-category");
    expect(select).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "Food" })).not.toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Coffee" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Income" })).toBeInTheDocument();
  });

  it("calls onChange when merchant changes  REQ: ACC-TXN-002", () => {
    const onChange = vi.fn();
    render(
      <TransactionFilters
        values={EMPTY_FILTERS}
        accounts={[]}
        categories={[]}
        onChange={onChange}
        onReset={vi.fn()}
      />,
    );
    fireEvent.change(screen.getByTestId("filter-merchant"), {
      target: { value: "Starbucks" },
    });
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ merchant: "Starbucks" }),
    );
  });

  it("calls onReset when Reset is clicked  REQ: ACC-TXN-002", () => {
    const onReset = vi.fn();
    render(
      <TransactionFilters
        values={EMPTY_FILTERS}
        accounts={[]}
        categories={[]}
        onChange={vi.fn()}
        onReset={onReset}
      />,
    );
    fireEvent.click(screen.getByTestId("filter-reset"));
    expect(onReset).toHaveBeenCalledOnce();
  });

  it("calls onChange when account changes  REQ: ACC-TXN-002", () => {
    const onChange = vi.fn();
    render(
      <TransactionFilters
        values={EMPTY_FILTERS}
        accounts={[makeAccount("acc_1", "Checking")]}
        categories={[]}
        onChange={onChange}
        onReset={vi.fn()}
      />,
    );
    fireEvent.change(screen.getByTestId("filter-account"), {
      target: { value: "acc_1" },
    });
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ account_id: "acc_1" }),
    );
  });
});
