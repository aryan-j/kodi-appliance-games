# Pause Menu Overlay — Visual Design Package

Static, dependency-free HTML/CSS implementing the approved visual design for the
in-game pause overlay. This is a **visual reference only** — no controller
navigation, focus management, WebView2 messaging, or system control logic is
implemented. All interactive-looking elements (`<button>`) are inert; states are
demonstrated via CSS classes for engineering to wire up.

## Opening the design

Open `index.html` directly in a browser. No build step, no server, no
dependencies. Fonts are system fonts only (no Google Fonts/CDNs).

The file has two parts:
1. **Live composition** — the full overlay assembled in its default/normal state.
2. **Component & state reference** — every component shown in each required
   visual state, individually labelled, for implementation reference.

## File structure

```
overlay-design/
├── index.html          Markup for the live composition + states gallery
├── styles.css           All component styles, semantic classes, states
├── design-tokens.css     Design tokens as CSS custom properties
├── README.md
└── assets/
    ├── icons/                 Row icons (also inlined as <svg> in index.html)
    ├── controller-glyphs/     DualSense-style prompt glyphs
    └── fallbacks/             Placeholder poster/fanart artwork
```

## Design tokens (`design-tokens.css`)

All values are expressed in `rem` against a 16px = 1920px-wide baseline, so the
whole design scales with `html { font-size: clamp(...) }` in `styles.css` (see
Responsive assumptions below). Token categories:

- **Color** — surfaces (`--color-bg`, `--color-panel`, `--color-group`), text
  (`--color-fg`, `--color-fg-muted`, `--color-fg-strong`), interactive states
  (`--color-focus-bg`, `--color-focus-text`, `--color-switch-on/off`,
  `--color-volume-fill`), and status pills.
- **Typography** — `--font-family` (system font stack), a type scale from
  `--fs-section-label` (11px) to `--fs-title` (34px), weights `--fw-regular`
  through `--fw-heavy`, and letter-spacing tokens.
- **Spacing** — `--space-1` (4px) through `--space-11` (64px).
- **Corner radii** — `--radius-sm` through `--radius-2xl`, `--radius-pill`, and
  `--radius-trigger` (the L2/R2 trigger-chip shape).
- **Shadows** — `--shadow-panel`, `--shadow-stats`, `--shadow-confirm`,
  `--shadow-toast`, `--shadow-glyph`.
- **Opacity** — `--opacity-disabled` (0.4) for disabled controls.
- **Transitions** — `--transition-fast` (120ms), `--transition-medium` (220ms),
  `--transition-knob` (140ms) for the switch knob.
- **Component sizes** — explicit widths/heights for the control panel (480×624),
  art column (420 wide), poster slot (420×630, fixed 2:3), row height (44px),
  switch, stats card, confirm panel, etc.

Change a token once in `design-tokens.css` and it propagates everywhere.

## Component classes (`styles.css`)

| Class | Purpose |
|---|---|
| `.stage` | 16:9 overlay canvas, clips content |
| `.background-layer` / `.background-art` / `.background-dim` | Dimmed game frame behind the overlay |
| `.tray` | Minimized "Press Guide to pause" prompt (pre-pause state) |
| `.overlay-shell` | Full-bleed flex column: header → content → footer |
| `.overlay-header`, `.overlay-title`, `.overlay-subtitle`, `.overlay-clock` | Title bar |
| `.stage-row` / `.content-row` | Centers the control panel + art column, pinned to opposite edges with open space between (so the paused game frame stays visible) |
| `.control-panel` | Left card containing the four control groups |
| `.control-group`, `.control-group-label` | A labelled section (Game / Audio / Connections / Power) |
| `.control-row` | One selectable list row (icon + label + trailing control/chevron) |
| `.control-row-icon`, `.control-row-label`, `.chevron` | Row internals |
| `.volume-meter`, `.volume-fill`, `.volume-value` | Inline volume slider inside the Volume row |
| `.switch`, `.switch-knob` | Toggle switch (Mute / Wi-Fi / Bluetooth) |
| `.status-pill` | Optional on/off text badge (available for connectivity rows) |
| `.art-column`, `.poster-slot`, `.poster-image` | Fixed 2:3 poster art frame |
| `.stats-card`, `.stat`, `.stat-value`, `.stat-label` | Session / total playtime card |
| `.footer-legend`, `.prompt-item`, `.prompt-glyph`, `.prompt-glyph--ps`, `.prompt-glyph--trigger`, `.prompt-label` | Controller button legend |
| `.confirm-backdrop`, `.confirm-panel`, `.confirm-message`, `.confirm-actions`, `.confirm-btn` | Destructive-action confirmation dialog |
| `.toast` | Bottom-center transient notification |

