# Brand Assets

Voltkeeper visual identity — two SVG assets and design rationale.

## Assets

| File                      | Purpose                                                                               |
| ------------------------- | ------------------------------------------------------------------------------------- |
| `voltkeeper-shield.svg`   | The icon mark. Square-ish shield with a lightning bolt flanked by two battery stacks. |
| `voltkeeper-wordmark.svg` | The word "voltkeeper" with "volt" in amber and "keeper" in currentColor.              |

Both files are standalone — open in any browser or vector editor.

## Design intent

- **"keeper"** → the **shield**. Evokes guardianship, protection, UPS-like stewardship.
- **"volt"** → the **lightning bolt and battery cells** inside the shield. The
  bolt is the universal electrical glyph; the cell stacks suggest a battery bank.

Color is restricted to two values: deep slate (`#0F172A`) for the shield,
and amber yellow (`#FACC15` / `#EAB308`) for accents. No gradients, no drop
shadows, no glows — the mark reproduces cleanly at any size.

The amber-on-slate palette references high-visibility electrical warning
signage and distinguishes the project from the cooler blue/teal palette
dominant in the EV-charging and consumer-power-station space.

## Shield (`voltkeeper-shield.svg`)

Layered in order: outer silhouette (slate), lightning bolt (amber),
battery stacks (amber strokes), inner outline (3px amber stroke, last in
source order so it always sits on top).

| Element                 | Position           |
| ----------------------- | ------------------ |
| Bolt top point          | (116, 30)          |
| Bolt bottom point       | (84, 188)          |
| Left cell stack origin  | translate(28, 36)  |
| Right cell stack origin | translate(150, 36) |

## Wordmark (`voltkeeper-wordmark.svg`)

| Property       | Value                                               |
| -------------- | --------------------------------------------------- |
| Font family    | ui-sans-serif, system-ui, -apple-system, sans-serif |
| Font size      | 64px (SVG coordinate space)                         |
| Font weight    | 500 (medium)                                        |
| Letter spacing | -1.5                                                |
| Case           | All lowercase                                       |

## Lockup (icon + wordmark)

The shield renders at about 100–115px tall alongside the wordmark.
Horizontal breathing room equals about half the shield's width between
them. Vertically center the wordmark on the shield's middle.

## Variants

- **Favicon / app icon**: Shield only, no wordmark, drop cells for clarity at 16–32px
- **Monochrome**: Single-color version using `currentColor` throughout
- **Inverted**: Shield in amber, bolt/cells/outline in slate
- **Banner / social card**: Lockup composed for 1280×640

## License

These assets are part of the Voltkeeper project and inherit its MIT license.
