/**
 * Category helper functions shared by UI components.
 *
 * REQ: FUNC-CAT-001
 */

import type { Category } from "../api/types";

/** Return active leaf categories (categories that have no active/inactive children). */
export function leafActiveCategories(categories: Category[]): Category[] {
  const parentIds = new Set<string>();
  for (const category of categories) {
    if (category.parent_id !== null) {
      parentIds.add(category.parent_id);
    }
  }
  return categories.filter((category) => category.active && !parentIds.has(category.category_id));
}
