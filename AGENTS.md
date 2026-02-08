# AGENTS.md (Codex Guidance)

This repository implements a single-user personal budgeting app. Development must strictly adhere to the Product Requirements Document (PRD) and maintain robust bidirectional traceability among requirements, production code, and tests.

## 1 Non-negotiables
1. Requirements are the source of truth. Do not implement features outside the PRD unless explicitly authorized.
2. Every change must maintain bidirectional traceability:
   - Requirements ↔ Production code
   - Production code ↔ Unit tests and component tests
   - Requirements ↔ Unit tests and component tests
3. Secure coding practices are mandatory for all changes involving financial data, secrets, and storage.
4. Keep the codebase efficient and DRY: minimize redundancy; refactor into common modules when appropriate.
5. Design documentation must exist and be updated with each change. Docs are Markdown; diagrams use Mermaid.
6. All unit and component tests must pass locally/CI before submission.
7. All linters must pass locally/CI before submission.

## 2 Source documents and canonical IDs
- PRD: `product-requirements-document.md` (or the repo’s current PRD path).
- Requirements are identified by stable IDs (e.g., `SYS-003`, `FUNC-ACCT-002`, `SEC-CRY-001`).
- A requirement may have a parent requirement ID; derived requirements must preserve this relationship.
- Each requirement contains exactly one "shall" statement:
  - Requirements are kept as small as possible
  - Decompose complex requirements into derived and corresponding system, sub-system, and component requirements
  - When a requirement starts describing chained or complex behavior, that is a sign that the requirement be decomposed into smaller chunks

## 3 Traceability rules (strict)
### 3.1 Requirement-to-code
- Every production module/class/function implementing requirement behavior MUST reference the corresponding requirement ID(s).
- Use a consistent in-code tag format:
  - `REQ: <REQ-ID>` (single) or `REQ: <REQ-ID1>, <REQ-ID2>` (multiple)
- Place tags in one of the following, in order of preference:
  1. Module header comment
  2. Public function/class docstring comment
  3. Inline comment adjacent to the relevant logic (only when narrow-scope)

### 3.2 Requirement-to-tests
- Every requirement MUST be covered by at least one automated test:
  - Unit tests for logic-level behavior
  - Component tests for cross-module behavior (API/service boundaries, persistence, encryption behavior, etc.)
- Tests MUST reference requirement ID(s) using the same tag format:
  - `REQ: <REQ-ID>` or `REQ: <REQ-ID1>, <REQ-ID2>`
- If a requirement is not testable yet (e.g., missing harness), create:
  - A tracked test stub marked `SKIP`/`XFAIL` with a linked issue/task, plus a brief rationale.
  - Still maintain trace links for future completion.

### 3.3 Code-to-tests
- Every non-trivial production change MUST introduce or update tests.
- Tests should verify behavior and security properties (e.g., redaction, encryption at rest, auth gating) where applicable.

### 3.4 Machine-readable trace index (required)
Maintain a repository-wide trace index to enable automated auditing. Create and keep updated:

- `trace/requirements.yml` (or `.json`), containing entries like:
  - requirement_id
  - title
  - parent_requirement_id (optional)
  - code_refs: list of file paths + symbol names/anchors
  - test_refs: list of file paths + test names
  - doc_refs: list of design docs that explain implementation decisions

Rules:
- Every change affecting a requirement MUST update the relevant entries.
- New code without trace entries is not acceptable.

## 4 Design documentation requirements
### 4.1 Always update or create design docs
For any non-trivial change (new module, new workflow, new security control, new storage model):
- Update existing design doc(s), or create a new doc under `docs/design/`.
- Docs MUST be Markdown and include Mermaid diagrams for flows or architecture.

Recommended design doc structure:
- Problem statement (linked requirement IDs)
- Architecture overview
- Data model changes
- API/interface changes
- Security considerations (threats + mitigations)
- Tradeoffs and alternatives considered
- Testing strategy and coverage mapping
- Rollout/migration notes (if applicable)

### 4.2 Mermaid diagram conventions
- Use Mermaid for sequence diagrams, flowcharts, state machines.
- Keep diagrams minimal and directly tied to requirement IDs.

Example tag in docs:
- `Requirements: SYS-003, SEC-CRY-001, FUNC-BKP-001`

## 5 Secure coding standards (best practices without losing efficiency)
### 5.1 Secrets and tokens
- Never log secrets (tokens, credentials, encryption keys, full account numbers).
- Store provider secrets only server-side if applicable; no secrets embedded in any client artifacts.
- Centralize secret access in a single module (e.g., `security/secrets.*`) to reduce duplication and ensure consistent handling.

### 5.2 Cryptography
- Use vetted libraries and modern primitives; no custom crypto.
- Prefer authenticated encryption for backups and sensitive blobs.
- Centralize cryptographic operations in `security/crypto.*` to standardize usage and reduce errors.

### 5.3 Logging and redaction
- All logs must be structured and pass through a redaction layer.
- Add tests that assert sensitive fields are absent from logs for relevant codepaths.

### 5.4 Input handling
- Validate and sanitize user inputs (notes, tags, category names) to prevent injection and malformed exports.
- Prefer parameterized queries for persistence; avoid string concatenation for queries.

### 5.5 Principle of least privilege
- Restrict filesystem permissions for DB/backup files.
- Keep network endpoints minimal; bind locally if appropriate; require auth for sensitive operations.

### 5.6 Dependency hygiene
- Pin dependencies and keep a lockfile.
- Run vulnerability checks when available; do not introduce unnecessary dependencies.

## 6 Code quality and DRY requirements
- Prefer small, composable modules; avoid copy/paste logic.
- If functionality is used in 2+ places, refactor into shared utilities/modules.
- Maintain clear boundaries:
  - Domain logic (budgets, categorization, reports)
  - Infrastructure (Plaid integration, persistence, encryption, logging)
  - UI/API layer (presentation + input validation)

## 7 Definition of Done (must satisfy before submission)
1. Implementation matches the PRD requirements; no scope creep.
2. Traceability updated:
   - In-code `REQ:` tags present
   - Tests include `REQ:` tags
   - `trace/requirements.yml` updated and consistent
3. Design docs updated/created in `docs/design/` with Mermaid diagrams where applicable.
4. All unit and component tests pass.
5. No secrets appear in logs; redaction verified by tests where applicable.
6. Lint/format/type checks (if configured) pass.
7. Security checks (if configured) pass.

## 8 Workflow for every task (agent checklist)
1. Identify impacted requirement IDs in the PRD.
2. Plan changes and update/create design doc first (or in parallel).
3. Implement code with `REQ:` tags.
4. Add/modify tests with `REQ:` tags.
5. Update `trace/requirements.yml` mappings.
6. Run all tests (unit + component) and required checks locally.
7. Provide a concise summary:
   - Requirements implemented/modified
   - Code files changed
   - Tests added/updated
   - Docs updated/created
   - Commands run and results

## 9 Repository conventions (create if missing)
If the following paths do not exist, create them:
- `docs/design/`
- `trace/`
- `trace/requirements.yml`

The agent is responsible for keeping these artifacts current as the codebase evolves.
