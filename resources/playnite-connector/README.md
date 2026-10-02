# Game Appliance Overlay — Playnite connector

This is the Playnite-side connector for the shared Game Appliance Overlay host.
It is intentionally a small GenericPlugin: Playnite owns game lifecycle,
metadata, playtime, and game actions; the companion host owns rendering,
controller navigation, audio, connectivity, and system controls.

## Transport

Each running game gets a random, current-user named pipe. The Playnite plugin
creates the pipe and launches the companion host with the pipe name and a
one-time handshake token. The host connects as a client and speaks newline-
delimited JSON:

- `hello` — host identity, protocol version, token, and process ID.
- `hello` response — connector snapshot.
- `action` — overlay actions such as `return` and `exit`.
- `snapshot` — connector metadata updates.
- `ping` / `pong` — liveness.

There is no TCP listener, browser endpoint, cloud dependency, or game-process
injection. The pipe ACL is restricted to the current Windows user.

## Development

1. Build the shared companion host from the Kodi repository and place the
   resulting `KodiApplianceOverlay-0.4.6.exe` in this extension's `companion/`
   directory.
2. Build this project against the Playnite SDK.
3. Add the project's `bin\Debug` directory to Playnite's developer extensions,
   or package the extension with Toolbox as a `.pext`.
4. Set the companion path in Playnite's extension settings only when testing a
   host outside the packaged `companion/` directory.

The production `.pext` should bundle the extension assembly, `extension.yaml`,
the shared companion executable, its WebView2/runtime files, and the built
`web-ui` directory. Users should not need a separate overlay installer for the
Playnite path.
