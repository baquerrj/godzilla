"""Validate requirement traceability artifacts for the layered verification model.

REQ: ACC-SYS-001, ACC-SYS-003
"""

from __future__ import annotations

import ast
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import yaml

REQUIREMENT_ID_RE = re.compile(r"\b(?:ACC|TECH)-[A-Z0-9-]+\b")
REQ_TAG_RE = re.compile(r"REQ:\s*([A-Z0-9,\- ]+)")
AUTOMATED_TRACES_COLUMN = 6
VALID_REQUIREMENT_TYPES = {"acceptance", "technical"}
VALID_IMPLEMENTATION_STATUSES = {
    "implemented",
    "partial",
    "not_implemented",
    "optional_deployment",
}
VALID_VERIFICATION_METHODS = {
    "acceptance",
    "unit",
    "integration",
    "component",
    "system",
    "manual",
    "static_analysis",
    "security_review",
}
TRACE_STUB_PREFIXES = ("skip: ", "xfail: ")
CODE_FILE_SUFFIXES = {".py", ".ts", ".tsx", ".rs"}
EXCLUDED_DIR_NAMES = {
    ".git",
    ".nox",
    "venv",
    "node_modules",
    "build",
    ".mypy_cache",
    ".pytest_cache",
}


@dataclass(frozen=True)
class MarkdownRequirement:
    """Requirement row extracted from the canonical requirements markdown."""

    requirement_id: str
    automated_traces: tuple[str, ...]


class ValidationError(RuntimeError):
    """Raised when the traceability audit finds invalid references."""


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_requirements_markdown(path: Path) -> dict[str, MarkdownRequirement]:
    requirements: dict[str, MarkdownRequirement] = {}
    for line in path.read_text().splitlines():
        if not line.startswith("| "):
            continue
        cells = [cell.strip() for cell in line.split("|")[1:-1]]
        if not cells:
            continue
        requirement_id = cells[0]
        if not REQUIREMENT_ID_RE.fullmatch(requirement_id):
            continue
        automated_traces = (
            tuple(
                trace.strip()
                for trace in cells[AUTOMATED_TRACES_COLUMN].split(";")
                if trace.strip()
            )
            if len(cells) > AUTOMATED_TRACES_COLUMN
            else ()
        )
        requirements[requirement_id] = MarkdownRequirement(
            requirement_id=requirement_id,
            automated_traces=automated_traces,
        )
    return requirements


def _load_requirements_trace(path: Path) -> list[dict[str, object]]:
    entries = yaml.safe_load(path.read_text())
    if not isinstance(entries, list):
        raise ValidationError("trace/requirements.yml must contain a list of requirement entries.")
    return entries


def _strip_trace_prefix(reference: str) -> str:
    normalized = reference
    for prefix in TRACE_STUB_PREFIXES:
        if normalized.startswith(prefix):
            return normalized[len(prefix) :]
    return normalized


def _split_reference(reference: str) -> tuple[Path, str | None]:
    normalized = _strip_trace_prefix(reference)
    if ":" not in normalized:
        return Path(normalized), None
    path_text, symbol = normalized.split(":", 1)
    return Path(path_text), symbol


