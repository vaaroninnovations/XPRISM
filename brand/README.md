# XPRISM brand kit

| File | Use |
|---|---|
| `xprism-logo-original.png` | The original logo on white |
| `xprism-logo-transparent.png` | Full logo with tagline, transparent background (light backgrounds only) |
| `xprism-lockup-transparent.png` | Logo without the tagline (site header) |
| `xprism-mark-transparent.png` | The X mark on its own (favicon, app icon, small spaces) |

Web-sized copies used by the site are in `static/assets/img/`.

## Colours (taken from the logo)

| Name | Hex | Used for |
|---|---|---|
| Navy | `#08193B` / `#0A1F44` | Text, navigation bar, dark panels |
| Purple | `#7E13B5` | Primary buttons, active tabs, links, badges |
| Violet | `#4E1C8F` | Start of the brand gradient |
| Blue | `#066EAA` | Middle of the brand gradient |
| Teal | `#2BBFB0` | End of the brand gradient, highlights |

Brand gradient: violet → purple → blue → teal (the swoosh in the logo). In code: the `.xp-gradient`
and `.xp-gradient-text` classes, the `brand-*` Tailwind colours, and `--xp-*` CSS variables. The
Tailwind `teal` scale is remapped to XPRISM purple in `tailwind.config.js`, so existing accent classes
follow the brand.

## Fonts

- **Source Serif 4** (variable, with optical sizes): headlines on the site pages
- **Inter**: body text and controls
- **Poppins** (600, 700, 800): headings inside the experiment benches, a geometric typeface like the logo's wordmark
- **JetBrains Mono**: data, codes and labels

All fonts are bundled in `static/assets/fonts/` (SIL Open Font License), with no external requests.
