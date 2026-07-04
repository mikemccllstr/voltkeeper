# ABOUTME: Prompt metadata for ground-truth operator prompts — shared V2-family table with per-model overrides.
# ABOUTME: Terminology: "the Bluetti unit" = power station, "your appliance" / "the load" = things plugged into it.

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, unique
from typing import Any


@unique
class Affect(Enum):
    """Effect classification for a writable field.

    LOAD — interrupts power to connected appliances.
    UNIT — changes the Bluetti unit's own behaviour or display only.
    NOT_VISIBLE — no observable effect on the device UI.
    """

    LOAD = "load"
    UNIT = "unit"
    NOT_VISIBLE = "not_visible"


@dataclass
class FieldPromptInfo:
    """Prompt metadata for a single writable or observable field."""

    friendly_name: str
    affects: Affect
    watch_for: str
    caution: str | None = None
    where: str | None = None
    is_generic: bool = False


# The settings-page (P0x) references below are verified against two V2 models
# whose manuals agree: EL100V2 (user manual V2.1) and AC2A (V3.0) — P01 Frequency,
# P03 Charging Mode, P05 ECO Mode. They are asserted for the whole V2 family by
# inheritance; the other V2 models (AC180, AC60, EL30V2, EL10V2, EL400, EP600) are
# NOT manual-checked. Verify page numbers against a model's own manual before
# relying on them, and add a device FIELD_PROMPT_OVERRIDES entry where they differ.
V2_FIELD_PROMPTS: dict[str, FieldPromptInfo] = {
    "ac_output": FieldPromptInfo(
        friendly_name="the AC outlets",
        affects=Affect.LOAD,
        watch_for=(
            "the AC icon on the Bluetti unit's main screen goes dark when off "
            "and any appliance plugged into the AC outlets loses power"
        ),
    ),
    "dc_output": FieldPromptInfo(
        friendly_name="the DC ports (car socket / USB)",
        affects=Affect.LOAD,
        watch_for=(
            "the DC icon on the Bluetti unit's main screen goes dark when off "
            "and any device plugged into the DC ports loses power"
        ),
    ),
    "ac_eco_mode": FieldPromptInfo(
        friendly_name="AC ECO mode",
        affects=Affect.UNIT,
        watch_for="the ECO icon appears or disappears on the Bluetti unit's main screen",
        # On the device, settings page P05 toggles AC-ECO and DC-ECO together;
        # controlling them separately is possible only from the BLUETTI app.
        where="settings page P05 (ECO Mode — toggles AC and DC ECO together on-device)",
    ),
    "dc_eco_mode": FieldPromptInfo(
        friendly_name="DC ECO mode",
        affects=Affect.UNIT,
        watch_for="the ECO icon appears or disappears on the Bluetti unit's main screen",
        # See ac_eco_mode: the device has a single ECO page; per-mode control is app-only.
        where="settings page P05 (ECO Mode — toggles AC and DC ECO together on-device)",
    ),
    "ctrl_grid": FieldPromptInfo(
        friendly_name="grid charging",
        affects=Affect.UNIT,
        watch_for=("the GRID icon appears or disappears on the Bluetti unit's main screen and the input watts change"),
    ),
    "ctrl_feed": FieldPromptInfo(
        friendly_name="grid feedback (feed-in)",
        affects=Affect.UNIT,
        watch_for=(
            "the feedback icon appears or disappears on the Bluetti unit's main screen and the output direction changes"
        ),
    ),
    "charging_mode": FieldPromptInfo(
        friendly_name="the charging speed mode",
        affects=Affect.UNIT,
        watch_for=(
            "if Turbo: a Turbo icon appears on the main screen and the fan speeds up. "
            "Standard vs. Silent: only distinguishable on settings page P03 "
            "(Settings Mode page)"
        ),
        where="settings page P03",
    ),
    "working_mode": FieldPromptInfo(
        friendly_name="the operating mode (UPS / Standard)",
        affects=Affect.UNIT,
        watch_for="the operating mode indicator on the Bluetti unit's main screen changes",
    ),
    "alarm_sound": FieldPromptInfo(
        friendly_name="the alarm sound (beep)",
        affects=Affect.UNIT,
        watch_for="the beep on button-press stops or resumes on the Bluetti unit",
    ),
    "inv_freq": FieldPromptInfo(
        friendly_name="the AC output frequency (50 Hz / 60 Hz)",
        affects=Affect.UNIT,
        watch_for="the 50 Hz / 60 Hz indicator on the Bluetti unit's main screen changes",
        # Verbatim from the EL100V2 user manual V2.1 §5.1 (AC2A V3.0 §9.3 says the same:
        # frequency can only be switched while AC output is off). The manuals give no
        # further appliance-damage/unplug wording for this setting.
        caution="Turn off AC output before setting the frequency.",
        where="settings page P01",
    ),
    "power_lifting": FieldPromptInfo(
        friendly_name="power lifting mode",
        affects=Affect.UNIT,
        watch_for="the power lifting icon appears or disappears on the Bluetti unit's main screen",
    ),
    "ctrl_led": FieldPromptInfo(
        friendly_name="the LED light",
        affects=Affect.UNIT,
        watch_for="the LED light on the Bluetti unit turns on or off",
    ),
}


def resolve_field_prompt_info(
    field_name: str,
    overrides: dict[str, FieldPromptInfo],
) -> FieldPromptInfo:
    """Resolve prompt metadata for a field: device override → shared table → generated fallback.

    Device overrides (FIELD_PROMPT_OVERRIDES on the device class) take precedence
    over the shared V2_FIELD_PROMPTS table. Fields absent from both sources get
    a generated entry flagged as generic.
    """
    if field_name in overrides:
        return overrides[field_name]

    if field_name in V2_FIELD_PROMPTS:
        return V2_FIELD_PROMPTS[field_name]

    return FieldPromptInfo(
        friendly_name=f'"{field_name}"',
        affects=Affect.UNIT,
        watch_for=f"the effect of {field_name} on the Bluetti unit's display",
        is_generic=True,
    )


def get_field_prompt_info(
    device: Any,
    field_name: str,
) -> FieldPromptInfo:
    """Resolve prompt metadata for a field on a specific device.

    Looks up FIELD_PROMPT_OVERRIDES on the device class if present, then
    falls back to resolve_field_prompt_info.
    """
    overrides: dict[str, FieldPromptInfo] = getattr(device, "FIELD_PROMPT_OVERRIDES", None) or {}
    return resolve_field_prompt_info(field_name, overrides)
