# AGENTS.md (Repository Agent Guide)

This repository implements a single-user personal budgeting app. Agent work must stay
inside PRD scope and maintain strict requirement traceability.

## 1) Authority and scope
- The PRD is the source of truth. Do not implement features outside it unless explicitly authorized.
- Preferred PRD path: `docs/product-requirements-document.md`.
- Current milestone plan: `docs/plan.md`.
- This file defines policy. `CLAUDE.md` provides project context and operational examples.

## 2) Requirement IDs and decomposition
- Use stable requirement IDs from the PRD (for example `SYS-003`, `FUNC-ACCT-002`, `SEC-CRY-001`).
- Preserve parent-child requirement relationships when adding derived requirements.
- Keep requirements small. One requirement should express one "shall" behavior.

## 3) Mandatory traceability
Maintain bidirectional links:
- Requirements <-> production code
- Production code <-> tests
- Requirements <-> tests

### 3.1 Requirement tags in code
- Every production module/class/function implementing requirement behavior must include `REQ:` tags.
- Format: `REQ: <REQ-ID>` or `REQ: <REQ-ID1>, <REQ-ID2>`.
- Preferred placement order:
  1. Module header comment
  2. Public class/function docstring
  3. Inline comment next to narrow-scope logic

### 3.2 Requirement tags in tests
- Every requirement must be covered by at least one automated test.
- Use the same `REQ:` tag format in tests.
- If a requirement is not currently testable, add a tracked `SKIP`/`XFAIL` test stub with rationale and linked issue/task.

### 3.3 Machine-readable trace index
- Keep `trace/requirements.yml` up to date for every requirement-impacting change.
- Each entry should include:
  - `requirement_id`, `title`
  - `parent_requirement_id` (optional)
  - `code_refs` (path + symbol/anchor)
  - `test_refs` (path + test name)
  - `doc_refs` (design docs explaining implementation)
- New requirement-related code without trace entries is not acceptable.

## 4) Design documentation
For non-trivial changes (new modules/workflows/security controls/storage model):
- Update or create docs under `docs/design/`.
- Use Markdown and Mermaid diagrams.
- Include requirement links (for example `Requirements: SYS-003, SEC-CRY-001`).

Recommended doc sections:
- Problem statement (linked requirement IDs)
- Architecture overview
- Data model changes
- API/interface changes
- Security considerations
- Tradeoffs/alternatives
- Testing strategy and coverage mapping
- Rollout/migration notes

## 5) Security baseline
- Never log secrets (tokens, credentials, keys, full account numbers).
- Keep provider secrets server-side only; never embed in client artifacts.
- Use vetted cryptographic libraries and authenticated encryption where required.
- Centralize secret and crypto handling in dedicated security modules.
- Validate/sanitize user input and use parameterized queries.
- Enforce least privilege for files/endpoints and keep dependency hygiene (pin + vulnerability checks).

## 6) Code quality and architecture boundaries
- Keep code DRY and composable; refactor repeated logic into shared modules.
- Preserve clear boundaries:
  - Domain logic (budgets, categorization, reports)
  - Infrastructure (Plaid, persistence, encryption, logging)
  - UI/API layer (presentation + input validation)

## 7) Definition of done
Before submission:
1. Implementation matches PRD requirements (no scope creep).
2. `REQ:` tags are present in production code and tests.
3. `trace/requirements.yml` is updated and consistent.
4. Design docs are updated/created when needed.
5. Lint, tests, and build checks pass. Exception: for purely non-functional changes (for example comments, TODOs, docstrings, or docs-only edits with no logic/config/behavior impact), run lint only; tests/build may be skipped.
    - Always run commands using virtual environment
    - Never install packages in system or user scope 
6. Security checks (if configured) pass.
7. No secrets appear in logs.

Python check commands:
- `nox -s lint` (or `python3 -m ruff check godzilla_core`)
- `nox -s tests` (or `python3 -m pytest`)
- `nox -s build` (or `python3 -m build --wheel`)

## 8) Agent workflow checklist
1. Identify impacted requirement IDs in the PRD.
2. Plan implementation and required design doc updates.
3. Implement code with `REQ:` tags.
4. Add/update tests with `REQ:` tags.
5. Update `trace/requirements.yml`.
6. Run required checks.
7. Summarize: requirements touched, files changed, tests changed, docs changed, commands/results.
8. Make a local commit following Conventional Commits convention using configured git user and e-mail.

## 9) Repository conventions
Ensure these paths exist and stay current:
- `docs/design/`
- `trace/`
- `trace/requirements.yml`
