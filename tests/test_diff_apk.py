# ABOUTME: Unit tests for the diff_apk extraction and comparison functions.
# ABOUTME: Uses small fixture directories that mimic jadx_out and apktool_out structure.

import subprocess
from pathlib import Path

import pytest
from diff_apk import (
    compare_sets,
    extract_ble_uuids,
    extract_device_models,
    extract_http_endpoints,
    extract_http_hosts,
    extract_layout_inventory,
    extract_manifest_info,
    extract_register_constants,
    extract_string_resources,
)

TASKS_DIR = Path(__file__).parent.parent / ".mise" / "tasks"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def jadx_dir(tmp_path):
    """Minimal jadx_out/sources tree with one Java file per extraction concern."""
    sources = tmp_path / "sources" / "com" / "example"
    sources.mkdir(parents=True)

    (sources / "BluetoothService.java").write_text(
        "public class BluetoothService {\n"
        '    private static final String SERVICE_UUID = "0000ff00-0000-1000-8000-00805f9b34fb";\n'
        '    private static final String NOTIFY_UUID = "0000ff01-0000-1000-8000-00805f9b34fb";\n'
        '    private static final String WRITE_UUID = "0000ff02-0000-1000-8000-00805f9b34fb";\n'
        "}\n"
    )

    (sources / "DeviceModel.java").write_text(
        "public enum DeviceModel {\n"
        '    AC2A("AC2A", 20),\n'
        '    EP500("EP500", 5),\n'
        '    EB3A("EB3A", 30);\n'
        "    private final String code;\n"
        "    private final int number;\n"
        "}\n"
    )

    (sources / "RegisterMap.java").write_text(
        "public class RegisterMap {\n"
        "    public static final int APP_HOME_DATA = 100;\n"
        "    public static final int INV_BASE_INFO = 1100;\n"
        "    public static final int INV_PV_INFO = 1200;\n"
        "    public static final int INV_BASE_SETTINGS = 2000;\n"
        "}\n"
    )

    (sources / "ApiService.java").write_text(
        "public interface ApiService {\n"
        '    @GET("/api/blusmartprod/device/basic/v1/findDeviceByBluetooth")\n'
        "    Call<Result> findDevice();\n"
        '    @POST("/api/midpmdata/app/version/v1/android/apk/latest")\n'
        "    Call<Result> latestApk();\n"
        "}\n"
    )

    (sources / "EnvManager.java").write_text(
        "public class EnvManager {\n"
        '    private static final String PROD_URL = "https://gw.bluettipower.com";\n'
        '    private static final String TEST_URL = "https://test-gw.poweroak.ltd:18443";\n'
        '    private static final String MQTT_URL = "ssl://iot.bluettipower.com:18760";\n'
        "}\n"
    )

    return tmp_path


@pytest.fixture()
def apktool_dir(tmp_path):
    """Minimal apktool_out tree with AndroidManifest, strings.xml, and res directories."""
    # apktool.yml with version info
    (tmp_path / "apktool.yml").write_text(
        "!!brut.androlib.meta.MetaInfo\nversionInfo:\n  versionCode: '1415'\n  versionName: 3.0.9\n"
    )

    # AndroidManifest.xml with permissions and activities
    (tmp_path / "AndroidManifest.xml").write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<manifest xmlns:android="http://schemas.android.com/apk/res/android"'
        ' package="net.poweroak.bluetticloud">\n'
        '    <uses-permission android:name="android.permission.BLUETOOTH"/>\n'
        '    <uses-permission android:name="android.permission.INTERNET"/>\n'
        "    <application>\n"
        '        <activity android:name=".MainActivity"/>\n'
        '        <activity android:name=".DeviceActivity"/>\n'
        '        <service android:name=".BleService"/>\n'
        "    </application>\n"
        "</manifest>\n"
    )

    # String resources
    res_values = tmp_path / "res" / "values"
    res_values.mkdir(parents=True)
    (res_values / "strings.xml").write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n'
        "<resources>\n"
        '    <string name="app_name">BLUETTI</string>\n'
        '    <string name="device_ac2a">AC2A Power Station</string>\n'
        '    <string name="battery_level">Battery Level</string>\n'
        "</resources>\n"
    )

    # Layout files
    layouts = tmp_path / "res" / "layout"
    layouts.mkdir(parents=True)
    (layouts / "activity_main.xml").write_text("<LinearLayout/>")
    (layouts / "fragment_device.xml").write_text("<FrameLayout/>")

    # Drawable and mipmap files
    drawable = tmp_path / "res" / "drawable"
    drawable.mkdir(parents=True)
    (drawable / "ic_battery.xml").write_text("<vector/>")
    (drawable / "ic_solar.xml").write_text("<vector/>")

    mipmap = tmp_path / "res" / "mipmap-hdpi"
    mipmap.mkdir(parents=True)
    (mipmap / "ic_launcher.png").write_bytes(b"\x89PNG")

    return tmp_path


# ---------------------------------------------------------------------------
# Protocol-anchor extraction (from jadx_out)
# ---------------------------------------------------------------------------


def test_extract_ble_uuids(jadx_dir):
    uuids = extract_ble_uuids(jadx_dir)

    assert "0000ff00-0000-1000-8000-00805f9b34fb" in uuids
    assert "0000ff01-0000-1000-8000-00805f9b34fb" in uuids
    assert "0000ff02-0000-1000-8000-00805f9b34fb" in uuids


