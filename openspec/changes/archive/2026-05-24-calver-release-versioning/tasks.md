## 1. Configure hatch-vcs

- [x] 1.1 Add `hatch-vcs` to `pyproject.toml` build-system requires
- [x] 1.2 Remove hardcoded `version` from `pyproject.toml` `[project]` section
- [x] 1.3 Add `[tool.hatch.build.hooks.vcs]` config with CalVer tag pattern
- [x] 1.4 Verify `uv build` produces correct version from a test tag

## 2. Update publish workflow triggers

- [x] 2.1 Replace `on: push` with `on: push: branches: [main]` and `tags: ['v*']`
- [x] 2.2 Verify the TestPyPI job still runs (no `if` guard needed)
- [x] 2.3 Verify the PyPI job `if` guard is still correct for the new tag format

## 3. Validate end-to-end

- [ ] 3.1 Create a test tag and push — confirm both TestPyPI and PyPI run
- [ ] 3.2 Push to main without a tag — confirm only TestPyPI runs
- [ ] 3.3 Push to a feature branch — confirm publish workflow does not trigger
- [x] 3.4 Run `mise run check` to confirm no regressions