## Visual state classes

| State | How it's shown |
|---|---|
| Normal | Base `.control-row` / `.confirm-btn` styling |
| Focused | `.is-focused` (also triggers on real `:hover` / `:focus-visible` for actual interactivity later) — inverts to light background / dark text, matching controller "selected" affordance |
| Pressed | `.is-pressed` — focused appearance plus a 0.98 scale-down |
| Disabled | `.is-disabled` — 40% opacity, `pointer-events: none` |
| Muted | Mute row shown with `.switch.is-on` |
| Connectivity on | `.switch.is-on` (green fill, knob right) |
| Connectivity off | `.switch` base (grey track, knob left) |
| Confirmation open | `.confirm-backdrop` + `.confirm-panel` rendered (see states gallery for a standalone demo; in the live overlay this stacks on top of `.stage`) |
| Toast visible | `.toast` rendered (see states gallery) |
| Missing artwork | `.poster-slot.is-empty` — centers a small inset placeholder icon instead of a full-bleed image |
| Long game title | `.overlay-title` clips to one line with an ellipsis rather than wrapping or overflowing |

All of these are demonstrated as individually labelled cards in the
"Component & state reference" section of `index.html`.

## Asset inventory

- **`assets/icons/`** — `return`, `exit`, `volume`, `mute`, `wifi`, `bluetooth`,
  `sleep`, `restart`, `shutdown`, `chevron-right`. Provided as standalone SVG
  files for reuse/export; in `index.html` the same paths are inlined directly
  as `<svg>` with `stroke="currentColor"` so they can recolor with the row's
  text color on focus/hover without JS.
- **`assets/controller-glyphs/`** — `face-cross.svg`, `face-circle.svg`
  (DualSense-style Cross/Circle face buttons), `ps-badge.svg` (PS button),
  `trigger-l2.svg` / `trigger-r2.svg` (trigger-shaped chips). These are
  original geometric redraws — not Sony assets — sized for the footer legend.
- **`assets/fallbacks/`** — `poster-fallback.svg` (2:3, neutral dark card with
  an image glyph, used as the poster's default `src` and for the "missing
  artwork" state) and `fanart-fallback.svg` (16:9 neutral gradient, used as the
  default background art).

## Responsive assumptions

- `html { font-size: clamp(14px, 0.8333vw, 32px) }` in `styles.css` makes the
  root font-size scale linearly with viewport width (16px at 1920px wide).
  Every measurement in the design is expressed in `rem`, so the entire overlay
  scales proportionally with no JavaScript and no layout recomputation.
- Verified against 1920×1080, 2048×1152, 2560×1440 and 3840×2160 — all 16:9.
  Nothing clips and nothing scrolls at any of these sizes.
- The design assumes a 16:9 host surface. Non-16:9 aspect ratios are out of
  scope (the `.stage` keeps `aspect-ratio: 16/9` and is letterboxed by its
  wrapper if the host viewport doesn't match).
- The poster slot is a **fixed 420×630 (2:3) box** — the intended art ratio —
  and always crops via `object-fit: cover`; do not make it flex-grow.

## Intentional visual behavior

- The control panel and art column sit at the **left/right edges** of the
  stage with open space between them, so the paused game frame stays legible
  underneath the dim layer — this is a deliberate departure from a full-bleed
  panel.
- Row icons and the chevron use `currentColor` so a single hover/focus state
  change (background + text color) recolors the icon too, with no extra
  markup.
- The toggle switch's "on" color (`--color-switch-on`, `#34c759`) is a
  standard, widely recognized "enabled" green, deliberately distinct from the
  otherwise monochrome palette used everywhere else (volume fill, focus states,
  glyphs all stay white/grey/black).
- No CSS animations beyond simple `transition`s on state changes
  (background/color swap, switch knob slide) — the pause menu is intended to
  read as an instant, console-quick-menu-style overlay, not an animated one.
