# Voltkeeper brand assets — design notes

This document describes the two SVG assets that make up the Voltkeeper visual
identity, the reasoning behind their construction, and the knobs a future
artist can turn to adjust them.

## Assets

| File | Purpose | Native viewBox |
|---|---|---|
| `voltkeeper-shield.svg` | The icon mark. Square-ish shield with a lightning bolt flanked by two battery stacks. Use anywhere the project needs a compact symbol: app icons, favicons, README headers, GitHub social cards, terminal banner art. | `0 0 200 215` |
| `voltkeeper-wordmark.svg` | The wordmark. The literal word "voltkeeper" with the "volt" half in amber and the "keeper" half adopting the surrounding text color. | `0 0 380 100` |

Both files are standalone — open in any browser or vector editor without
modification. They render correctly with `width="100%"` inside any container,
or with explicit pixel dimensions.

## Design intent

The two halves of the name map to two halves of the mark:

- **"keeper"** → the **shield**. A heater-style silhouette evokes guardianship,
  protection, and UPS-like stewardship. This matches the project's identity as
  something that watches over power stations and the hosts depending on them.
- **"volt"** → the **lightning bolt and battery cells** inside the shield. The
  bolt is the universal electrical glyph; the cell stacks suggest a battery
  bank rather than a single device, hinting at the project's multi-device
  support and aspirational multi-vendor future.

Color is intentionally restricted to two values: a deep slate (`#0F172A`) for
the shield, and an amber yellow (`#FACC15` for the bolt and cells, `#EAB308`
for the wordmark) for everything else. No gradients, no drop shadows, no
glows — the mark should reproduce cleanly at any size, including monochrome
print and embroidery.

The amber-on-slate palette is reminiscent of high-visibility electrical
warning signage without being literally hazard-themed, and the warm yellow
distinguishes the project from the cooler blue/teal palette that dominates
the EV-charging and consumer-power-station space (Tesla, EcoFlow, Anker
Solix, etc.).

## Shield (`voltkeeper-shield.svg`)

### Anatomy

The SVG is drawn in four layers, in this order:

1. **Outer shield silhouette** (filled, slate `#0F172A`). This is the dark
   background everything else sits on.
2. **Lightning bolt** (filled, amber `#FACC15`). Pointed at both top and
   bottom. Centered horizontally; the upper point sits near the top of the
   inner border, the lower point sits near the bottom.
3. **Two battery stacks** (amber strokes and small terminal-cap fills),
   placed symmetrically on either side of the bolt. Each stack has two
   upright cells with positive terminals on top.
4. **Inner shield outline** (3px amber stroke, no fill). This is drawn
   **last on purpose** — if any cell or bolt vertex ever drifts close to the
   border, the outline rides cleanly on top and is never visually cut off by
   the elements behind it. If you reposition anything inside the shield,
   keep the outline last in source order.

### Coordinate system

The shield uses a `200 × 215` viewBox. Origin is top-left. The shield
silhouette occupies the full viewBox; the inner outline is inset 14px on the
top and sides and tapers to a point at `(100, 200)`. The interior "safe"
region for icon content is roughly `x: 28..172, y: 30..195`.

### Geometry reference

| Element | Position |
|---|---|
| Outer shield top edge | `y = 0`, full width |
| Outer shield bottom point | `(100, 215)` |
| Inner outline top edge | `y = 14`, inset 14px |
| Inner outline bottom point | `(100, 200)` |
| Bolt top point | `(116, 30)` |
| Bolt bottom point | `(84, 188)` |
| Left cell stack origin | `translate(28, 36)` |
| Right cell stack origin | `translate(150, 36)` |
| Each cell body | `22 × 32` rect, `rx="2"` |
| Each cell terminal cap | `10 × 6` rect, `rx="1"`, centered above body |
| Inter-cell vertical gap | 8px (cell body ends at y+38, next terminal at y+46) |

### Common adjustments

- **Recolor the shield.** Change the `fill` on the outer silhouette path. The
  current slate works on light and dark hosts; if you need pure black or a
  brand color, swap it here.
- **Recolor the accents.** Change every `#FACC15` to the new accent. The
  inner outline uses `stroke="#FACC15"` — change that too.
- **Single-color (monochrome) version.** Remove the inner outline path and
  set every fill/stroke to `currentColor`. Then the icon inherits whatever
  color the host text uses.
- **Drop the cells for a simpler/favicon version.** Delete the two `<g
  transform="translate(...)">` blocks containing the cell stacks. The shield
  with just a bolt scales down better below ~24px.
- **Add more cells per stack.** Each cell occupies 38px of vertical space
  (32px body + 6px terminal). Adding a third cell to each stack means
  starting them higher (e.g. `translate(28, 0)`) and they'll bump into the
  bolt's flare region — you'd also need to narrow the bolt or widen the
  shield.
- **Sharper or rounder shield corners.** The shoulders are square
  (`L 200 0` / `L 0 0`). Replace with a quarter-circle (`Q` command) for
  rounded shoulders. The base curves use `Q ... 110 ... 195` with the same
  radius implied on both sides — keep them symmetric.
- **Bolt zigzag intensity.** The bolt's "kink" is the segment from
  `(78, 112)` to `(100, 112)` to `(84, 188)`. Pulling the kink further from
  the bolt's central axis (e.g. `(70, 112)` and `(130, 102)`) creates a more
  dramatic zigzag. Keep both top and bottom points on the bolt's vertical
  centerline (`x = 100`-ish) to preserve balance.

