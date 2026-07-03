# ABOUTME: CLI verify command — run a six-tier integration test against a Bluetti device.

import asyncio

import click

from voltkeeper.bluetooth import lookup_scan_result
from voltkeeper.bluetooth.client import BluetoothClient
from voltkeeper.cli import cli
from voltkeeper.cli._helpers import _close_loop, _device_from_scan


@cli.command()
@click.argument("address")
@click.option("-o", "--output", default=None, help="Output YAML file (default: hardware-data/verify-MODEL-DATE.yaml)")
@click.option("--tier", "max_tier", default=6, type=int, help="Run through this tier only (1–6).")
@click.option("--yes", "pre_consent", is_flag=True, default=False, help="Pre-consent to all supervised tiers.")
@click.option("--no-scrub", "no_scrub", is_flag=True, default=False, help="Keep real SN and BLE address in report.")
def verify(address: str, output: str | None, max_tier: int, pre_consent: bool, no_scrub: bool) -> None:
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
        today = datetime.date.today().isoformat()
        output = f"hardware-data/verify-{device.type}-{today}.yaml"

    client = BluetoothClient(address, encrypted=sr.encrypted or False)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    tier_results: list[TierResult] = []
    tier1_values: dict = {}

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
        if max_tier < 2:
            _skip_remaining(tier_results, tier_plan, 2, "tier limit")
            _finish(device, address, tier_results, tier1_values, output, no_scrub)
            return

        # ── Tier 2: identity writes ────────────────────────────────────
        fields2 = tier_plan.get(2, [])
        if fields2:
            click.echo(f"Tier 2  identity writes ({len(fields2)} fields) ...", nl=False)
            t2 = loop.run_until_complete(run_tier2(client, device, tier1_values, fields2))
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
            _finish(device, address, tier_results, tier1_values, output, no_scrub)
            return

        # ── Tier 3: probe writes ───────────────────────────────────────
        fields3 = tier_plan.get(3, [])
        if fields3:
            click.echo(f"Tier 3  probe writes ({len(fields3)} fields) ...", nl=False)
            t3 = loop.run_until_complete(run_tier3(client, device, tier1_values, fields3))
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
                run_tier_supervised(client, device, tier1_values, fields, tier_num, consent=consent)
            )
            tier_results.append(t)
            _print_tier_summary(t)
            if t.failure_count and tier_num < 6:
                click.secho(
                    f"  ⚠ {t.failure_count} issue(s) found — consider sharing the report before continuing",
                    fg="yellow",
                )

    except KeyboardInterrupt:
        click.echo("\nInterrupted.")
    except Exception as exc:
        click.secho(f"Error: {exc}", fg="red")
    finally:
        loop.run_until_complete(client.disconnect())
        _close_loop(loop)

    _finish(device, address, tier_results, tier1_values, output, no_scrub)


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
) -> None:
    from voltkeeper import _version
    from voltkeeper.core.verify import build_report, write_report

    report = build_report(
        device,
        sn=device.sn,
        address=address,
        tier_results=tier_results,
        tier1_values=tier1_values,
        scrub=not no_scrub,
        voltkeeper_version=_version.__version__,
    )
    write_report(report, output)
    click.echo(f"\nReport written to: {output}")
    click.secho(
        "Share this file in a GitHub issue: https://github.com/mikemccllstr/voltkeeper/issues",
        fg="cyan",
    )
