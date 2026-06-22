# apk-version-analysis Specification

## Purpose
TBD - created by archiving change add-apk-diff-tooling. Update Purpose after archive.
## Requirements
### Requirement: Import a specific APK into the working set
The `import-apk` task SHALL copy a caller-specified APK file into `bluetti-files/<version>/bluetti.apk`, where `<version>` is derived from the source filename, so that the existing `decompile-jadx` and `decompile-apktool` tasks process it without modification. The task SHALL NOT overwrite an APK that is already staged.

#### Scenario: Importing an archived APK
- **WHEN** a user runs `import-apk` with the path to an APK in `bluetti-apk-archive/`
- **THEN** the APK is staged at `bluetti-files/<version>/bluetti.apk`
- **AND** it is available to `decompile-jadx` and `decompile-apktool`

#### Scenario: Importing a version that is already staged
- **WHEN** a user runs `import-apk` for a version whose `bluetti.apk` already exists
- **THEN** the task leaves the existing APK in place and reports it as already present

#### Scenario: Importing a missing or unreadable file
- **WHEN** the provided path does not exist or is not a readable file
- **THEN** the task exits with a non-zero status and an explanatory message

### Requirement: Preserve downloaded APKs during cleanup
The `cleanup` task SHALL remove derived decompilation and diff output under `bluetti-files/` while preserving every `bluetti.apk`. Because Bluetti's download endpoint serves only the latest build, older APKs cannot be re-fetched and MUST be treated as precious.

#### Scenario: Cleanup removes derived output but keeps APKs
- **WHEN** a user runs `cleanup` with decompiled output and staged APKs present
- **THEN** all `jadx_out`, `apktool_out`, diff output, and logs are removed
- **AND** every `bluetti.apk` remains in place

#### Scenario: Cleanup with nothing to clean
- **WHEN** `bluetti-files/` does not exist
- **THEN** the task exits successfully without error

### Requirement: Compare protocol-relevant anchors between two versions
The `diff-apk` task SHALL produce a focused comparison of protocol-relevant anchors between two decompiled versions, covering at least BLE UUIDs, register/numeric constants, cryptographic usage, and device-model identifiers extracted from the decompiled code. Output SHALL be written under `bluetti-files/` (gitignored, regenerable). The task SHALL NOT rely on a raw recursive text diff of the decompiled trees.

#### Scenario: Diffing two decompiled versions
- **WHEN** a user runs `diff-apk` with two versions that have both been decompiled
- **THEN** the task writes comparison artifacts highlighting added, removed, and changed protocol anchors between the versions

#### Scenario: Diffing a version that has not been decompiled
- **WHEN** a user runs `diff-apk` referencing a version with no decompiled output
- **THEN** the task exits with a non-zero status and indicates which version must be decompiled first

### Requirement: Compare the resource and user-facing surface between two versions
The `diff-apk` task SHALL also compare the resource and user-facing surface between the two versions, covering at least default string resources, GUI layouts, the drawable/asset/mipmap inventory, Android manifest components and permissions, and build/version properties. This comparison SHALL highlight added, removed, and changed items so a reviewer can infer the nature of a release (e.g., new device support, new or renamed features).

#### Scenario: A release adds device support or a feature
- **WHEN** `diff-apk` compares a version that introduces a new device or feature
- **THEN** the resource comparison surfaces the new or changed strings, layouts, and assets that accompany it

#### Scenario: Version metadata is reported
- **WHEN** `diff-apk` compares two versions
- **THEN** the comparison reports each version's `versionName`/`versionCode` and any changed permissions or manifest components

### Requirement: Compare the backend/cloud API surface between two versions
The `diff-apk` task SHALL compare the backend/cloud API surface between the two versions, covering at least HTTP endpoint paths, host/base URLs, and HTTP client definitions (e.g. Retrofit/OkHttp) extracted from the decompiled code. The comparison SHALL highlight added, removed, and changed endpoints and hosts.

#### Scenario: An endpoint changes between versions
- **WHEN** `diff-apk` compares two versions where a cloud endpoint path or host changed
- **THEN** the comparison surfaces the added, removed, and changed endpoints and hosts with citations

### Requirement: Document latest-only APK acquisition
The APK acquisition workflow SHALL document that `download-apk` retrieves only the latest published build and that Bluetti provides no supported way to download a specific historical version. The documentation SHALL direct users to `import-apk` with the local archive for older versions.

#### Scenario: User seeks an older version
- **WHEN** a developer needs an APK version other than the latest
- **THEN** the documentation directs them to import it from `bluetti-apk-archive/` via `import-apk` rather than expecting `download-apk` to fetch it

