---
id: publish-python-package
type: journey
refs:
  persona: specs/personas/release-maintainer.md
---

# Journey: Publish Python Package

## Actor
Release maintainer preparing a public package release.
Source Persona: specs/personas/release-maintainer.md

## Trigger
A maintainer is ready to publish a tagged release of `ehr-writeback` to PyPI.

## Preconditions
- The repository has a passing CI baseline for the revision being released
- The package metadata and build backend are present in `pyproject.toml`
- PyPI trusted publishing is configured for the repository and publish workflow

## Flow

### 1. Create release intent
- **User intent**: Mark a specific repository revision as release-worthy
- **System response**: GitHub records a version tag or release event for that revision
- **Next**: Build distribution artifacts from the tagged source

### 2. Build distributable artifacts
- **User intent**: Produce the wheel and source distribution that will be published
- **System response**: The release workflow builds reproducible Python package artifacts and validates their presence
- **Next**: Authenticate to PyPI using trusted publishing

### 3. Publish with trusted identity
- **User intent**: Publish without storing PyPI API tokens in repository secrets
- **System response**: GitHub Actions obtains an OIDC identity token and exchanges it through PyPI trusted publishing
- **Next**: Upload artifacts and await publish confirmation

### 4. Confirm installability
- **User intent**: Verify end users can install the released package
- **System response**: The workflow reports the published version and supports clean-environment install verification
- **Next**: Surface release status in repository docs

### 5. Surface release status
- **User intent**: Make release availability visible to repository visitors
- **System response**: README displays the PyPI version badge and points users to `pip install ehr-writeback`
- **Next**: Journey complete

## Outcomes
- **Success**: A tagged GitHub release publishes `ehr-writeback` to PyPI via trusted publishing, and users can install it with `pip install ehr-writeback`
- **Failure modes**: Build artifacts are missing, trusted publishing is not configured, publish permissions are absent, or the release publishes but install verification fails

## Related Stories
- specs/stories/release/publish-package-to-pypi.md

## E2E Coverage
- .github/workflows/release-publish.yml
