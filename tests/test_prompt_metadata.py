# ABOUTME: Tests for prompt-metadata resolution — shared table, device overrides, fallback generation.
# ABOUTME: Exercises FieldPromptInfo dataclass, V2_FIELD_PROMPTS, and resolve_field_prompt_info().
# ruff: noqa: I001

from voltkeeper.core.prompt_metadata import Affect, FieldPromptInfo, V2_FIELD_PROMPTS, resolve_field_prompt_info


class TestFieldPromptInfo:
    def test_minimal_construction(self):
        info = FieldPromptInfo(
            friendly_name="the AC outlets",
            affects=Affect.LOAD,
            watch_for="the AC icon goes dark",
        )
        assert info.friendly_name == "the AC outlets"
        assert info.affects == Affect.LOAD
        assert info.watch_for == "the AC icon goes dark"
        assert info.caution is None
        assert info.where is None

    def test_full_construction(self):
        info = FieldPromptInfo(
            friendly_name="the AC output frequency",
            affects=Affect.UNIT,
            watch_for="the frequency indicator changes",
            caution="Turn off AC output before setting the frequency",
            where="settings page P05",
        )
        assert info.caution == "Turn off AC output before setting the frequency"
        assert info.where == "settings page P05"


class TestSharedTable:
    def test_table_is_dict_of_fieldpromptinfo(self):
        assert isinstance(V2_FIELD_PROMPTS, dict)
        for key, value in V2_FIELD_PROMPTS.items():
            assert isinstance(key, str)
            assert isinstance(value, FieldPromptInfo)

    def test_known_fields_present(self):
        """Core fields that are actuated or observed should have entries."""
        essential = {
            "ac_output",
            "dc_output",
            "charging_mode",
            "inv_freq",
        }
        present = set(V2_FIELD_PROMPTS.keys())
        missing = essential - present
        assert not missing, f"Missing shared metadata entries: {missing}"


class TestResolveFieldPromptInfo:
    """Tests for the resolution function: device override → shared → fallback."""

    def test_shared_entry_returned_by_default(self):
        """When no device override exists, the shared table entry is returned."""
        overrides: dict[str, FieldPromptInfo] = {}
        info = resolve_field_prompt_info("ac_output", overrides)
        assert info is V2_FIELD_PROMPTS["ac_output"]
        assert info.friendly_name is not None

    def test_device_override_wins_over_shared(self):
        """When a device declares an override, it takes precedence."""
        override = FieldPromptInfo(
            friendly_name="the custom AC output",
            affects=Affect.LOAD,
            watch_for="something different",
            where="custom page",
        )
        overrides = {"ac_output": override}
        info = resolve_field_prompt_info("ac_output", overrides)
        assert info is override
        assert info.friendly_name == "the custom AC output"
        assert info.where == "custom page"

    def test_override_only_affects_specified_key(self):
        """An override for one field does not affect others."""
        override = FieldPromptInfo(
            friendly_name="custom DC",
            affects=Affect.LOAD,
            watch_for="custom DC change",
        )
        overrides = {"dc_output": override}
        info = resolve_field_prompt_info("ac_output", overrides)
        assert info is V2_FIELD_PROMPTS["ac_output"]

    def test_unknown_field_yields_generic_fallback(self):
        """A field absent from both sources gets a generated entry flagged generic."""
        overrides: dict[str, FieldPromptInfo] = {}
        info = resolve_field_prompt_info("some_unknown_field", overrides)
        assert info.is_generic is True
        assert "some_unknown_field" in info.friendly_name.lower()
        assert info.affects == Affect.UNIT
        assert info.watch_for is not None

    def test_unknown_field_with_override_not_generic(self):
        """An unknown field with a device override is NOT flagged generic."""
        override = FieldPromptInfo(
            friendly_name="custom field",
            affects=Affect.UNIT,
            watch_for="custom watch",
        )
        overrides = {"custom_thing": override}
        info = resolve_field_prompt_info("custom_thing", overrides)
        assert info is override
        assert info.is_generic is False

    def test_affects_enum_values(self):
        assert Affect.LOAD.value == "load"
        assert Affect.UNIT.value == "unit"
        assert Affect.NOT_VISIBLE.value == "not_visible"


class TestRatedACOutput:
    """Tests for RATED_AC_OUTPUT_W on device classes."""

    def test_el100v2_rated_ac_output(self):
        """EL100V2 should expose rated AC output 1800 W from the user manual."""
        from voltkeeper.core.devices.el100v2 import El100V2

        device = El100V2("AA:BB:CC:DD:EE:FF", "0")
        assert device.RATED_AC_OUTPUT_W == 1800

    def test_ac2a_rated_ac_output(self):
        """AC2A should expose rated AC output 300 W from the user manual."""
        from voltkeeper.core.devices.ac2a import AC2A

        device = AC2A("AA:BB:CC:DD:EE:FF", "0")
        assert device.RATED_AC_OUTPUT_W == 300

    def test_base_device_has_none_by_default(self):
        """A device class without a declared rating should have RATED_AC_OUTPUT_W = None."""
        from voltkeeper.core.devices.bluetti_device import BluettiDevice

        assert BluettiDevice.RATED_AC_OUTPUT_W is None


class TestDeviceOverridesApplied:
    """Real per-model FIELD_PROMPT_OVERRIDES resolve against the shared table."""

    def test_ac2a_charging_mode_override_reflects_app_only_modes(self):
        """AC2A exposes only Turbo on-device; Standard/Silent are app-only."""
        from voltkeeper.core.devices.ac2a import AC2A
        from voltkeeper.core.prompt_metadata import get_field_prompt_info

        info = get_field_prompt_info(AC2A("AA:BB:CC:DD:EE:FF", "0"), "charging_mode")
        assert info is not V2_FIELD_PROMPTS["charging_mode"]
        assert "app" in info.watch_for.lower()
        assert "P03" in info.where

    def test_el100v2_charging_mode_uses_shared_entry(self):
        """EL100V2 has no charging_mode override, so it gets the shared table entry."""
        from voltkeeper.core.devices.el100v2 import El100V2
        from voltkeeper.core.prompt_metadata import get_field_prompt_info

        info = get_field_prompt_info(El100V2("AA:BB:CC:DD:EE:FF", "0"), "charging_mode")
        assert info is V2_FIELD_PROMPTS["charging_mode"]
