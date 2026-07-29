# Kodi Appliance Games

Windows-focused Kodi add-on for browsing, inspecting, and launching locally
installed PC games. It provides native Kodi game-library routes, metadata and
artwork integration, game information pages, trailers and walkthroughs, plus an
optional controller-operated companion overlay.

## Repository layout

- `resources/lib/`: Kodi library, metadata, launch, and process-management code.
- `resources/companion/`: C# companion overlay and build script.
- `resources/companion/web-ui/`: controller-first overlay interface.
- `resources/settings.xml`: add-on settings schema. Credentials are deliberately
  stored only in Kodi's profile and are never committed.

## Local data

The following runtime files belong under Kodi's
`userdata/addon_data/plugin.program.appliance.games` directory and must remain
untracked:

- `settings.xml`
- `igdb-token.json`
- `games.db`

Game records contain direct executable, argument and working-directory data.
Artwork copied into the add-on profile remains owned by Kodi, so browsing and
launching do not require an external library manager.

## Building the companion

Run the build script from PowerShell:

```powershell
.\resources\companion\build.ps1 -Version 0.4.6
```

The script compiles the C# sources against the bundled WebView2 assemblies.

## Upstream and release policy

This repository is the canonical source for the custom add-on. Changes should
be developed on focused branches, reviewed through pull requests, and packaged
only after Kodi runtime validation. Generated databases, user configuration,
credentials, caches, logs, and machine-specific paths are excluded.
