# Contributing to ehr-writeback

Thanks for your interest in contributing! This project aims to close the loop from healthcare analytics back to clinical workflow via FHIR.

## Development Setup

### Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

### Getting started

```bash
# Clone the repo
git clone git@github.com:slusset/databricks-ehr-integration-core.git
cd databricks-ehr-integration-core

# Install dependencies (includes dev tools)
uv sync

# Run tests
uv run pytest

# Run linting
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/

# Run type checking
uv run mypy src/
```

### Optional: Databricks extras

If you're working on the Databricks integration layer:

```bash
uv sync --extra databricks
```

## Project Structure

```
src/ehr_writeback/
├── core/           # Domain models, port interfaces, orchestrator
├── adapters/       # EHR-specific implementations (Epic, Cerner, Generic FHIR)
├── infrastructure/ # Delta Lake storage, idempotency, dead-letter
└── pipelines/      # DLT pipeline definitions
```

The architecture follows **hexagonal (ports-and-adapters)** design. If you're adding a new EHR adapter:

1. Create a new directory under `src/ehr_writeback/adapters/<ehr_name>/`
2. Implement `EHRWritebackPort` from `core/ports.py`
3. Implement `AuthPort` for the EHR's authentication mechanism
4. Add tests under `tests/unit/`

## Coding Standards

- **Style**: We use [Ruff](https://docs.astral.sh/ruff/) for linting and formatting. CI enforces this.
- **Types**: All new code should pass `mypy --strict`. Use type annotations everywhere.
- **Tests**: All new features need unit tests. Use `pytest` with `pytest-asyncio` for async code.
- **Imports**: Use absolute imports from `ehr_writeback.*`. Ruff handles import sorting.

### Ruff rules we enforce

`E` (pycodestyle), `F` (pyflakes), `I` (isort), `UP` (pyupgrade), `B` (bugbear), `SIM` (simplify)

## Pull Request Process

1. **Fork** the repo and create a feature branch from `main`
2. **Write tests** for any new functionality
3. **Run the full check suite** before submitting:
   ```bash
   uv run ruff check src/ tests/
   uv run ruff format --check src/ tests/
   uv run pytest
   ```
4. **Open a PR** against `main` with a clear description of what and why
5. CI must pass (lint + tests)
6. A maintainer will review — we aim to respond within a few business days

### Commit messages

- Use present tense ("Add feature" not "Added feature")
- Keep the first line under 72 characters
- Reference issue numbers where applicable (`Closes #123`)

## Reporting Bugs

Use the [bug report template](https://github.com/slusset/databricks-ehr-integration-core/issues/new?template=bug_report.md) on GitHub. Include:

- Steps to reproduce
- Expected vs. actual behavior
- Python version, OS, and relevant package versions

## Requesting Features

Use the [feature request template](https://github.com/slusset/databricks-ehr-integration-core/issues/new?template=feature_request.md). We especially welcome:

- New EHR adapter implementations
- Additional clinical scoring models (like the sepsis example)
- Improvements to retry/resilience logic

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you agree to uphold it.

## License

By contributing, you agree that your contributions will be licensed under the [Apache 2.0 License](LICENSE).
