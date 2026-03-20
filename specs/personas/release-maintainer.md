---
id: release-maintainer
type: persona
---

# Persona: Release Maintainer

## Role
Maintainer responsible for publishing stable `ehr-writeback` releases to public package registries.

## Goals
- Publish a tagged release to PyPI without handling long-lived secrets
- Ensure users can install the package with standard Python tooling
- Keep release steps repeatable and auditable in GitHub Actions

## Frustrations
- Manual release steps drift over time and are easy to misconfigure
- Registry credentials create avoidable security and rotation overhead
- Failed releases are hard to diagnose without explicit workflow outputs

## Context
- Tech comfort: high
- Usage frequency: occasional
- Key devices: desktop

## Quotes
> "A release should be a tagged, observable workflow, not a one-off shell ritual."
