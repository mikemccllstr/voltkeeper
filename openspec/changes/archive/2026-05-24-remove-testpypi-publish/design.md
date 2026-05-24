## Context

The `publish-to-testpypi` job in `publish-to-pypi.yml` runs on every push to `main`. The project uses hatch-vcs with the `post-release` version scheme, which appends a local version segment (`+g<commit>`) on any non-tagged commit. PyPI and TestPyPI both reject local versions, causing every main-push TestPyPI publish to fail with HTTP 400.

TestPyPI no longer provides value as a pre-release check. It can be added back later if needed.

## Goals / Non-Goals

**Goals:**
- Remove the failing `publish-to-testpypi` job
- Eliminate TestPyPI-related noise from CI runs

**Non-Goals:**
- Changing the version scheme
- Modifying the `build` or `publish-to-pypi` jobs
- Adding manual dispatch triggers (considered and rejected — see below)

## Decisions

### Remove rather than fix

The failing TestPyPI publish could have been fixed by gating it behind tags or workflow_dispatch. But the team assessed TestPyPI provides no current value and opted for removal. If pre-release checks are needed later, the job can be restored and gated appropriately.

### Keep the build job

The `build` job (building sdist + wheel) runs on every main push and tag push. It's cheap, fast, and serves as a build-sanity check. It stays unchanged.

## Risks / Trade-offs

- **No pre-release check**: If a packaging error is introduced, it won't be caught until a tag-triggered PyPI publish. Mitigation: the `uv build` step in CI on every main push still validates that the package builds successfully.
- **Reversibility**: Low risk — re-adding TestPyPI publish is a single job addition.
