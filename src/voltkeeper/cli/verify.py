# ABOUTME: CLI verify command — run a six-tier integration test against a Bluetti device.

import asyncio

import click

from voltkeeper.bluetooth import lookup_scan_result
from voltkeeper.bluetooth.client import BluetoothClient
from voltkeeper.cli import cli
from voltkeeper.cli._helpers import _close_loop, _device_from_scan


@cli.command()
@click.argument("address")
@click.option(
    "-o",
    "--output",
    default=None,
    help="Output YAML file (default: hardware-data/{verify|verify-ground-truth}_MODEL_YYYY-MM-DDTHHMMZ.yaml)",
)
@click.option("--tier", "max_tier", default=6, type=int, help="Run through this tier only (1–6).")
@click.option("--yes", "pre_consent", is_flag=True, default=False, help="Pre-consent to all supervised tiers.")
@click.option("--no-scrub", "no_scrub", is_flag=True, default=False, help="Keep real SN and BLE address in report.")
@click.option(
    "--ground-truth",
    is_flag=True,
    default=False,
    help="Attended mode: prompts operator to compare device-screen values against parsed registers.",
)
@click.option(
    "--skip-category",
    "skip_categories",
    multiple=True,
    type=click.Choice(["observations", "load_actuations", "mode_actuations", "induced"]),
    help="Skip a ground-truth category (repeatable). Pre-answers the interactive menu.",
)
def verify(
    address: str,
    output: str | None,
    max_tier: int,
    pre_consent: bool,
    no_scrub: bool,
    ground_truth: bool,
    skip_categories: tuple[str, ...] = (),
) -> None:
    """Run a six-tier integration test against a Bluetti device.

    \b
    Tiers 1-3 run automatically (read, identity writes, probe writes).
    Tiers 4-6 prompt before running (load toggles, mode changes, irreversible).

    \b
    The output YAML report is safe to share in a GitHub issue:
      https://github.com/mikemccllstr/voltkeeper/issues
    """
    import datetime

    from voltkeeper.core.verify import (
        TierResult,
        build_tier_plan,
        run_tier1,
        run_tier2,
        run_tier3,
        run_tier_supervised,
    )

    if pre_consent and ground_truth:
        raise click.UsageError("--yes and --ground-truth are mutually exclusive.")

    session_start = datetime.datetime.now(datetime.timezone.utc)

    TIER_DESCRIPTIONS = {
        4: "load-affecting toggles (ac_output, dc_output, ctrl_grid, ctrl_feed, power_lifting, eco_mode)",
        5: "operating mode changes (working_mode, ups_mode)",
        6: "IRREVERSIBLE operations (factory_reset, system_power, power_off)",
    }
    TIER_CONSENT_LABEL = {
        4: "pre-granted (--yes)",
        5: "pre-granted (--yes)",
        6: "pre-granted (--yes)",
    }

    address = address.upper()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        sr = loop.run_until_complete(lookup_scan_result(address))
    finally:
        loop.close()

    device = _device_from_scan(sr)
    tier_plan = build_tier_plan(device)

    if output is None:
        from voltkeeper.core.verify import _build_default_output_path

        output = _build_default_output_path(device.type, ground_truth=ground_truth, now=session_start)

    client = BluetoothClient(address, encrypted=sr.encrypted or False)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    tier_results: list[TierResult] = []
    tier1_values: dict = {}
    ground_truth_result = None
    consented_tiers: set[int] = {1, 2, 3}
    selected_categories: frozenset[str] | None = None
    restore_audit: dict | None = None

    def _progress(msg: str) -> None:
        click.echo(msg)

    if ground_truth:
        selected_categories = _resolve_categories(skip_categories)

    try:
        loop.run_until_complete(client.connect())
        click.echo(f"Connected to {device.type} ({address})")

        # ── Tier 1: read & parse ───────────────────────────────────────
        click.echo("Tier 1  reading all blocks ...", nl=False)
        t1, tier1_values = loop.run_until_complete(run_tier1(client, device))
        tier_results.append(t1)
        _print_tier_summary(t1)
        if t1.failure_count and max_tier > 1:
            click.secho(
                f"  ⚠ {t1.failure_count} issue(s) found — consider sharing the report before continuing",
                fg="yellow",
            )
        # ── Ground-truth observations (before writes) ───────────────────
        if ground_truth:
            click.echo("\n── Ground-truth observations ─────────────────────")
            click.echo("Answer questions based on what the device's own display shows.\n")
            gt_obs_result, handoff_ok = loop.run_until_complete(
                _run_handoff_observations(
                    client, device, tier1_values, t1.blocks, selected_categories=selected_categories
                )
            )
            ground_truth_result = gt_obs_result
            if not handoff_ok:
                _skip_remaining(tier_results, tier_plan, 2, "connection lost during app handoff")
                _finish(device, address, tier_results, tier1_values, output, no_scrub, ground_truth_result)
                return
        if max_tier < 2:
            _skip_remaining(tier_results, tier_plan, 2, "tier limit")
            if ground_truth:
                gt_act_result = loop.run_until_complete(
                    _run_ground_truth_actuations(
                        client, device, tier1_values, consented_tiers, selected_categories=selected_categories
                    )
                )
                ground_truth_result = _merge_ground_truth_results(ground_truth_result, gt_act_result)
            restore_audit = _run_restore_audit_sync(loop, client, device, tier1_values, max_tier)
            _finish(device, address, tier_results, tier1_values, output, no_scrub, ground_truth_result, restore_audit)
            return

        # ── Tier 2: identity writes ────────────────────────────────────
        fields2 = tier_plan.get(2, [])
        if fields2:
            click.echo(f"Tier 2  identity writes ({len(fields2)} fields) ...", nl=False)
            t2 = loop.run_until_complete(run_tier2(client, device, tier1_values, fields2, progress=_progress))
        else:
            t2 = TierResult(tier=2, status="pass", reason="no automatic fields")
        tier_results.append(t2)
        _print_tier_summary(t2)
        if t2.failure_count and max_tier > 2:
            click.secho(
                f"  ⚠ {t2.failure_count} issue(s) found — consider sharing the report before continuing",
                fg="yellow",
            )
        if max_tier < 3:
            _skip_remaining(tier_results, tier_plan, 3, "tier limit")
            if ground_truth:
                gt_act_result = loop.run_until_complete(
                    _run_ground_truth_actuations(
                        client, device, tier1_values, consented_tiers, selected_categories=selected_categories
                    )
                )
                ground_truth_result = _merge_ground_truth_results(ground_truth_result, gt_act_result)
            restore_audit = _run_restore_audit_sync(loop, client, device, tier1_values, max_tier)
            _finish(device, address, tier_results, tier1_values, output, no_scrub, ground_truth_result, restore_audit)
            return

        # ── Tier 3: probe writes ───────────────────────────────────────
        fields3 = tier_plan.get(3, [])
        if fields3:
            click.echo(f"Tier 3  probe writes ({len(fields3)} fields) ...", nl=False)
            t3 = loop.run_until_complete(run_tier3(client, device, tier1_values, fields3, progress=_progress))
        else:
            t3 = TierResult(tier=3, status="pass", reason="no automatic fields")
        tier_results.append(t3)
        _print_tier_summary(t3)
        if t3.failure_count and max_tier > 3:
            click.secho(
                f"  ⚠ {t3.failure_count} issue(s) found — consider sharing the report before continuing",
                fg="yellow",
            )

        # ── Tiers 4, 5, 6: supervised ─────────────────────────────────
        consent: str | None = None
        for tier_num in (4, 5, 6):
            if max_tier < tier_num:
                _skip_remaining(tier_results, tier_plan, tier_num, "tier limit")
                continue

            fields = tier_plan.get(tier_num, [])
            if not fields:
                tier_results.append(
                    TierResult(tier=tier_num, status="skipped", reason="no fields at this tier for this device")
                )
                continue

            desc = TIER_DESCRIPTIONS[tier_num]
            if tier_num == 6:
                click.echo(f"\nTier 6  ⚠ IRREVERSIBLE: {desc}")
                if pre_consent:
                    consent = TIER_CONSENT_LABEL[6]
                    proceed = True
                else:
                    typed = click.prompt(
                        '  Type "I understand this is irreversible" to proceed, or Enter to skip',
                        default="",
                    )
                    proceed = typed.strip() == "I understand this is irreversible"
                    consent = "typed confirmation" if proceed else None
            else:
                click.echo(f"\nTier {tier_num}  {desc}")
                if pre_consent:
                    proceed = True
                    consent = TIER_CONSENT_LABEL[tier_num]
                else:
                    proceed = click.confirm("  Continue?", default=False)
                    consent = "user confirmed" if proceed else None

            if not proceed:
                tier_results.append(TierResult(tier=tier_num, status="skipped", reason="user declined"))
                continue

            click.echo(f"  Running tier {tier_num} ({len(fields)} fields) ...", nl=False)
            t = loop.run_until_complete(
                run_tier_supervised(client, device, tier1_values, fields, tier_num, consent=consent, progress=_progress)
            )
            tier_results.append(t)
            _print_tier_summary(t)
            consented_tiers.add(tier_num)
            if t.failure_count and tier_num < 6:
                click.secho(
                    f"  ⚠ {t.failure_count} issue(s) found — consider sharing the report before continuing",
                    fg="yellow",
                )

        # ── Ground-truth actuations ──────────────────────────────────────
        if ground_truth:
            gt_act_result = loop.run_until_complete(
                _run_ground_truth_actuations(
                    client, device, tier1_values, consented_tiers, selected_categories=selected_categories
                )
            )
            ground_truth_result = _merge_ground_truth_results(ground_truth_result, gt_act_result)

        # ── Restore audit ──────────────────────────────────────────────
        restore_audit = _run_restore_audit_sync(loop, client, device, tier1_values, max_tier)

    except KeyboardInterrupt:
        click.echo("\nInterrupted.")
    except Exception as exc:
        click.secho(f"Error: {exc}", fg="red")
    finally:
        loop.run_until_complete(client.disconnect())
        _close_loop(loop)

    _finish(device, address, tier_results, tier1_values, output, no_scrub, ground_truth_result, restore_audit)


