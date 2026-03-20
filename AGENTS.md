# AGENTS.md

## Repo Summary

This repository contains `ehr-writeback`, a Python framework for writing analytics results back into EHR systems through FHIR. It is designed around hexagonal architecture:

- `src/ehr_writeback/core/` contains domain models, ports, and orchestration logic.
- `src/ehr_writeback/adapters/` contains EHR-specific adapters such as Epic, Cerner, and generic FHIR R4.
- `src/ehr_writeback/infrastructure/` contains persistence, idempotency, and dead-letter support.
- `src/ehr_writeback/pipelines/` contains Databricks-oriented pipeline code.
- `tests/unit/` contains fast unit coverage for core behavior.
- `tests/integration/` contains live integration tests against FHIR endpoints, gated by environment variables.

This is a Python 3.10+ project managed with `uv`. Standard quality checks use `pytest`, `ruff`, and `mypy`.

## Default Development Guidance

Use [$idd-workflow](https://github.com/slusset/intention-driven-design) as the default workflow guide for starting work, modifying behavior, and fixing defects in this repository.

Apply these repo-specific expectations when using `$idd-workflow`:

- Treat the repository as a Python backend project with hexagonal boundaries.
- Prefer changes that keep domain logic in `core/` and infrastructure or EHR-specific concerns in adapters/infrastructure packages.
- The repository now uses a committed `specs/` tree as the source of truth for issue-driven capability work. Start with the relevant artifacts under `specs/` before implementation, and extend the tree when a new issue introduces a new capability.
- `specs/skills/repo-overlay.md` is still not present. If `$idd-workflow` looks for it, treat it as missing and continue with the repo rules in this `AGENTS.md` unless the user explicitly asks to scaffold the overlay.
- For implementation and verification, rely on the existing Python toolchain and test suite in this repo.

## Specs Workflow Guidance

When creating or changing behavior for a GitHub issue, prefer the following artifact flow:

1. Narrative layer:
   - `specs/personas/`
   - `specs/journeys/`
   - `specs/stories/`
2. Capability scope:
   - `specs/capabilities/`
3. Model layer:
   - `specs/models/`
4. Contract and fixture layer:
   - `specs/features/`
   - `specs/contracts/`
   - `specs/fixtures/`

Additional repo-specific rules:

- For operational or CI/CD capabilities that do not expose an application API, use a workflow contract under `specs/contracts/workflows/` instead of forcing an OpenAPI document.
- Keep traceability explicit: story references journey and persona, capability references the in-scope artifacts, and contracts/features point back to the source story.
- Keep issue scope tight. Prefer one capability file per issue-sized change unless the issue clearly extends an existing capability.

## Story Workflow

For work tied to an assigned GitHub issue, follow this process in addition to `$idd-workflow`:

1. Review the assigned GitHub issue and confirm the intended behavior change.
2. Create a branch for that issue before coding.
   Example: `git checkout -b feature/gh-123-short-description`
3. Make the smallest coherent change that satisfies the issue while preserving hexagonal boundaries.
4. Run the required verification for the scope of the change:
   - Unit tests: `uv run pytest tests/unit`
   - Behavior tests: run the relevant behavior/spec tests if they exist for the story being changed
   - Integration tests: run the appropriate integration coverage for affected adapters or FHIR flows
5. Run the standard repo quality checks before finishing:
   - `uv run ruff check src/ tests/`
   - `uv run ruff format --check src/ tests/`
   - `uv run mypy src/`
6. If all required checks are green, commit with a concise message that references the issue when appropriate.
7. Push the branch to origin.
8. Open a pull request against `main`.

## Test Selection Guidance

Choose verification based on what changed:

- Core model or orchestration changes: run `uv run pytest tests/unit`
- Adapter changes: run the affected unit tests and the matching integration tests under `tests/integration/`
- Live FHIR integration tests require `FHIR_TEST_BASE_URL`
  Example: `FHIR_TEST_BASE_URL=https://hapi.fhir.org/baseR4 uv run pytest tests/integration/ -v`
- Databricks-related work may require `uv sync --extra databricks` before validation

Do not skip required integration coverage when a story changes adapter behavior, request/response handling, or live FHIR interoperability.

## Pull Request End State

A story is ready for PR only when all of the following are true:

- Branch created from the assigned GitHub issue
- Required unit, behavior, and appropriate integration tests are green
- Lint and type checks are green
- Changes are committed and pushed
- A pull request is opened
