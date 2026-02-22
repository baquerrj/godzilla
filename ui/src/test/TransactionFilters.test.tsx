/**
 * Tests for TransactionFilters component.
 *
 * REQ: FUNC-TXN-002
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { TransactionFilters, EMPTY_FILTERS } from "../components/TransactionFilters";
import type { FilterValues } from "../components/TransactionFilters";
import type { Category } from "../api/types";

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

const TOKEN = "tok";
void TOKEN;

describe("TransactionFilters", () => {
  it("renders all filter inputs  REQ: FUNC-TXN-002", () => {
    const onChange = vi.fn();
    render(
      <TransactionFilters
        values={EMPTY_FILTERS}
        categories={[]}
        onChange={onChange}
        onReset={vi.fn()}
      />,
    );
    expect(screen.getByTestId("filter-date-from")).toBeInTheDocument();
    expect(screen.getByTestId("filter-date-to")).toBeInTheDocument();
    expect(screen.getByTestId("filter-merchant")).toBeInTheDocument();
    expect(screen.getByTestId("filter-amount-min")).toBeInTheDocument();
    expect(screen.getByTestId("filter-amount-max")).toBeInTheDocument();
    expect(screen.getByTestId("filter-category")).toBeInTheDocument();
  });

  it("shows only leaf active categories in dropdown  REQ: FUNC-TXN-002", () => {
    const onChange = vi.fn();
    const cats: Category[] = [
      makeCategory("food", "Food"),
      makeCategory("food_coffee", "Coffee", "food"),
      makeCategory("income", "Income"),
    ];
    render(
      <TransactionFilters
        values={EMPTY_FILTERS}
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

  it("calls onChange when merchant changes  REQ: FUNC-TXN-002", () => {
    const onChange = vi.fn();
    render(
      <TransactionFilters
        values={EMPTY_FILTERS}
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

  it("calls onReset when Reset is clicked  REQ: FUNC-TXN-002", () => {
    const onReset = vi.fn();
    render(
      <TransactionFilters
        values={EMPTY_FILTERS}
        categories={[]}
        onChange={vi.fn()}
        onReset={onReset}
      />,
    );
    fireEvent.click(screen.getByTestId("filter-reset"));
    expect(onReset).toHaveBeenCalledOnce();
  });
});