def _print_tier_summary(t) -> None:
    total = len(t.blocks) + len(t.fields)
    fails = t.failure_count
    icon = "✓" if t.status in ("pass", "skipped") else "✗"
    status_str = t.status if t.status == "skipped" else f"{total - fails}/{total} ok"
    click.echo(f"  {icon} {status_str}")


def _skip_remaining(
    results: list,
    tier_plan: dict,
    from_tier: int,
    reason: str,
) -> None:
    from voltkeeper.core.verify import TierResult

    for n in range(from_tier, 7):
        if any(t.tier == n for t in results):
            continue
        results.append(TierResult(tier=n, status="skipped", reason=reason))


def _finish(
    device,
    address: str,
    tier_results: list,
    tier1_values: dict,
    output: str,
    no_scrub: bool,
    ground_truth_result=None,
    restore_audit=None,
) -> None:
    from voltkeeper import _version
    from voltkeeper.core.ground_truth import ground_truth_to_report_section
    from voltkeeper.core.verify import _device_bcd_sn_fields, _scrub_block_raw, build_report, write_report

    report = build_report(
        device,
        sn=device.sn,
        address=address,
        tier_results=tier_results,
        tier1_values=tier1_values,
        scrub=not no_scrub,
        voltkeeper_version=_version.__version__,
    )
    if ground_truth_result is not None:
        if not no_scrub:
            # Scrub induced-check raw hex (HOME block, address 100) using the
            # same BCD-serial-field logic as tier-1 blocks.
            sn_fields = _device_bcd_sn_fields(device)
            for ic in ground_truth_result.induced_checks:
                if ic.raw_hex is not None:
                    ic.raw_hex = _scrub_block_raw(ic.raw_hex, 100, sn_fields)
        report["ground_truth"] = ground_truth_to_report_section(ground_truth_result)
    if restore_audit is not None:
        report["restore_audit"] = restore_audit
    actual_path = write_report(report, output)
    click.echo(f"\nReport written to: {actual_path}")
    click.secho(
        "Share this file in a GitHub issue: https://github.com/mikemccllstr/voltkeeper/issues",
        fg="cyan",
    )