### Pitfalls

- **Don't reorder the layers.** The inner outline must stay last in source
  order so it always sits on top.
- **Don't add `viewBox` padding by inflating the viewBox.** If you need
  whitespace around the icon, do it in the host CSS or with a wrapper. The
  current viewBox snugly fits the silhouette and changing it shifts the
  natural alignment between the shield and wordmark.
- **Don't shrink the inner outline stroke below 2px.** At smaller render
  sizes (24px and below) thinner strokes fade out and the shield reads as a
  shape with no border.
- **Stay inside the safe interior.** Anything inside the inner outline at
  `x: 14..186, y: 14..200` will read as part of the icon; anything outside
  is the dark "frame" and should remain empty.

## Wordmark (`voltkeeper-wordmark.svg`)

### Anatomy

A single `<text>` element split into two `<tspan>`s:

- `volt` — filled with amber `#EAB308` (a half-shade darker than the
  shield's `#FACC15`, so the wordmark holds against light backgrounds where
  the bright yellow would feel washed out).
- `keeper` — filled with `currentColor`, which means it adopts the color of
  whatever surrounds it. On a light page it appears near-black; on a dark
  page it appears near-white. No CSS changes required.

### Typography

| Property | Value | Notes |
|---|---|---|
| Font family | `ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif` | Native system stack; renders cleanly without web font loading. |
| Font size | `64px` (in the SVG's coordinate space) | The SVG scales, so this is a relative number — the wordmark renders at whatever size the container allows. |
| Font weight | `500` (medium) | Not bold. Bold reads too heavy alongside the icon. |
| Letter spacing | `-1.5` | Slight negative tracking tightens the wordmark and helps it read as one connected token. |
| Case | All lowercase | The project is `voltkeeper` — lowercase everywhere, like `kubectl` or `systemd`. Never `VoltKeeper`, never `VOLTKEEPER`. |

### Common adjustments

- **Use a brand font.** Replace the `font-family` value. If you embed a
  custom font, do it via `@font-face` in the host page — SVGs in browsers
  pick up document-level font definitions.
- **Use a single color.** Remove the per-tspan `fill` attributes and set
  `fill="currentColor"` on the parent `<text>`. The accent disappears, but
  the wordmark becomes maximally portable.
- **Bake in a fixed dark color** (for use against a known light background
  where `currentColor` isn't reliable, e.g. a PDF export). Replace the
  second `<tspan>`'s `fill="currentColor"` with `fill="#0F172A"` (the
  shield's slate). For the opposite case, use `fill="#F8FAFC"`.
- **Larger letter spacing.** The current `-1.5` is intentionally tight.
  Setting it to `0` gives a more conventional, slightly more open feel. Anything
  positive looks airy and reads as a different brand.
- **Different weight.** `400` looks delicate; `600` looks pushy. `500` is
  the sweet spot for the current icon size — change it only if you're
  redesigning the icon to match a heavier or lighter typographic style.

### Pitfalls

- **Don't use ALL CAPS.** The brand is consistently lowercase. A capitalized
  variant looks like a different project.
- **Don't change the split point.** The amber accent is on exactly the four
  letters `volt`, never on `voltk` or `vol`. The split mirrors the icon's
  internal split (bolt + cells = "volt" content; shield = "keeper" frame).
- **Keep `currentColor` for the "keeper" half** unless you have a specific
  reason to hardcode a color. This is what lets the wordmark drop into
  light-mode and dark-mode contexts without per-context variants.

## Lockup (icon + wordmark together)

The two assets are designed to live side by side as a lockup, with the
shield at the left and the wordmark at the right. A typical lockup:

- Set the shield's rendered height to **roughly 1.8–2.0× the wordmark's
  cap height**. With the current `64px` font size, that means the shield
  renders at about 100–115px tall.
- Allow **horizontal breathing room equal to about half the shield's
  width** between shield and wordmark.
- **Vertically center** the wordmark on the shield's middle, not its
  baseline. The shield's optical center is around `y = 95` in its native
  viewBox (slightly above geometric center because the shield narrows
  toward the bottom).

If you produce a single combined SVG for the lockup, treat the shield and
wordmark as independent `<g>` blocks with their own `transform`s — don't
flatten them. Future-you will want to recompose them.

## Variants worth producing

If the project grows, these derivatives are worth having on hand:

- **Favicon / app icon.** Shield only, no wordmark. Drop the cells for
  clarity at 16–32px. Export as 32×32, 64×64, 128×128 PNG plus an ICO.
- **Monochrome.** Single-color version (use `currentColor` throughout) for
  embroidery, single-color printing, terminal banners, and contexts where
  the amber doesn't print.
- **Inverted.** Same composition with the shield filled in amber and the
  bolt/cells/outline in slate, for amber-on-dark contexts.
- **Banner / social card.** Lockup composed for 1280×640 with breathing
  room — the GitHub social-card preview size.
- **ASCII art version.** For CLI `--help` and startup banner. Hand-drawn,
  not generated, but should preserve the shield silhouette.

## License and use

These assets are part of the Voltkeeper project and inherit its license.
Future contributors are welcome to adjust them for the project; if forking
or remixing for unrelated work, please change the wordmark text so the
result isn't confused with the original Voltkeeper brand.
