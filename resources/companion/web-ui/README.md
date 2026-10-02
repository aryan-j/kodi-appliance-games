# Gaming Overlay UI

This directory is the packaged, network-free output consumed by the WebView2
companion overlay. It is generated from the component source in
`../web-ui-app`.

## Development

From `resources/companion/web-ui-app`:

```powershell
pnpm install
pnpm run build
```

The build emits three runtime files into this directory:

- `index.html`
- `overlay-runtime.js`
- `styles.css`

The generated bundle includes Preact and all UI behavior. It makes no runtime
network requests. Inline SVG icons keep the packaged UI independent from an
icon CDN or a component service.

## Architecture

- `src/app.jsx` contains the view components.
- `src/store.js` contains the single normalized UI state.
- `src/bridge.js` exposes `window.overlayUI` for the existing WebView2 host and
  supplies the browser demo connector.
- `src/connector-contract.js` defines the connector-neutral snapshot and
  action boundary.
- `CONNECTORS.md` documents the Kodi and future Playnite integration shape.

The Kodi host continues to call `window.overlayUI.initialize`,
`updateDynamicState`, `setFocus`, and the detail/confirmation methods already
used by `WebOverlayForm.cs`. The frontend posts small JSON action messages back
to the host; it does not call Kodi, Playnite, Windows, or audio APIs directly.

## Performance rules

- Keep the runtime bundle small and statically bundled.
- Keep all layout work in normal flow; avoid JavaScript resize loops.
- Animate only `transform`, `opacity`, colors, and the switch fill.
- Do not transition `box-shadow`, `filter`, or `backdrop-filter`.
- Keep frosted surfaces limited to the actual panels and status widget.
- Keep one state store so hover/focus changes do not mutate sibling styles.
- Respect `prefers-reduced-motion`.

Game logos are supplied by a connector as `logoUrl` and rendered with
`object-fit: contain`, so portrait and landscape art retain their source
aspect ratio.