async def _run_ground_truth_observations(
    client, device, tier1_values, tier1_blocks, prompt_fn=None, source_override=None, selected_categories=None
):
    """Run the passive observation phase (read-only, no writes).

    Returns a GroundTruthResult containing only observations.
    """
    from voltkeeper.core.ground_truth import (
        GroundTruthResult,
        build_observation_items,
        run_observations,
    )

    result = GroundTruthResult()

    if prompt_fn is None:

        async def _prompt(text: str, source: str) -> str | None:
            return click.prompt(f"  {text}", default="", show_default=False)

        prompt_fn = _prompt

    obs_items = build_observation_items(
        device, tier1_values, source_override=source_override, selected_categories=selected_categories
    )
    if selected_categories is not None and "observations" not in selected_categories:
        result.categories["observations"] = "skipped (operator category selection)"
    if obs_items:
        await run_observations(obs_items, tier1_blocks, device, prompt_fn)
        result.observations = obs_items

    return result


async def _run_ground_truth_actuations(
    client, device, tier1_values, consented_tiers, prompt_fn=None, selected_categories=None
):
    """Run actuate-and-confirm and induced-condition checks (writes are performed).

    Returns a GroundTruthResult containing actuations and induced_checks.
    """
    from voltkeeper.core.ground_truth import (
        GroundTruthResult,
        build_actuation_items,
        run_actuations,
        run_induced_checks,
    )

    result = GroundTruthResult()

    if selected_categories is not None:
        if "load_actuations" not in selected_categories:
            result.categories["load_actuations"] = "skipped (operator category selection)"
        if "mode_actuations" not in selected_categories:
            result.categories["mode_actuations"] = "skipped (operator category selection)"
        if "induced" not in selected_categories:
            result.categories["induced"] = "skipped (operator category selection)"

    if prompt_fn is None:

        async def _prompt(text: str, source: str) -> str | None:
            return click.prompt(f"  {text}", default="", show_default=False)

        prompt_fn = _prompt

    act_items = build_actuation_items(device, tier1_values, consented_tiers, selected_categories=selected_categories)
    if act_items:
        await run_actuations(act_items, client, device, tier1_values, prompt_fn)
        result.actuations = act_items

    induced = await run_induced_checks(client, device, prompt_fn, selected_categories=selected_categories)
    if induced:
        result.induced_checks = induced

    return result