def test_extract_ble_uuids_empty_dir(tmp_path):
    assert extract_ble_uuids(tmp_path) == set()


def test_extract_register_constants(jadx_dir):
    constants = extract_register_constants(jadx_dir)

    assert ("APP_HOME_DATA", 100) in constants
    assert ("INV_BASE_INFO", 1100) in constants
    assert ("INV_PV_INFO", 1200) in constants
    assert ("INV_BASE_SETTINGS", 2000) in constants


def test_extract_register_constants_empty_dir(tmp_path):
    assert extract_register_constants(tmp_path) == set()


def test_extract_device_models(jadx_dir):
    models = extract_device_models(jadx_dir)

    assert "AC2A" in models
    assert "EP500" in models
    assert "EB3A" in models


def test_extract_device_models_empty_dir(tmp_path):
    assert extract_device_models(tmp_path) == set()


# ---------------------------------------------------------------------------
# Resource/UI-surface extraction (from apktool_out)
# ---------------------------------------------------------------------------


def test_extract_string_resources(apktool_dir):
    strings = extract_string_resources(apktool_dir)

    assert strings.get("app_name") == "BLUETTI"
    assert strings.get("device_ac2a") == "AC2A Power Station"
    assert strings.get("battery_level") == "Battery Level"


def test_extract_string_resources_missing(tmp_path):
    assert extract_string_resources(tmp_path) == {}


def test_extract_layout_inventory(apktool_dir):
    layouts = extract_layout_inventory(apktool_dir)

    assert "activity_main.xml" in layouts
    assert "fragment_device.xml" in layouts


def test_extract_layout_inventory_missing(tmp_path):
    assert extract_layout_inventory(tmp_path) == set()


def test_extract_manifest_info_permissions(apktool_dir):
    info = extract_manifest_info(apktool_dir)

    assert "android.permission.BLUETOOTH" in info["permissions"]
    assert "android.permission.INTERNET" in info["permissions"]


def test_extract_manifest_info_version(apktool_dir):
    info = extract_manifest_info(apktool_dir)

    assert info["version_name"] == "3.0.9"
    assert info["version_code"] == "1415"


def test_extract_manifest_info_components(apktool_dir):
    info = extract_manifest_info(apktool_dir)

    assert ".MainActivity" in info["activities"]
    assert ".DeviceActivity" in info["activities"]
    assert ".BleService" in info["services"]


def test_extract_manifest_info_missing(tmp_path):
    info = extract_manifest_info(tmp_path)

    assert info["permissions"] == set()
    assert info["activities"] == set()
    assert info["services"] == set()


# ---------------------------------------------------------------------------
# Backend/cloud API extraction (from jadx_out)
# ---------------------------------------------------------------------------


def test_extract_http_endpoints(jadx_dir):
    endpoints = extract_http_endpoints(jadx_dir)

    assert "/api/blusmartprod/device/basic/v1/findDeviceByBluetooth" in endpoints
    assert "/api/midpmdata/app/version/v1/android/apk/latest" in endpoints


def test_extract_http_endpoints_empty_dir(tmp_path):
    assert extract_http_endpoints(tmp_path) == set()


def test_extract_http_hosts(jadx_dir):
    hosts = extract_http_hosts(jadx_dir)

    assert "https://gw.bluettipower.com" in hosts
    assert "https://test-gw.poweroak.ltd:18443" in hosts
    assert "ssl://iot.bluettipower.com:18760" in hosts


def test_extract_http_hosts_empty_dir(tmp_path):
    assert extract_http_hosts(tmp_path) == set()


# ---------------------------------------------------------------------------
# compare_sets helper
# ---------------------------------------------------------------------------


def test_compare_sets_added_removed_unchanged():
    a = {"x", "y", "z"}
    b = {"y", "z", "w"}
    result = compare_sets(a, b)

    assert result["added"] == {"w"}
    assert result["removed"] == {"x"}
    assert result["unchanged"] == {"y", "z"}


def test_compare_sets_identical():
    s = {"a", "b"}
    result = compare_sets(s, s)

    assert result["added"] == set()
    assert result["removed"] == set()
    assert result["unchanged"] == s


# ---------------------------------------------------------------------------
# diff-apk task: missing-version guard
# ---------------------------------------------------------------------------


def _run_diff_apk(args, cwd):
    script = TASKS_DIR / "diff-apk"
    return subprocess.run(
        [str(script), *args],
        capture_output=True,
        text=True,
        cwd=cwd,
    )


def test_diff_apk_exits_nonzero_when_version_not_decompiled(tmp_path):
    # Stage an APK but do NOT decompile it (no jadx_out/apktool_out)
    ver_dir = tmp_path / "bluetti-files" / "BLUETTI-v3.0.9.apk"
    ver_dir.mkdir(parents=True)
    (ver_dir / "bluetti.apk").write_bytes(b"PK")

    result = _run_diff_apk(["3.0.9", "3.0.10"], cwd=tmp_path)

    assert result.returncode != 0
    combined = result.stdout + result.stderr
    # Should name which version is missing
    assert "3.0.9" in combined or "3.0.10" in combined
