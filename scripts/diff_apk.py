#!/usr/bin/env python3
# ABOUTME: Extracts and compares protocol anchors, resource surface, and cloud API between two decompiled APK versions.
# ABOUTME: Importable extractors for unit testing; the __main__ block drives the diff-apk mise task.

import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree

# ---------------------------------------------------------------------------
# Extraction: protocol anchors (from jadx_out)
# ---------------------------------------------------------------------------

_UUID_RE = re.compile(
    r'"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"',
    re.IGNORECASE,
)

_CONST_RE = re.compile(
    r"(?:public\s+)?static\s+final\s+(?:int|long)\s+(\w+)\s*=\s*(\d+)\s*;"
)

# Bluetti model names: 1–3 uppercase letters + 1–4 digits + optional uppercase letter/suffix
_MODEL_RE = re.compile(r'"([A-Z]{1,3}[0-9]{1,4}[A-Z]?)"')
_MODEL_NOISE = frozenset({"UUID", "NULL", "HTTP", "UTF8", "JSON", "HTML", "TRUE", "FALSE", "NaN"})


def extract_ble_uuids(jadx_dir: Path) -> set:
    """Return all UUID-format string literals found in Java sources under jadx_dir."""
    uuids = set()
    for java_file in jadx_dir.rglob("*.java"):
        text = java_file.read_text(errors="replace")
        for m in _UUID_RE.finditer(text):
            uuids.add(m.group(1).lower())
    return uuids


def extract_register_constants(jadx_dir: Path) -> set:
    """Return (name, value) pairs for static final int/long constants in jadx_dir."""
    constants = set()
    for java_file in jadx_dir.rglob("*.java"):
        text = java_file.read_text(errors="replace")
        for m in _CONST_RE.finditer(text):
            name, value = m.group(1), int(m.group(2))
            constants.add((name, value))
    return constants


def extract_device_models(jadx_dir: Path) -> set:
    """Return device model identifier strings found in Java sources under jadx_dir."""
    models = set()
    for java_file in jadx_dir.rglob("*.java"):
        text = java_file.read_text(errors="replace")
        for m in _MODEL_RE.finditer(text):
            name = m.group(1)
            if name not in _MODEL_NOISE:
                models.add(name)
    return models


# ---------------------------------------------------------------------------
# Extraction: resource/UI surface (from apktool_out)
# ---------------------------------------------------------------------------


def extract_string_resources(apktool_dir: Path) -> dict:
    """Return {name: value} from the default strings.xml, or {} if missing."""
    strings_xml = apktool_dir / "res" / "values" / "strings.xml"
    if not strings_xml.exists():
        return {}
    try:
        tree = ElementTree.parse(strings_xml)
    except ElementTree.ParseError:
        return {}
    result = {}
    for elem in tree.iterfind("string"):
        name = elem.get("name")
        if name and elem.text:
            result[name] = elem.text
    return result


def extract_layout_inventory(apktool_dir: Path) -> set:
    """Return the set of layout filenames under res/layout/."""
    layout_dir = apktool_dir / "res" / "layout"
    if not layout_dir.is_dir():
        return set()
    return {f.name for f in layout_dir.iterdir() if f.is_file()}


def extract_manifest_info(apktool_dir: Path) -> dict:
    """Return permissions, activities, services, and version info from the manifest."""
    result: dict = {
        "permissions": set(),
        "activities": set(),
        "services": set(),
        "version_name": "",
        "version_code": "",
    }

    manifest = apktool_dir / "AndroidManifest.xml"
    apktool_yml = apktool_dir / "apktool.yml"

    # Version from apktool.yml (more reliable than manifest attributes)
    if apktool_yml.exists():
        for line in apktool_yml.read_text().splitlines():
            if "versionName:" in line:
                result["version_name"] = line.split(":", 1)[1].strip().strip("'\"")
            elif "versionCode:" in line:
                result["version_code"] = line.split(":", 1)[1].strip().strip("'\"")

    if not manifest.exists():
        return result

    try:
        tree = ElementTree.parse(manifest)
    except ElementTree.ParseError:
        return result

    root = tree.getroot()
    _NS = "http://schemas.android.com/apk/res/android"

    def _android_attr(elem: ElementTree.Element, attr: str) -> str:
        return elem.get(f"{{{_NS}}}{attr}") or elem.get(f"android:{attr}") or ""

    for perm in root.iter("uses-permission"):
        name = _android_attr(perm, "name")
        if name:
            result["permissions"].add(name)

    app = root.find("application")
    if app is not None:
        for activity in app.iter("activity"):
            name = _android_attr(activity, "name")
            if name:
                result["activities"].add(name)
        for service in app.iter("service"):
            name = _android_attr(service, "name")
            if name:
                result["services"].add(name)

    return result


# ---------------------------------------------------------------------------
# Extraction: backend/cloud API (from jadx_out)
# ---------------------------------------------------------------------------

# API paths: at least two path segments, starting with /api/ or /
_ENDPOINT_RE = re.compile(r'"(/(?:api/|[a-z])[a-zA-Z0-9/_.-]*(?:/[a-zA-Z0-9/_.-]+)+)"')

