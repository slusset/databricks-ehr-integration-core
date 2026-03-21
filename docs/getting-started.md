# Getting Started

## Install from PyPI

```bash
pip install ehr-writeback
```

## Local development setup

```bash
git clone git@github.com:slusset/databricks-ehr-integration-core.git
cd databricks-ehr-integration-core
uv sync
```

## Run the standard checks

```bash
uv run pytest tests/unit -v --tb=short
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy src/ehr_writeback/core/
```

## Build the docs site locally

```bash
uv sync --group docs
uv run --group docs mkdocs serve
```
