/**
 * TransactionFilters: controlled filter form for the transactions list.
 *
 * REQ: ACC-TXN-002
 */

import type { ChangeEvent } from "react";
import type { Account, Category } from "../api/types";
import { leafActiveCategories } from "./categoryUtils";

export interface FilterValues {
  account_id: string;
  date_from: string;
  date_to: string;
  merchant: string;
  amount_min: string;
  amount_max: string;
  category_id: string;
}

export const EMPTY_FILTERS: FilterValues = {
  account_id: "",
  date_from: "",
  date_to: "",
  merchant: "",
  amount_min: "",
  amount_max: "",
  category_id: "",
};

interface Props {
  values: FilterValues;
  accounts: Account[];
  categories: Category[];
  onChange: (values: FilterValues) => void;
  onReset: () => void;
}

export function TransactionFilters({
  values,
  accounts,
  categories,
  onChange,
  onReset,
}: Props) {
  const leafCategories = leafActiveCategories(categories);

  const set = (field: keyof FilterValues) => (
    e: ChangeEvent<HTMLInputElement | HTMLSelectElement>,
  ) => onChange({ ...values, [field]: e.target.value });

  return (
    <div className="filter-bar" data-testid="transaction-filters">
      <select
        aria-label="Account"
        value={values.account_id}
        onChange={set("account_id")}
        data-testid="filter-account"
      >
        <option value="">All accounts</option>
        {accounts.map((account) => (
          <option key={account.account_id} value={account.account_id}>
            {account.name}
          </option>
        ))}
      </select>
      <input
        type="date"
        aria-label="From date"
        value={values.date_from}
        onChange={set("date_from")}
        data-testid="filter-date-from"
      />
      <input
        type="date"
        aria-label="To date"
        value={values.date_to}
        onChange={set("date_to")}
        data-testid="filter-date-to"
      />
      <input
        type="text"
        aria-label="Merchant"
        placeholder="Merchant…"
        value={values.merchant}
        onChange={set("merchant")}
        data-testid="filter-merchant"
      />
      <input
        type="number"
        aria-label="Min amount"
        placeholder="Min $"
        value={values.amount_min}
        onChange={set("amount_min")}
        data-testid="filter-amount-min"
      />
      <input
        type="number"
        aria-label="Max amount"
        placeholder="Max $"
        value={values.amount_max}
        onChange={set("amount_max")}
        data-testid="filter-amount-max"
      />
      <select
        aria-label="Category"
        value={values.category_id}
        onChange={set("category_id")}
        data-testid="filter-category"
      >
        <option value="">All categories</option>
        {leafCategories.map((c) => (
          <option key={c.category_id} value={c.category_id}>
            {c.name}
          </option>
        ))}
      </select>
      <button
        className="btn btn-sm"
        onClick={onReset}
        data-testid="filter-reset"
      >
        Reset
      </button>
    </div>
  );
}
