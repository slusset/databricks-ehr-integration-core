# id: publish-package
# type: feature
# story: specs/stories/release/publish-package-to-pypi.md
# journey: specs/journeys/publish-python-package.md
# contract: WORKFLOW specs/contracts/workflows/pypi-publish.contract.yaml

@release
Feature: Publish ehr-writeback to PyPI
  As a release maintainer
  I want GitHub Actions to publish tagged releases to PyPI
  So that users can install ehr-writeback directly from the Python package index

  @happy-path
  Scenario: Publish a tagged release through trusted publishing
    Given a repository release is published for version "0.1.0"
    And the release workflow can build both source and wheel artifacts
    And PyPI trusted publishing is configured for this repository and workflow
    When the publish workflow runs
    Then the workflow publishes "ehr-writeback" version "0.1.0" to PyPI
    And the workflow reports a successful publish outcome

  @workflow-validation
  Scenario: Fail when trusted publishing is not available
    Given a repository release is published for version "0.1.0"
    And the publish workflow does not have OIDC publish permission
    When the publish workflow runs
    Then the workflow fails before uploading to PyPI
    And the failure indicates that trusted publishing is not configured

  @artifact-validation
  Scenario: Fail when build artifacts are incomplete
    Given a repository release is published for version "0.1.0"
    And only one distribution artifact is produced
    When the publish workflow runs
    Then the workflow fails before publish
    And the failure indicates both wheel and source distribution are required

  @install-verification
  Scenario: Verify a released package can be installed
    Given "ehr-writeback" version "0.1.0" has been published to PyPI
    When a user installs the package in a clean Python environment
    Then `pip install ehr-writeback==0.1.0` succeeds
    And the installed package exposes the `ehr_writeback` module
