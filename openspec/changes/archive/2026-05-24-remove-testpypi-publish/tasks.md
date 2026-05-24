## 1. Remove TestPyPI job

- [x] 1.1 Remove the `publish-to-testpypi` job from `.github/workflows/publish-to-pypi.yml`
- [x] 1.2 Remove the `testpypi` environment dependency from the `build` job's `needs` (if it references testpypi — confirm during implementation)

## 2. Validate

- [x] 2.1 Run `mise run check` to confirm no regressions
- [x] 2.2 Push branch and verify CI passes, and confirm no TestPyPI job appears in the CI run