def _merge_ground_truth_results(obs_result, act_result):
    """Merge observation and actuation GroundTruthResults into one.

    Either result may be None.
    """
    from voltkeeper.core.ground_truth import GroundTruthResult

    if obs_result is None and act_result is None:
        return None
    merged = GroundTruthResult()
    if obs_result is not None:
        merged.observations = obs_result.observations
        if obs_result.categories:
            merged.categories.update(obs_result.categories)
    if act_result is not None:
        merged.actuations = act_result.actuations
        merged.induced_checks = act_result.induced_checks
        if act_result.categories:
            merged.categories.update(act_result.categories)
    return merged


async def _run_handoff_observations(
    client,
    device,
    tier1_values,
    tier1_blocks,
    prompt_fn=None,
    retry_connect=3,
    _echo=None,
    _confirm=None,
    _prompt=None,
    selected_categories=None,
):
    """Run the observation phase with BLE handoff for app-based readings.

    1. Disconnect BLE so the vendor app can take the connection.
    2. Invite the operator to connect the vendor app (or proceed LCD-only).
    3. Run passive observations with the supplied prompt_fn.
    4. Instruct the operator to return the app to its device list.
    5. Reconnect BLE with a retry loop; returns observations even on failure.

    Returns (GroundTruthResult, reconnected: bool).
    _echo, _confirm, _prompt: test hooks (when absent, click.echo/confirm/prompt are used).
    """
    echo = _echo if _echo is not None else click.echo
    confirm = _confirm if _confirm is not None else click.confirm
    cprompt = _prompt if _prompt is not None else click.prompt

    # Skip handoff entirely when observations category is deselected
    if selected_categories is not None and "observations" not in selected_categories:
        from voltkeeper.core.ground_truth import GroundTruthResult

        result = GroundTruthResult()
        result.categories["observations"] = "skipped (operator category selection)"
        return result, True

    await client.disconnect()
    echo("BLE connection released.")

    echo(
        "\nConnect the BLUETTI app to the device now.\n"
        "For each question the app reading is preferred — voltkeeper will show\n"
        "what it parsed so you can compare."
    )
    use_app = confirm("Is the app connected to the device?", default=True)
    if use_app:
        observation_source = "app_live"
    else:
        echo("Proceeding with LCD-screen / multimeter observations.")
        # No override: on-screen fields keep their native device_screen source,
        # off-screen fields keep multimeter — the app is not available to promote.
        observation_source = None

    if prompt_fn is None:

        async def _default_prompt(text: str, source: str) -> str | None:
            return cprompt(f"  {text}", default="", show_default=False)

        prompt_fn = _default_prompt

    result = await _run_ground_truth_observations(
        client,
        device,
        tier1_values,
        tier1_blocks,
        prompt_fn=prompt_fn,
        source_override=observation_source,
        selected_categories=selected_categories,
    )

    if use_app:
        echo("\nReturn the BLUETTI app to its device list to release the connection.")
        cprompt("Press Enter when ready", default="", show_default=False)

    for attempt in range(1, retry_connect + 1):
        try:
            await client.connect()
            echo("Reconnected to device.")
            return result, True
        except Exception as exc:
            echo(f"  Reconnect attempt {attempt} failed: {exc}")
            if attempt < retry_connect:
                cprompt(
                    "  Make sure the app has disconnected, then press Enter to retry",
                    default="",
                    show_default=False,
                )
            else:
                echo("  Could not reconnect. Tier-1 and observations are preserved;\n  tiers 2+ will be skipped.")
    return result, False