def _load_python_symbols(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    symbols: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            symbols.add(node.name)
        elif isinstance(node, ast.ClassDef):
            symbols.add(node.name)
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    symbols.add(f"{node.name}.{child.name}")
    return symbols


def _reference_exists(root: Path, reference: str) -> bool:
    rel_path, symbol = _split_reference(reference)
    path = root / rel_path
    if not path.exists():
        return False
    if symbol is None:
        return True
    text = path.read_text()
    if path.suffix == ".py":
        symbols = _load_python_symbols(path)
        if symbol in symbols:
            return True
        if "." not in symbol and any(candidate.endswith(f".{symbol}") for candidate in symbols):
            return True
    if path.suffix in {".ts", ".tsx"} and "." in symbol:
        owner_name, member_name = symbol.split(".", 1)
        has_owner = re.search(
            rf"(?:class|const|let|var)\s+{re.escape(owner_name)}\b",
            text,
        )
        has_member = re.search(rf"\b{re.escape(member_name)}\s*\(", text)
        if has_owner and has_member:
            return True
    return symbol in text


def _iter_req_ids_from_file(path: Path) -> Iterable[str]:
    if path.suffix not in CODE_FILE_SUFFIXES:
        return ()
    text = path.read_text()
    ids: list[str] = []
    for match in REQ_TAG_RE.finditer(text):
        ids.extend(
            requirement_id
            for requirement_id in (item.strip() for item in match.group(1).split(","))
            if requirement_id
        )
    return ids


def _validate_metadata(
    requirement_id: str,
    entry: dict[str, object],
    trace_lookup: dict[str, dict[str, object]],
) -> list[str]:
    errors: list[str] = []
    requirement_type = entry.get("requirement_type")
    if requirement_type not in VALID_REQUIREMENT_TYPES:
        errors.append(f"{requirement_id}: invalid requirement_type {requirement_type!r}")

    implementation_status = entry.get("implementation_status")
    if implementation_status not in VALID_IMPLEMENTATION_STATUSES:
        errors.append(f"{requirement_id}: invalid implementation_status {implementation_status!r}")

    verification_method = entry.get("verification_method")
    if verification_method not in VALID_VERIFICATION_METHODS:
        errors.append(f"{requirement_id}: invalid verification_method {verification_method!r}")

    parent_requirement_id = entry.get("parent_requirement_id")
    if parent_requirement_id and parent_requirement_id not in trace_lookup:
        errors.append(
            f"{requirement_id}: parent_requirement_id {parent_requirement_id!r} does not exist"
        )

    verification_notes = entry.get("verification_notes")
    if not isinstance(verification_notes, str) or not verification_notes.strip():
        errors.append(f"{requirement_id}: verification_notes must be a non-empty string")

    gap_notes = entry.get("gap_notes")
    requires_gap_notes = implementation_status != "implemented" or verification_method in {
        "manual",
        "static_analysis",
        "security_review",
        "system",
    }
    if requires_gap_notes and (not isinstance(gap_notes, str) or not gap_notes.strip()):
        errors.append(
            f"{requirement_id}: gap_notes are required for status/method "
            f"{implementation_status}/{verification_method}"
        )

    return errors


def _validate_references(
    root: Path,
    requirement_id: str,
    entry: dict[str, object],
) -> list[str]:
    errors: list[str] = []
    for field_name in ("code_refs", "test_refs", "doc_refs"):
        field_value = entry.get(field_name)
        if not isinstance(field_value, list) or not field_value:
            errors.append(f"{requirement_id}: {field_name} must be a non-empty list")
            continue
        for reference in field_value:
            if not isinstance(reference, str):
                errors.append(
                    f"{requirement_id}: {field_name} contains non-string reference "
                    f"{reference!r}"
                )
                continue
            if field_name == "doc_refs":
                doc_path, _ = _split_reference(reference)
                if not (root / doc_path).exists():
                    errors.append(
                        f"{requirement_id}: {field_name} reference does not resolve: "
                        f"{reference}"
                    )
                continue
            if not _reference_exists(root, reference):
                errors.append(
                    f"{requirement_id}: {field_name} reference does not resolve: " f"{reference}"
                )
    return errors


def _validate_markdown_traces(
    root: Path,
    requirement_id: str,
    markdown_entry: MarkdownRequirement | None,
) -> list[str]:
    errors: list[str] = []
    if markdown_entry is None:
        return errors
    for reference in markdown_entry.automated_traces:
        if not _reference_exists(root, reference):
            errors.append(
                f"{requirement_id}: requirements.md automated trace does not resolve: "
                f"{reference}"
            )
    return errors


def _validate_trace_entries(
    root: Path,
    markdown_requirements: dict[str, MarkdownRequirement],
    trace_entries: list[dict[str, object]],
) -> list[str]:
    errors: list[str] = []
    trace_ids = [str(entry.get("requirement_id", "")) for entry in trace_entries]
    markdown_ids = list(markdown_requirements)

    missing_from_trace = sorted(set(markdown_ids) - set(trace_ids))
    missing_from_markdown = sorted(set(trace_ids) - set(markdown_ids))
    if missing_from_trace:
        errors.append(f"Missing trace entries for requirement IDs: {', '.join(missing_from_trace)}")
    if missing_from_markdown:
        errors.append(
            "Trace index contains IDs not present in requirements.md: "
            f"{', '.join(missing_from_markdown)}"
        )

    trace_lookup = {
        entry["requirement_id"]: entry for entry in trace_entries if "requirement_id" in entry
    }
    for requirement_id, entry in trace_lookup.items():
        errors.extend(_validate_metadata(requirement_id, entry, trace_lookup))
        errors.extend(_validate_references(root, requirement_id, entry))
        errors.extend(
            _validate_markdown_traces(
                root, requirement_id, markdown_requirements.get(requirement_id)
            )
        )

    return errors


def _validate_req_tags(root: Path, valid_ids: set[str]) -> list[str]:
    errors: list[str] = []
    for path in root.rglob("*"):
        if (
            not path.is_file()
            or any(part in EXCLUDED_DIR_NAMES for part in path.parts)
            or path.suffix not in CODE_FILE_SUFFIXES
        ):
            continue
        for requirement_id in _iter_req_ids_from_file(path):
            if requirement_id not in valid_ids:
                errors.append(f"{path}: unknown REQ tag {requirement_id}")
    return errors


def main() -> int:
    """Run the traceability audit and return a process exit code."""
    root = _repo_root()
    requirements_md = root / "docs/requirements/requirements.md"
    requirements_yml = root / "trace/requirements.yml"

    markdown_requirements = _load_requirements_markdown(requirements_md)
    trace_entries = _load_requirements_trace(requirements_yml)

    errors = _validate_trace_entries(root, markdown_requirements, trace_entries)
    valid_ids = {entry["requirement_id"] for entry in trace_entries if "requirement_id" in entry}
    errors.extend(_validate_req_tags(root, valid_ids))

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    method_counts: dict[str, int] = {}
    for entry in trace_entries:
        method = str(entry["verification_method"])
        method_counts[method] = method_counts.get(method, 0) + 1

    print(f"Validated {len(trace_entries)} requirements.")
    print("Verification methods:")
    for method in sorted(method_counts):
        print(f"  {method}: {method_counts[method]}")
    print("REQ tags: ok")
    print("References: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
