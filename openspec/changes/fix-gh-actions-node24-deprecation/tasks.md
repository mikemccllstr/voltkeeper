## 1. Update ci.yml

- [x] 1.1 Bump `actions/checkout@v4` → `@v6` (quality job)
- [x] 1.2 Bump `jdx/mise-action@v2` → `@v4` (quality job)
- [x] 1.3 Bump `actions/checkout@v4` → `@v6` (test job, inside matrix)
- [x] 1.4 Bump `jdx/mise-action@v2` → `@v4` (test job, inside matrix)

## 2. Update publish-to-pypi.yml

- [x] 2.1 Bump `actions/checkout@v4` → `@v6` (build job)
- [x] 2.2 Bump `jdx/mise-action@v2` → `@v4` (build job)
- [x] 2.3 Fix `actions/upload-artifact@v5` → `@v7` (build job, nonexistent version)
- [x] 2.4 Fix `actions/download-artifact@v6` → `@v8` (publish-to-testpypi job, nonexistent version)
- [x] 2.5 Fix `actions/download-artifact@v6` → `@v8` (publish-to-pypi job, nonexistent version)

## 3. Update docs.yml

- [x] 3.1 Bump `actions/checkout@v4` → `@v6` (deploy job)
- [x] 3.2 Bump `jdx/mise-action@v2` → `@v4` (deploy job)
- [x] 3.3 Pin `peaceiris/actions-gh-pages@v4` → `@v4.1` (deploy job, same major, latest patch)

## 4. Validate

- [x] 4.1 Run `mise run check` to confirm no regressions in local toolchain
- [ ] 4.2 Push branch and verify CI passes without deprecation warnings
