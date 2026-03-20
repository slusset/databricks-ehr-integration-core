---
id: publish-package-to-pypi
type: story
refs:
  journey: specs/journeys/publish-python-package.md
  persona: specs/personas/release-maintainer.md
  steps: [1, 2, 3, 4, 5]
---

# Story: Publish Package To PyPI

## Narrative
As a release maintainer,
I want tagged releases to publish `ehr-writeback` to PyPI through GitHub Actions,
So that users can install the package directly without maintainers managing static registry secrets.

## Acceptance Criteria
- [ ] A release-specific GitHub Actions workflow triggers from a release tag or release publication event
- [ ] The publish job builds both wheel and source distribution artifacts from the tagged revision
- [ ] The publish job uses OIDC trusted publishing instead of PyPI API token secrets
- [ ] The workflow fails clearly when artifact build or publish steps do not complete
- [ ] The released package can be installed in a clean environment with `pip install ehr-writeback`
- [ ] The README exposes a PyPI badge and install path for the published package

## Notes
This story is about operational release behavior rather than runtime API behavior. The contract should therefore describe the release workflow trigger, permissions, artifacts, and expected publish outcomes instead of an application endpoint.
