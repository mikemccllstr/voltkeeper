# ABOUTME: Tests for mise tasks (import-apk, cleanup) using subprocess.
# ABOUTME: Runs bash task scripts in isolated temporary directories.

import subprocess
from pathlib import Path

TASKS_DIR = Path(__file__).parent.parent / ".mise" / "tasks"


def run_task(name, args=(), cwd=None):
    """Run a mise task script directly; returns CompletedProcess."""
    return subprocess.run(
        [str(TASKS_DIR / name), *args],
        capture_output=True,
        text=True,
        cwd=cwd,
    )


# --- import-apk ---


def test_import_apk_stages_file(tmp_path):
    fake_apk = tmp_path / "BLUETTI-v3.0.9.apk"
    fake_apk.write_bytes(b"PK fake apk content")

    result = run_task("import-apk", [str(fake_apk)], cwd=tmp_path)

    assert result.returncode == 0
    staged = tmp_path / "bluetti-files" / "BLUETTI-v3.0.9.apk" / "bluetti.apk"
    assert staged.exists()
    assert staged.read_bytes() == b"PK fake apk content"


def test_import_apk_idempotent(tmp_path):
    fake_apk = tmp_path / "BLUETTI-v3.0.9.apk"
    fake_apk.write_bytes(b"original content")
    run_task("import-apk", [str(fake_apk)], cwd=tmp_path)

    fake_apk.write_bytes(b"different content")
    result = run_task("import-apk", [str(fake_apk)], cwd=tmp_path)

    assert result.returncode == 0
    staged = tmp_path / "bluetti-files" / "BLUETTI-v3.0.9.apk" / "bluetti.apk"
    assert staged.read_bytes() == b"original content"
    combined = result.stdout + result.stderr
    assert "already" in combined.lower() or "skipping" in combined.lower()


def test_import_apk_missing_path(tmp_path):
    result = run_task("import-apk", ["/nonexistent/BLUETTI-v9.9.9.apk"], cwd=tmp_path)

    assert result.returncode != 0
    combined = result.stdout + result.stderr
    assert "BLUETTI-v9.9.9.apk" in combined


def test_import_apk_no_args(tmp_path):
    result = run_task("import-apk", [], cwd=tmp_path)

    assert result.returncode != 0


# --- cleanup ---


def test_cleanup_removes_derived_output_preserves_apks(tmp_path):
    ver_dir = tmp_path / "bluetti-files" / "BLUETTI-v3.0.9.apk"
    apk = ver_dir / "bluetti.apk"
    jadx_file = ver_dir / "jadx_out" / "sources" / "Foo.java"
    apktool_file = ver_dir / "apktool_out" / "AndroidManifest.xml"

    apk.parent.mkdir(parents=True)
    apk.write_bytes(b"PK apk")
    jadx_file.parent.mkdir(parents=True)
    jadx_file.write_text("class Foo {}")
    apktool_file.parent.mkdir(parents=True)
    apktool_file.write_text("<manifest/>")

    result = run_task("cleanup", cwd=tmp_path)

    assert result.returncode == 0
    assert apk.exists(), "APK must be preserved"
    assert not (ver_dir / "jadx_out").exists(), "jadx_out must be removed"
    assert not (ver_dir / "apktool_out").exists(), "apktool_out must be removed"


def test_cleanup_noop_when_absent(tmp_path):
    result = run_task("cleanup", cwd=tmp_path)

    assert result.returncode == 0