VALID_CATEGORIES = frozenset({"observations", "load_actuations", "mode_actuations", "induced"})


def _resolve_categories(skip_categories: tuple[str, ...]) -> frozenset[str]:
    """Build selected-categories set from interactive menu and/or CLI flags.

    When skip_categories is non-empty the menu is skipped.
    Returns a frozenset of selected category names.
    """
    if skip_categories:
        return _categories_from_skips(list(skip_categories))

    # Interactive menu
    click.echo("\nGround-truth categories (all enabled by default):")
    categories = []
    labels = [
        ("observations", "Passive observations (screen readings)"),
        ("load_actuations", "Output & load actuations"),
        ("mode_actuations", "Operating mode changes"),
        ("induced", "Induced conditions (e.g. overload test)"),
    ]
    for name, desc in labels:
        if click.confirm(f"  Include {desc}?", default=True):
            categories.append(name)

    if not categories:
        click.echo("  No categories selected — ground-truth will have nothing to test.")
    return frozenset(categories)


def _run_restore_audit_sync(loop, client, device, tier1_values, max_tier) -> dict | None:
    """Run the restore audit if max_tier >= 2, otherwise record not_applicable."""
    from voltkeeper.core.verify import _print_restore_audit, _run_restore_audit_or_note

    audit = _run_restore_audit_or_note(loop, client, device, tier1_values, max_tier)
    _print_restore_audit(audit)
    return audit


def _categories_from_skips(skips: list[str]) -> frozenset[str]:
    """Convert --skip-category values to an enabled-categories set."""
    if any(s not in VALID_CATEGORIES for s in skips):
        raise ValueError(f"unknown category in {skips}")
    default = set(VALID_CATEGORIES)
    for name in skips:
        default.discard(name)
    return frozenset(default)
