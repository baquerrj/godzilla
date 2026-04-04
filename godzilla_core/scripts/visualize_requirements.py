"""Generate a self-contained HTML visualization for requirement trace YAML."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any

import yaml


class RequirementsVisualizationError(ValueError):
    """Raised when the requirements trace file cannot be visualized."""


@dataclass(frozen=True)
class RequirementEntry:
    """Normalized trace entry used by the HTML generator."""

    requirement_id: str
    title: str
    requirement_type: str
    parent_requirement_id: str | None
    code_refs: tuple[str, ...]
    test_refs: tuple[str, ...]
    doc_refs: tuple[str, ...]
    implementation_status: str | None
    verification_method: str | None
    verification_notes: str | None
    gap_notes: str | None

    def to_view_model(self) -> dict[str, Any]:
        """Convert the entry into a JSON-serializable view model."""
        search_terms = " ".join(
            part
            for part in (
                self.requirement_id,
                self.title,
                self.requirement_type,
                self.parent_requirement_id or "",
                self.implementation_status or "",
                self.verification_method or "",
                " ".join(self.code_refs),
                " ".join(self.test_refs),
                " ".join(self.doc_refs),
                self.verification_notes or "",
                self.gap_notes or "",
            )
            if part
        ).lower()
        return {
            "requirement_id": self.requirement_id,
            "title": self.title,
            "requirement_type": self.requirement_type,
            "parent_requirement_id": self.parent_requirement_id,
            "implementation_status": self.implementation_status,
            "verification_method": self.verification_method,
            "verification_notes": self.verification_notes,
            "gap_notes": self.gap_notes,
            "code_refs": list(self.code_refs),
            "test_refs": list(self.test_refs),
            "doc_refs": list(self.doc_refs),
            "code_ref_count": len(self.code_refs),
            "test_ref_count": len(self.test_refs),
            "doc_ref_count": len(self.doc_refs),
            "search_text": search_terms,
        }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a self-contained HTML report for a requirements YAML trace file."
    )
    parser.add_argument(
        "requirements_path",
        help="Path to a machine-readable requirements YAML file.",
    )
    return parser.parse_args()


def _normalize_string_list(value: object, field_name: str, requirement_id: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise RequirementsVisualizationError(
            f"{requirement_id}: {field_name} must be a list when present."
        )
    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise RequirementsVisualizationError(
                f"{requirement_id}: {field_name} must contain only strings."
            )
        normalized.append(item)
    return tuple(normalized)


def _normalize_optional_string(
    value: object,
    field_name: str,
    requirement_id: str,
) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise RequirementsVisualizationError(
            f"{requirement_id}: {field_name} must be a string when present."
        )
    stripped = value.strip()
    return stripped or None


def load_requirements_trace(path: Path) -> list[RequirementEntry]:
    """Load and validate a requirements trace file."""
    if not path.exists():
        raise RequirementsVisualizationError(f"Requirements file does not exist: {path}")
    if not path.is_file():
        raise RequirementsVisualizationError(f"Requirements path is not a file: {path}")

    try:
        data = yaml.safe_load(path.read_text())
    except yaml.YAMLError as exc:
        raise RequirementsVisualizationError(f"Malformed YAML in {path}: {exc}") from exc

    if not isinstance(data, list):
        raise RequirementsVisualizationError("Requirements YAML must contain a top-level list.")

    seen_ids: set[str] = set()
    entries: list[RequirementEntry] = []
    for index, raw_entry in enumerate(data, start=1):
        if not isinstance(raw_entry, dict):
            raise RequirementsVisualizationError(
                f"Entry {index} must be a mapping of requirement fields."
            )

        requirement_id = raw_entry.get("requirement_id")
        title = raw_entry.get("title")
        requirement_type = raw_entry.get("requirement_type")
        missing_fields = [
            field_name
            for field_name, value in (
                ("requirement_id", requirement_id),
                ("title", title),
                ("requirement_type", requirement_type),
            )
            if not isinstance(value, str) or not value.strip()
        ]
        if missing_fields:
            raise RequirementsVisualizationError(
                f"Entry {index} is missing required field(s): {', '.join(missing_fields)}"
            )

        requirement_id = requirement_id.strip()
        title = title.strip()
        requirement_type = requirement_type.strip()

        if requirement_id in seen_ids:
            raise RequirementsVisualizationError(
                f"Duplicate requirement_id found: {requirement_id}"
            )
        seen_ids.add(requirement_id)

        entries.append(
            RequirementEntry(
                requirement_id=requirement_id,
                title=title,
                requirement_type=requirement_type,
                parent_requirement_id=_normalize_optional_string(
                    raw_entry.get("parent_requirement_id"),
                    "parent_requirement_id",
                    requirement_id,
                ),
                code_refs=_normalize_string_list(
                    raw_entry.get("code_refs"), "code_refs", requirement_id
                ),
                test_refs=_normalize_string_list(
                    raw_entry.get("test_refs"), "test_refs", requirement_id
                ),
                doc_refs=_normalize_string_list(
                    raw_entry.get("doc_refs"),
                    "doc_refs",
                    requirement_id,
                ),
                implementation_status=_normalize_optional_string(
                    raw_entry.get("implementation_status"),
                    "implementation_status",
                    requirement_id,
                ),
                verification_method=_normalize_optional_string(
                    raw_entry.get("verification_method"),
                    "verification_method",
                    requirement_id,
                ),
                verification_notes=_normalize_optional_string(
                    raw_entry.get("verification_notes"),
                    "verification_notes",
                    requirement_id,
                ),
                gap_notes=_normalize_optional_string(
                    raw_entry.get("gap_notes"),
                    "gap_notes",
                    requirement_id,
                ),
            )
        )
    return entries


def output_path_for(requirements_path: Path) -> Path:
    """Return the HTML output path derived from the YAML path."""
    return requirements_path.with_name(f"{requirements_path.stem}.visualization.html")


def _build_hierarchy(entries: list[RequirementEntry]) -> list[dict[str, Any]]:
    by_parent: dict[str | None, list[RequirementEntry]] = defaultdict(list)
    for entry in entries:
        parent_id = entry.parent_requirement_id if entry.parent_requirement_id else None
        by_parent[parent_id].append(entry)

    for siblings in by_parent.values():
        siblings.sort(key=lambda item: item.requirement_id)

    known_ids = {entry.requirement_id for entry in entries}

    def build_node(entry: RequirementEntry) -> dict[str, Any]:
        return {
            "requirement_id": entry.requirement_id,
            "title": entry.title,
            "requirement_type": entry.requirement_type,
            "implementation_status": entry.implementation_status,
            "verification_method": entry.verification_method,
            "children": [build_node(child) for child in by_parent.get(entry.requirement_id, ())],
        }

    root_entries = [
        entry
        for entry in entries
        if not entry.parent_requirement_id or entry.parent_requirement_id not in known_ids
    ]
    root_entries.sort(key=lambda item: item.requirement_id)
    return [build_node(entry) for entry in root_entries]


def _counter_items(counter: Counter[str]) -> list[dict[str, Any]]:
    return [
        {"label": label, "count": count}
        for label, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    ]


def build_view_model(entries: list[RequirementEntry], source_path: Path) -> dict[str, Any]:
    """Build the view model consumed by the static HTML page."""
    requirement_type_counts = Counter(entry.requirement_type for entry in entries)
    status_counts = Counter(entry.implementation_status or "unspecified" for entry in entries)
    verification_counts = Counter(entry.verification_method or "unspecified" for entry in entries)

    return {
        "source_path": str(source_path),
        "overview": {
            "total_requirements": len(entries),
            "acceptance_requirements": requirement_type_counts.get("acceptance", 0),
            "technical_requirements": requirement_type_counts.get("technical", 0),
            "implementation_status_counts": _counter_items(status_counts),
            "verification_method_counts": _counter_items(verification_counts),
        },
        "filter_options": {
            "requirement_types": sorted({entry.requirement_type for entry in entries}),
            "implementation_statuses": sorted(
                {entry.implementation_status or "unspecified" for entry in entries}
            ),
            "verification_methods": sorted(
                {entry.verification_method or "unspecified" for entry in entries}
            ),
        },
        "requirements": [entry.to_view_model() for entry in entries],
        "hierarchy": _build_hierarchy(entries),
    }


def render_html(entries: list[RequirementEntry], source_path: Path) -> str:
    """Render the HTML visualization as a standalone document."""
    view_model = build_view_model(entries, source_path)
    view_model_json = json.dumps(view_model)
    page_title = f"Requirements Visualization: {source_path.name}"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(page_title)}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f4efe7;
      --surface: #fffaf3;
      --surface-strong: #fff;
      --border: #d8cbb8;
      --text: #1f1b16;
      --muted: #6b6256;
      --accent: #1f6f78;
      --accent-soft: #d8edf0;
      --good: #2f6b3c;
      --warn: #9b6a19;
      --bad: #8f2d2d;
      --shadow: rgba(42, 29, 14, 0.08);
      font-family: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", serif;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background:
        radial-gradient(circle at top right, rgba(31, 111, 120, 0.14), transparent 28%),
        linear-gradient(180deg, #f7f1e8 0%, var(--bg) 100%);
      color: var(--text);
    }}
    main {{
      max-width: 1400px;
      margin: 0 auto;
      padding: 32px 20px 48px;
    }}
    header {{
      margin-bottom: 28px;
      padding: 28px;
      border: 1px solid var(--border);
      border-radius: 20px;
      background: linear-gradient(135deg, rgba(255, 250, 243, 0.98), rgba(248, 242, 233, 0.92));
      box-shadow: 0 18px 45px var(--shadow);
    }}
    h1, h2, h3 {{
      margin: 0;
      font-weight: 700;
      line-height: 1.15;
    }}
    h1 {{
      font-size: clamp(2rem, 4vw, 3.4rem);
      margin-bottom: 12px;
    }}
    h2 {{
      font-size: 1.35rem;
      margin-bottom: 14px;
    }}
    p {{
      margin: 0;
      line-height: 1.5;
    }}
    .subtitle {{
      color: var(--muted);
      max-width: 70ch;
    }}
    .section {{
      margin-top: 28px;
      padding: 24px;
      border: 1px solid var(--border);
      border-radius: 20px;
      background: rgba(255, 250, 243, 0.92);
      box-shadow: 0 14px 35px var(--shadow);
    }}
    .grid {{
      display: grid;
      gap: 16px;
    }}
    .overview-grid {{
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    }}
    .card {{
      padding: 18px;
      border: 1px solid var(--border);
      border-radius: 16px;
      background: var(--surface-strong);
    }}
    .metric-label {{
      display: block;
      font-size: 0.84rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--muted);
      margin-bottom: 8px;
    }}
    .metric-value {{
      font-size: 2rem;
      font-weight: 700;
    }}
    .stats-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 16px;
      margin-top: 16px;
    }}
    .stats-list {{
      display: grid;
      gap: 8px;
      margin-top: 12px;
    }}
    .stats-row {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      padding: 10px 12px;
      border-radius: 12px;
      background: var(--surface);
    }}
    .controls {{
      display: grid;
      grid-template-columns: minmax(220px, 2fr) repeat(3, minmax(160px, 1fr));
      gap: 12px;
      margin-bottom: 18px;
    }}
    input, select {{
      width: 100%;
      padding: 11px 12px;
      border: 1px solid var(--border);
      border-radius: 12px;
      background: #fffdf9;
      color: var(--text);
      font: inherit;
    }}
    .results-label {{
      color: var(--muted);
      margin-bottom: 10px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      border-spacing: 0;
      background: var(--surface-strong);
      border: 1px solid var(--border);
      border-radius: 16px;
      overflow: hidden;
    }}
    thead {{
      background: #efe5d7;
    }}
    th, td {{
      padding: 12px 14px;
      text-align: left;
      vertical-align: top;
      border-bottom: 1px solid #eadfce;
    }}
    tbody tr:last-child td {{
      border-bottom: 0;
    }}
    .requirement-cell {{
      min-width: 240px;
    }}
    .badge-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin-top: 8px;
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      padding: 3px 9px;
      border-radius: 999px;
      font-size: 0.78rem;
      font-weight: 700;
      letter-spacing: 0.02em;
      border: 1px solid transparent;
      background: #ece3d6;
      color: #54483c;
    }}
    .badge.type-acceptance {{
      background: #dcecf0;
      color: #174f56;
    }}
    .badge.type-technical {{
      background: #efe4cf;
      color: #6b4e15;
    }}
    .badge.status-implemented {{
      background: #ddeedd;
      color: var(--good);
    }}
    .badge.status-partial,
    .badge.status-partially-implemented {{
      background: #f6ecd4;
      color: var(--warn);
    }}
    .badge.status-not_implemented,
    .badge.status-not-implemented {{
      background: #f4dddd;
      color: var(--bad);
    }}
    .badge.status-optional_deployment {{
      background: #e8e0f2;
      color: #5a3d85;
    }}
    .badge.method {{
      background: var(--accent-soft);
      color: var(--accent);
    }}
    details {{
      border: 1px solid #eadfce;
      border-radius: 14px;
      background: #fffdf9;
      padding: 10px 12px;
    }}
    details > summary {{
      cursor: pointer;
      list-style: none;
      font-weight: 700;
    }}
    details > summary::-webkit-details-marker {{
      display: none;
    }}
    .detail-grid {{
      display: grid;
      gap: 14px;
      margin-top: 12px;
    }}
    .detail-block h3 {{
      font-size: 0.96rem;
      margin-bottom: 8px;
    }}
    .detail-block p {{
      color: var(--muted);
      white-space: pre-wrap;
    }}
    .ref-list {{
      margin: 0;
      padding-left: 18px;
      display: grid;
      gap: 4px;
      color: var(--muted);
      word-break: break-word;
    }}
    .tree {{
      display: grid;
      gap: 12px;
    }}
    .tree-node {{
      border-left: 2px solid #dacbb5;
      margin-left: 10px;
      padding-left: 16px;
    }}
    .tree-card {{
      padding: 14px 16px;
      border: 1px solid var(--border);
      border-radius: 14px;
      background: var(--surface-strong);
    }}
    .tree-title {{
      font-size: 1rem;
      font-weight: 700;
    }}
    .tree-card-button {{
      width: 100%;
      border: 0;
      padding: 0;
      background: transparent;
      color: inherit;
      text-align: left;
      cursor: pointer;
      font: inherit;
    }}
    .relationship-controls {{
      display: grid;
      grid-template-columns: minmax(260px, 1fr);
      gap: 12px;
      margin-bottom: 20px;
    }}
    .focus-tree-shell {{
      overflow-x: auto;
      padding-bottom: 8px;
    }}
    .focus-tree-canvas {{
      min-width: max-content;
      display: grid;
      justify-items: center;
      gap: 16px;
      padding: 8px 12px 20px;
    }}
    .ancestor-chain {{
      display: grid;
      justify-items: center;
      gap: 10px;
    }}
    .ancestor-step {{
      display: grid;
      justify-items: center;
      gap: 10px;
    }}
    .tree-connector-vertical {{
      width: 2px;
      height: 18px;
      background: #d4c3aa;
    }}
    .focus-stage {{
      display: grid;
      justify-items: center;
      gap: 10px;
    }}
    .focus-label {{
      font-size: 0.82rem;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--muted);
    }}
    .relationship-node {{
      min-width: 240px;
      max-width: 340px;
      padding: 14px 16px;
      border: 1px solid var(--border);
      border-radius: 16px;
      background: var(--surface-strong);
      box-shadow: 0 10px 24px var(--shadow);
      text-align: left;
    }}
    .relationship-node:hover {{
      border-color: #b59d78;
      transform: translateY(-1px);
    }}
    .relationship-node.is-focus {{
      min-width: 300px;
      border-width: 2px;
      border-color: var(--accent);
      background: linear-gradient(180deg, #fdfcf8, #eef8f9);
    }}
    .relationship-node.is-path {{
      background: #faf4ea;
    }}
    .relationship-node-title {{
      display: block;
      font-size: 1rem;
      font-weight: 700;
      line-height: 1.3;
    }}
    .relationship-node-subtitle {{
      display: block;
      margin-top: 4px;
      color: var(--muted);
      font-size: 0.92rem;
      line-height: 1.4;
    }}
    .descendant-tree,
    .descendant-tree ul {{
      display: flex;
      justify-content: center;
      align-items: flex-start;
      gap: 16px;
      margin: 0;
      padding: 0;
      list-style: none;
      position: relative;
    }}
    .descendant-tree ul {{
      padding-top: 24px;
    }}
    .descendant-tree ul::before {{
      content: "";
      position: absolute;
      top: 0;
      left: 50%;
      width: 2px;
      height: 18px;
      background: #d4c3aa;
      transform: translateX(-50%);
    }}
    .descendant-tree li {{
      position: relative;
      display: grid;
      justify-items: center;
      gap: 10px;
      padding: 0 8px;
    }}
    .descendant-tree li::before,
    .descendant-tree li::after {{
      content: "";
      position: absolute;
      top: 0;
      width: 50%;
      height: 2px;
      background: #d4c3aa;
    }}
    .descendant-tree li::before {{
      right: 50%;
    }}
    .descendant-tree li::after {{
      left: 50%;
    }}
    .descendant-tree li:only-child::before,
    .descendant-tree li:only-child::after {{
      display: none;
    }}
    .descendant-tree li:first-child::before {{
      display: none;
    }}
    .descendant-tree li:last-child::after {{
      display: none;
    }}
    .descendant-tree-root {{
      padding-top: 0;
    }}
    .descendant-tree-root::before,
    .descendant-tree-root > li::before,
    .descendant-tree-root > li::after {{
      display: none;
    }}
    .empty-tree-state {{
      padding: 18px 20px;
      border: 1px dashed var(--border);
      border-radius: 14px;
      color: var(--muted);
      background: rgba(255, 253, 249, 0.75);
    }}
    .muted {{
      color: var(--muted);
    }}
    .hidden {{
      display: none !important;
    }}
    @media (max-width: 900px) {{
      .controls {{
        grid-template-columns: 1fr;
      }}
      table, thead, tbody, tr, th, td {{
        display: block;
      }}
      thead {{
        display: none;
      }}
      tbody tr {{
        margin-bottom: 16px;
        border: 1px solid var(--border);
        border-radius: 16px;
        background: var(--surface-strong);
        overflow: hidden;
      }}
      td {{
        border-bottom: 1px solid #eadfce;
      }}
      tbody tr td:last-child {{
        border-bottom: 0;
      }}
      td::before {{
        content: attr(data-label);
        display: block;
        margin-bottom: 6px;
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: var(--muted);
      }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>Requirements Trace Visualizer</h1>
      <p class="subtitle">
        Self-contained HTML report for
        <strong>{escape(str(source_path))}</strong>. The page includes summary metrics,
        requirement hierarchy, and client-side search and filtering over trace metadata.
      </p>
    </header>

    <section class="section">
      <h2>Overview</h2>
      <div class="grid overview-grid" id="overview-cards"></div>
      <div class="stats-grid">
        <div class="card">
          <h2>Implementation Status</h2>
          <div class="stats-list" id="status-counts"></div>
        </div>
        <div class="card">
          <h2>Verification Methods</h2>
          <div class="stats-list" id="verification-counts"></div>
        </div>
      </div>
    </section>

    <section class="section">
      <h2>Hierarchy</h2>
      <p class="results-label">
        Parent-child structure derived from <code>parent_requirement_id</code>.
      </p>
      <div class="tree" id="hierarchy-root"></div>
    </section>

    <section class="section">
      <h2>Relationship Tree</h2>
      <p class="results-label">
        Center any requirement to see parent nodes flowing in above it and child
        requirements branching out below it.
      </p>
      <div class="relationship-controls">
        <select id="focus-requirement-select"></select>
      </div>
      <div class="focus-tree-shell">
        <div class="focus-tree-canvas" id="focus-tree-root"></div>
      </div>
    </section>

    <section class="section">
      <h2>Search and Filter</h2>
      <div class="controls">
        <input
          id="search-input"
          type="search"
          placeholder="Search by ID, title, notes, or references"
        >
        <select id="type-filter"></select>
        <select id="status-filter"></select>
        <select id="verification-filter"></select>
      </div>
      <p class="results-label" id="results-label"></p>
      <table>
        <thead>
          <tr>
            <th>Requirement</th>
            <th>Parent</th>
            <th>Status</th>
            <th>Verification</th>
            <th>Trace Counts</th>
            <th>Details</th>
          </tr>
        </thead>
        <tbody id="requirements-table"></tbody>
      </table>
    </section>
  </main>

  <script>
    const data = {view_model_json};
    const requirementsById = new Map(
      data.requirements.map((entry) => [entry.requirement_id, entry])
    );
    const childrenByParentId = new Map();
    const focusState = {{
      requirementId: data.requirements[0]?.requirement_id || null,
    }};

    data.requirements.forEach((entry) => {{
      const parentId = entry.parent_requirement_id || "__root__";
      if (!childrenByParentId.has(parentId)) {{
        childrenByParentId.set(parentId, []);
      }}
      childrenByParentId.get(parentId).push(entry.requirement_id);
    }});

    childrenByParentId.forEach((childIds) => {{
      childIds.sort((leftId, rightId) => leftId.localeCompare(rightId));
    }});

    const createBadge = (label, className = "") => {{
      const span = document.createElement("span");
      span.className = `badge ${{className}}`.trim();
      span.textContent = label;
      return span;
    }};

    const createRequirementNode = (entry, variant = "") => {{
      const button = document.createElement("button");
      button.type = "button";
      button.className = `relationship-node ${{variant}}`.trim();
      button.dataset.requirementId = entry.requirement_id;
      button.addEventListener("click", () => setFocusRequirement(entry.requirement_id));

      const title = document.createElement("span");
      title.className = "relationship-node-title";
      title.textContent = entry.requirement_id;
      button.appendChild(title);

      const subtitle = document.createElement("span");
      subtitle.className = "relationship-node-subtitle";
      subtitle.textContent = entry.title;
      button.appendChild(subtitle);

      const badges = document.createElement("div");
      badges.className = "badge-row";
      badges.appendChild(
        createBadge(entry.requirement_type, `type-${{entry.requirement_type}}`)
      );
      badges.appendChild(
        createBadge(
          entry.implementation_status || "unspecified",
          `status-${{(entry.implementation_status || "unspecified").replaceAll(" ", "-")}}`
        )
      );
      badges.appendChild(
        createBadge(entry.verification_method || "unspecified", "method")
      );
      button.appendChild(badges);
      return button;
    }};

    const populateOverview = () => {{
      const cards = [
        ["Total requirements", data.overview.total_requirements],
        ["Acceptance requirements", data.overview.acceptance_requirements],
        ["Technical requirements", data.overview.technical_requirements],
      ];
      const overviewRoot = document.getElementById("overview-cards");
      cards.forEach(([label, value]) => {{
        const card = document.createElement("article");
        card.className = "card";
        card.innerHTML =
          `<span class="metric-label">${{label}}</span>` +
          `<div class="metric-value">${{value}}</div>`;
        overviewRoot.appendChild(card);
      }});

      const fillCounts = (rootId, items) => {{
        const root = document.getElementById(rootId);
        items.forEach((item) => {{
          const row = document.createElement("div");
          row.className = "stats-row";
          row.innerHTML = `<span>${{item.label}}</span><strong>${{item.count}}</strong>`;
          root.appendChild(row);
        }});
      }};

      fillCounts("status-counts", data.overview.implementation_status_counts);
      fillCounts("verification-counts", data.overview.verification_method_counts);
    }};

    const renderTreeNode = (node, container) => {{
      const wrapper = document.createElement("div");
      wrapper.className = "tree-node";

      const card = document.createElement("div");
      card.className = "tree-card";
      const cardButton = document.createElement("button");
      cardButton.type = "button";
      cardButton.className = "tree-card-button";
      cardButton.dataset.requirementId = node.requirement_id;
      cardButton.addEventListener("click", () => setFocusRequirement(node.requirement_id));

      const title = document.createElement("div");
      title.className = "tree-title";
      title.textContent = `${{node.requirement_id}}: ${{node.title}}`;
      cardButton.appendChild(title);

      const badges = document.createElement("div");
      badges.className = "badge-row";
      badges.appendChild(
        createBadge(node.requirement_type, `type-${{node.requirement_type}}`)
      );
      if (node.implementation_status) {{
        const statusClass =
          `status-${{node.implementation_status.replaceAll(" ", "-")}}`;
        badges.appendChild(
          createBadge(node.implementation_status, statusClass)
        );
      }}
      if (node.verification_method) {{
        badges.appendChild(createBadge(node.verification_method, "method"));
      }}
      cardButton.appendChild(badges);
      card.appendChild(cardButton);
      wrapper.appendChild(card);

      if (node.children.length) {{
        const childContainer = document.createElement("div");
        childContainer.className = "tree";
        node.children.forEach((child) => renderTreeNode(child, childContainer));
        wrapper.appendChild(childContainer);
      }}

      container.appendChild(wrapper);
    }};

    const populateHierarchy = () => {{
      const root = document.getElementById("hierarchy-root");
      data.hierarchy.forEach((node) => renderTreeNode(node, root));
    }};

    const getAncestorEntries = (requirementId) => {{
      const ancestors = [];
      let current = requirementsById.get(requirementId);
      const visited = new Set();
      while (current?.parent_requirement_id) {{
        const parentId = current.parent_requirement_id;
        if (visited.has(parentId) || !requirementsById.has(parentId)) {{
          break;
        }}
        const parent = requirementsById.get(parentId);
        ancestors.unshift(parent);
        visited.add(parentId);
        current = parent;
      }}
      return ancestors;
    }};

    const renderDescendantBranch = (requirementId) => {{
      const branchItem = document.createElement("li");
      const entry = requirementsById.get(requirementId);
      branchItem.appendChild(createRequirementNode(entry));

      const childIds = childrenByParentId.get(requirementId) || [];
      if (childIds.length) {{
        const childList = document.createElement("ul");
        childIds.forEach((childId) => {{
          childList.appendChild(renderDescendantBranch(childId));
        }});
        branchItem.appendChild(childList);
      }}
      return branchItem;
    }};

    const renderFocusTree = () => {{
      const root = document.getElementById("focus-tree-root");
      root.innerHTML = "";
      if (!focusState.requirementId || !requirementsById.has(focusState.requirementId)) {{
        const emptyState = document.createElement("div");
        emptyState.className = "empty-tree-state";
        emptyState.textContent = "No requirement is available to center in the tree.";
        root.appendChild(emptyState);
        return;
      }}

      const focusEntry = requirementsById.get(focusState.requirementId);
      const ancestors = getAncestorEntries(focusEntry.requirement_id);
      if (ancestors.length) {{
        const ancestorChain = document.createElement("div");
        ancestorChain.className = "ancestor-chain";
        ancestors.forEach((entry, index) => {{
          if (index > 0) {{
            const connector = document.createElement("div");
            connector.className = "tree-connector-vertical";
            ancestorChain.appendChild(connector);
          }}
          const step = document.createElement("div");
          step.className = "ancestor-step";
          step.appendChild(createRequirementNode(entry, "is-path"));
          ancestorChain.appendChild(step);
        }});
        const connector = document.createElement("div");
        connector.className = "tree-connector-vertical";
        ancestorChain.appendChild(connector);
        root.appendChild(ancestorChain);
      }}

      const focusStage = document.createElement("div");
      focusStage.className = "focus-stage";
      const focusLabel = document.createElement("div");
      focusLabel.className = "focus-label";
      focusLabel.textContent = "Focused Requirement";
      focusStage.appendChild(focusLabel);
      focusStage.appendChild(createRequirementNode(focusEntry, "is-focus"));
      root.appendChild(focusStage);

      const childIds = childrenByParentId.get(focusEntry.requirement_id) || [];
      if (childIds.length) {{
        const connector = document.createElement("div");
        connector.className = "tree-connector-vertical";
        root.appendChild(connector);

        const descendantList = document.createElement("ul");
        descendantList.className = "descendant-tree descendant-tree-root";
        childIds.forEach((childId) => {{
          descendantList.appendChild(renderDescendantBranch(childId));
        }});
        root.appendChild(descendantList);
      }}
    }};

    const populateFocusSelect = () => {{
      const select = document.getElementById("focus-requirement-select");
      data.requirements.forEach((entry) => {{
        const option = document.createElement("option");
        option.value = entry.requirement_id;
        option.textContent = `${{entry.requirement_id}}: ${{entry.title}}`;
        select.appendChild(option);
      }});
      if (focusState.requirementId) {{
        select.value = focusState.requirementId;
      }}
      select.addEventListener("change", (event) => {{
        setFocusRequirement(event.target.value);
      }});
    }};

    const setFocusRequirement = (requirementId) => {{
      if (!requirementsById.has(requirementId)) {{
        return;
      }}
      focusState.requirementId = requirementId;
      const select = document.getElementById("focus-requirement-select");
      if (select && select.value !== requirementId) {{
        select.value = requirementId;
      }}
      renderFocusTree();
    }};

    const buildSelectOptions = (elementId, label, options) => {{
      const select = document.getElementById(elementId);
      const allOption = document.createElement("option");
      allOption.value = "";
      allOption.textContent = `All ${{label}}`;
      select.appendChild(allOption);
      options.forEach((value) => {{
        const option = document.createElement("option");
        option.value = value;
        option.textContent = value;
        select.appendChild(option);
      }});
      return select;
    }};

    const renderReferenceList = (items) => {{
      if (!items.length) {{
        return "<p class=\\"muted\\">None</p>";
      }}
      return `<ul class="ref-list">${{items.map((item) => `<li>${{item}}</li>`).join("")}}</ul>`;
    }};

    const createDetailBlock = (heading, content) => {{
      return `
        <section class="detail-block">
          <h3>${{heading}}</h3>
          ${{content}}
        </section>
      `;
    }};

    const createRow = (entry) => {{
      const row = document.createElement("tr");
      row.dataset.type = entry.requirement_type;
      row.dataset.status = entry.implementation_status || "unspecified";
      row.dataset.verification = entry.verification_method || "unspecified";
      row.dataset.search = entry.search_text;

      const detailContent = `
        <div class="detail-grid">
          ${{createDetailBlock("Title", `<p>${{entry.title}}</p>`)}}
          ${{
            createDetailBlock(
              "Parent Requirement",
              `<p>${{entry.parent_requirement_id || "None"}}</p>`
            )
          }}
          ${{
            createDetailBlock(
              "Verification Notes",
              `<p>${{entry.verification_notes || "None"}}</p>`
            )
          }}
          ${{createDetailBlock("Gap Notes", `<p>${{entry.gap_notes || "None"}}</p>`)}}
          ${{createDetailBlock("Code References", renderReferenceList(entry.code_refs))}}
          ${{createDetailBlock("Test References", renderReferenceList(entry.test_refs))}}
          ${{
            createDetailBlock(
              "Documentation References",
              renderReferenceList(entry.doc_refs)
            )
          }}
        </div>
      `;

      const statusLabel = entry.implementation_status || "unspecified";
      const statusClass = statusLabel.replaceAll(" ", "-");
      const verificationLabel = entry.verification_method || "unspecified";
      const badges = `
        <div class="badge-row">
          <span class="badge type-${{entry.requirement_type}}">${{entry.requirement_type}}</span>
          <span class="badge status-${{statusClass}}">${{statusLabel}}</span>
          <span class="badge method">${{verificationLabel}}</span>
        </div>
      `;

      row.innerHTML = `
        <td data-label="Requirement" class="requirement-cell">
          <strong>${{entry.requirement_id}}</strong><br>
          <span>${{entry.title}}</span>
          ${{badges}}
        </td>
        <td data-label="Parent">${{entry.parent_requirement_id || "None"}}</td>
        <td data-label="Status">${{entry.implementation_status || "unspecified"}}</td>
        <td data-label="Verification">${{entry.verification_method || "unspecified"}}</td>
        <td data-label="Trace Counts">
          code: <strong>${{entry.code_ref_count}}</strong><br>
          tests: <strong>${{entry.test_ref_count}}</strong><br>
          docs: <strong>${{entry.doc_ref_count}}</strong>
        </td>
        <td data-label="Details">
          <details>
            <summary>Expand</summary>
            ${{detailContent}}
          </details>
        </td>
      `;
      return row;
    }};

    const populateTable = () => {{
      const table = document.getElementById("requirements-table");
      data.requirements.forEach((entry) => {{
        table.appendChild(createRow(entry));
      }});
    }};

    const applyFilters = () => {{
      const searchValue = document.getElementById("search-input").value.trim().toLowerCase();
      const typeValue = document.getElementById("type-filter").value;
      const statusValue = document.getElementById("status-filter").value;
      const verificationValue = document.getElementById("verification-filter").value;
      const rows = Array.from(document.querySelectorAll("#requirements-table tr"));
      let visibleCount = 0;

      rows.forEach((row) => {{
        const matchesSearch = !searchValue || row.dataset.search.includes(searchValue);
        const matchesType = !typeValue || row.dataset.type === typeValue;
        const matchesStatus = !statusValue || row.dataset.status === statusValue;
        const matchesVerification =
          !verificationValue || row.dataset.verification === verificationValue;
        const visible = matchesSearch && matchesType && matchesStatus && matchesVerification;
        row.classList.toggle("hidden", !visible);
        if (visible) {{
          visibleCount += 1;
        }}
      }});

      document.getElementById("results-label").textContent =
        `${{visibleCount}} of ${{data.requirements.length}} requirement entries shown`;
    }};

    populateOverview();
    populateHierarchy();
    populateFocusSelect();
    renderFocusTree();
    populateTable();
    buildSelectOptions("type-filter", "types", data.filter_options.requirement_types);
    buildSelectOptions(
      "status-filter",
      "statuses",
      data.filter_options.implementation_statuses
    );
    buildSelectOptions(
      "verification-filter",
      "verification methods",
      data.filter_options.verification_methods
    );
    [
      "search-input",
      "type-filter",
      "status-filter",
      "verification-filter",
    ].forEach((elementId) => {{
      document.getElementById(elementId).addEventListener("input", applyFilters);
      document.getElementById(elementId).addEventListener("change", applyFilters);
    }});
    applyFilters();
  </script>
</body>
</html>
"""


def main() -> int:
    """Generate the HTML visualization and print its output path."""
    args = _parse_args()
    requirements_path = Path(args.requirements_path)
    try:
        entries = load_requirements_trace(requirements_path)
        output_path = output_path_for(requirements_path)
        output_path.write_text(render_html(entries, requirements_path))
    except RequirementsVisualizationError as exc:
        print(exc, file=sys.stderr)
        return 1

    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