# Base URLs and SSL broker URIs
_HOST_RE = re.compile(r'"((?:https?|ssl)://[a-z0-9][a-z0-9.-]+(?::[0-9]+)?)"', re.IGNORECASE)


def extract_http_endpoints(jadx_dir: Path) -> set:
    """Return API endpoint path strings found in Java sources."""
    endpoints = set()
    for java_file in jadx_dir.rglob("*.java"):
        text = java_file.read_text(errors="replace")
        for m in _ENDPOINT_RE.finditer(text):
            endpoints.add(m.group(1))
    return endpoints


def extract_http_hosts(jadx_dir: Path) -> set:
    """Return base URL / host strings (https://, http://, ssl://) found in Java sources."""
    hosts = set()
    for java_file in jadx_dir.rglob("*.java"):
        text = java_file.read_text(errors="replace")
        for m in _HOST_RE.finditer(text):
            hosts.add(m.group(1))
    return hosts


# ---------------------------------------------------------------------------
# Comparison helper
# ---------------------------------------------------------------------------


def compare_sets(a: set, b: set) -> dict:
    """Return {added, removed, unchanged} sets comparing a (old) to b (new)."""
    return {
        "added": b - a,
        "removed": a - b,
        "unchanged": a & b,
    }


def compare_dicts(a: dict, b: dict) -> dict:
    """Compare two str→str dicts; return {added, removed, changed, unchanged} dicts."""
    keys_a = set(a)
    keys_b = set(b)
    added = {k: b[k] for k in keys_b - keys_a}
    removed = {k: a[k] for k in keys_a - keys_b}
    changed = {k: (a[k], b[k]) for k in keys_a & keys_b if a[k] != b[k]}
    unchanged = {k: a[k] for k in keys_a & keys_b if a[k] == b[k]}
    return {"added": added, "removed": removed, "changed": changed, "unchanged": unchanged}


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def _fmt_set_diff(diff: dict, label: str, lines: list) -> None:
    lines.append(f"\n### {label}")
    for item in sorted(str(x) for x in diff["added"]):
        lines.append(f"  + {item}")
    for item in sorted(str(x) for x in diff["removed"]):
        lines.append(f"  - {item}")
    if not diff["added"] and not diff["removed"]:
        lines.append("  (no changes)")


def _fmt_dict_diff(diff: dict, label: str, lines: list) -> None:
    lines.append(f"\n### {label}")
    for k, v in sorted(diff["added"].items()):
        lines.append(f"  + {k} = {v!r}")
    for k, v in sorted(diff["removed"].items()):
        lines.append(f"  - {k} = {v!r}")
    for k, (old, new) in sorted(diff["changed"].items()):
        lines.append(f"  ~ {k}: {old!r} → {new!r}")
    if not diff["added"] and not diff["removed"] and not diff["changed"]:
        lines.append("  (no changes)")


# ---------------------------------------------------------------------------
# Version resolution
# ---------------------------------------------------------------------------

_BLUETTI_DIR_RE = re.compile(r"BLUETTI[_-]v?(\d+\.\d+\.\d+)")


def resolve_version_dir(bluetti_files: Path, ver: str) -> Path | None:
    """Find the bluetti-files subdirectory that corresponds to a version string.

    Accepts either a short version (e.g., '3.0.9') or a full directory name.
    """
    # Direct match
    if (bluetti_files / ver).is_dir():
        return bluetti_files / ver

    # Standard naming convention: BLUETTI-v<ver>.apk
    candidate = bluetti_files / f"BLUETTI-v{ver}.apk"
    if candidate.is_dir():
        return candidate

    # Glob scan: any directory whose name contains the version string
    for d in bluetti_files.iterdir():
        if d.is_dir() and ver in d.name:
            return d

    return None


def check_decompiled(ver_dir: Path, ver: str) -> str | None:
    """Return an error message if ver_dir lacks both decompiled outputs, else None."""
    if not (ver_dir / "jadx_out").is_dir() or not (ver_dir / "apktool_out").is_dir():
        return f"version {ver!r} has not been decompiled (missing jadx_out or apktool_out in {ver_dir})"
    return None


# ---------------------------------------------------------------------------
# Main diff logic
# ---------------------------------------------------------------------------


