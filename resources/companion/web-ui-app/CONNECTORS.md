# Overlay connector contract

The frontend is intentionally connector-neutral. A connector owns metadata,
system integration, and side effects; the UI only renders a normalized
snapshot and emits small action messages.

## Snapshot

```json
{
  "title": "Game name",
  "subtitle": "Genre  |  Studio",
  "clock": "3:36 PM",
  "sessionTime": "00:08:44",
  "totalPlaytime": "02:02:00",
  "logoUrl": "https://logo.local/game.png",
  "volume": 66,
  "muted": false,
  "wifiEnabled": true,
  "bluetoothEnabled": true,
  "outputDevices": { "defaultId": "living-room", "devices": [] },
  "connectivitySnapshot": { "wifi": {}, "bluetooth": {} },
  "focusedAction": "return"
}
```

## Commands

The UI posts `{ "type": "action", "action": "..." }` with optional `ssid`
or `deviceId`. Kodi currently receives these through WebView2's
`WebMessageReceived` event. The Playnite connector uses the same action
payload at its boundary, but the browser never opens the pipe directly: the
native companion host is the named-pipe client and forwards game lifecycle
actions to the Playnite plugin.

The Playnite Overlay project is a useful reference for game detection and
Playnite-side values: title, image path, game ID, process ID, active time, and
total playtime. Its `RunningApp` model already exposes the core fields needed
to populate this snapshot. The connector should translate those values into
the contract rather than coupling the UI to Playnite SDK types.

The first adapter helpers live in `src/connectors/kodi.js` and
`src/connectors/playnite.js`. The Playnite helper maps the `RunningApp` fields
used by the linked extension (`Title`, `ActivatedTime`, `TotalPlaytime`, and a
transport-served image URL) into the same snapshot. The production Playnite
connector supplies the equivalent values to the native host as `title`,
`genres`, `studio`, `logoPath`, `totalSeconds`, and `sessionStartEpoch`; the
host maps the local logo path into the WebView2 asset origin. It does not
assume that a Windows file path is directly readable by the browser.

## Playnite transport

`resources/playnite-connector` contains the Playnite GenericPlugin
and its `NamedPipeServerStream` implementation. Playnite creates a random pipe
per game session, restricts it to the current Windows user, launches the shared
companion with a one-time token, and owns `exit` actions. The companion host
owns rendering and Windows controls, so the same static UI can serve both Kodi
and Playnite without a network/runtime dependency.

## Runtime rule

The packaged `resources/companion/web-ui` directory contains only the built
static output. Preact and the connector adapters are build-time dependencies;
the running overlay makes no network requests for code or UI components.