def diff_apk(bluetti_files: Path, ver_a: str, ver_b: str, out_dir: Path) -> None:
    """Extract all three lenses for verA and verB, write comparison artifacts to out_dir."""
    dir_a = resolve_version_dir(bluetti_files, ver_a)
    dir_b = resolve_version_dir(bluetti_files, ver_b)

    for ver, d in [(ver_a, dir_a), (ver_b, dir_b)]:
        if d is None:
            print(f"Error: version {ver!r} not found under {bluetti_files}", file=sys.stderr)
            sys.exit(1)
        err = check_decompiled(d, ver)
        if err:
            print(f"Error: {err}", file=sys.stderr)
            sys.exit(1)

    jadx_a = dir_a / "jadx_out"
    jadx_b = dir_b / "jadx_out"
    apktool_a = dir_a / "apktool_out"
    apktool_b = dir_b / "apktool_out"

    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # --- Protocol anchors ---
    uuids = compare_sets(extract_ble_uuids(jadx_a), extract_ble_uuids(jadx_b))
    consts_a = {f"{n}={v}" for n, v in extract_register_constants(jadx_a)}
    consts_b = {f"{n}={v}" for n, v in extract_register_constants(jadx_b)}
    consts = compare_sets(consts_a, consts_b)
    models = compare_sets(extract_device_models(jadx_a), extract_device_models(jadx_b))

    lines = [f"# Protocol Anchors: {ver_a} vs {ver_b}", f"# Generated: {ts}", ""]
    _fmt_set_diff(uuids, "BLE UUIDs", lines)
    _fmt_set_diff(consts, "Register Constants (name=value)", lines)
    _fmt_set_diff(models, "Device Models", lines)
    (out_dir / "protocol_anchors.txt").write_text("\n".join(lines) + "\n")

    # --- Resource/UI surface ---
    strings = compare_dicts(
        extract_string_resources(apktool_a), extract_string_resources(apktool_b)
    )
    layouts = compare_sets(extract_layout_inventory(apktool_a), extract_layout_inventory(apktool_b))
    manifest_a = extract_manifest_info(apktool_a)
    manifest_b = extract_manifest_info(apktool_b)
    permissions = compare_sets(manifest_a["permissions"], manifest_b["permissions"])
    activities = compare_sets(manifest_a["activities"], manifest_b["activities"])
    services = compare_sets(manifest_a["services"], manifest_b["services"])

    lines = [f"# Resource / UI Surface: {ver_a} vs {ver_b}", f"# Generated: {ts}"]
    lines.append(f"\n## Version Info")
    lines.append(f"  {ver_a}: versionName={manifest_a['version_name']}, versionCode={manifest_a['version_code']}")
    lines.append(f"  {ver_b}: versionName={manifest_b['version_name']}, versionCode={manifest_b['version_code']}")
    _fmt_dict_diff(strings, "String Resources", lines)
    _fmt_set_diff(layouts, "Layout Files", lines)
    _fmt_set_diff(permissions, "Permissions", lines)
    _fmt_set_diff(activities, "Activities", lines)
    _fmt_set_diff(services, "Services", lines)
    (out_dir / "resources.txt").write_text("\n".join(lines) + "\n")

    # --- Cloud API ---
    endpoints = compare_sets(extract_http_endpoints(jadx_a), extract_http_endpoints(jadx_b))
    hosts = compare_sets(extract_http_hosts(jadx_a), extract_http_hosts(jadx_b))

    lines = [f"# Cloud API Surface: {ver_a} vs {ver_b}", f"# Generated: {ts}", ""]
    _fmt_set_diff(endpoints, "HTTP Endpoints", lines)
    _fmt_set_diff(hosts, "Base URLs / Hosts", lines)
    (out_dir / "cloud_api.txt").write_text("\n".join(lines) + "\n")

    # --- AGENTS.md for the diff directory ---
    report_path = f"docs/source/protocol/apk-{ver_a}-vs-{ver_b}.md"
    agents_md = (
        f"# APK Diff: {ver_a} vs {ver_b}\n"
        f"\n"
        f"Produced by: mise run diff-apk {ver_a} {ver_b}\n"
        f"Polished report: {report_path}\n"
        f"\n"
        f"## Artifact Files\n"
        f"\n"
        f"protocol_anchors.txt   BLE UUIDs, register constants (static final int/long),\n"
        f"                       device model string literals.  jadx_out → set diff.\n"
        f"\n"
        f"resources.txt          String resources (strings.xml), layout filenames,\n"
        f"                       AndroidManifest permissions/activities/services,\n"
        f"                       version name/code.  apktool_out → set/dict diff.\n"
        f"\n"
        f"cloud_api.txt          HTTP endpoint paths (\"/api/...\"), host/base URLs.\n"
        f"                       jadx_out → set diff.\n"
        f"\n"
        f"Prefixes: + added, - removed, ~ changed\n"
        f"\n"
        f"## Interpretation\n"
        f"\n"
        f"New device support shows additions in all three files.\n"
        f"Feature additions show new strings + new endpoints.\n"
        f"Pure refactoring usually shows protocol-anchor-only changes or no changes.\n"
        f"Version bump with zero feature changes may only show version_code in resources.\n"
    )
    (out_dir / "AGENTS.md").write_text(agents_md)

    print(f"Diff artifacts written to {out_dir}/")
    print(f"  protocol_anchors.txt  resources.txt  cloud_api.txt  AGENTS.md")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: diff_apk.py <verA> <verB>", file=sys.stderr)
        sys.exit(1)

    ver_a, ver_b = sys.argv[1], sys.argv[2]
    bluetti_files = Path("bluetti-files")
    out_dir = bluetti_files / "diff" / f"{ver_a}-vs-{ver_b}"
    diff_apk(bluetti_files, ver_a, ver_b, out_dir)
