# Kodi Appliance Games

Windows-focused Kodi add-on for browsing, inspecting, and launching locally
installed PC games. It provides native Kodi game-library routes, metadata and
artwork integration, game information pages, trailers and walkthroughs, plus an
optional controller-operated companion overlay.

## Repository layout

- `resources/lib/`: Kodi library, metadata, launch, and process-management code.
- `resources/lib/apps.py`: static desktop application catalog and Windows launch
  command helpers.
- `resources/companion/`: C# companion overlay and build script.
- `resources/companion/web-ui-app/`: component source, connector contract and
  local build tooling for the overlay interface.
- `resources/companion/web-ui/`: generated, network-free WebView2 package.
- `resources/media/apps/`: checked-in Hydra and ChatGPT application artwork.
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

## Applications

The Games root includes an Applications entry with static Hydra and ChatGPT
launch items. Registered Windows AppIDs are opened headlessly through
`explorer.exe shell:AppsFolder\<AppID>`; Hydra uses
`gg.hydralauncher.hydra` when registered and falls back at runtime to
`D:\Programs\Hydra\Hydra.exe` only when that executable is present. ChatGPT
uses `OpenAI.Codex_2p2nqsd0c76g0!App`. These application entries never create
Games database records, queue game sessions, or start the companion overlay.
Unavailable targets stay visible with their explicit labels and show a clear
Kodi error notification when selected. Availability uses only bounded checks
for the two known targets; it does not enumerate installed files or perform
network discovery on widget refresh.

## Metadata and artwork

IGDB metadata and SteamGridDB artwork have independent refresh actions and
failure domains. An IGDB refresh updates descriptive fields without changing
artwork, executable details, favourites or play statistics. A SteamGridDB
refresh updates only successfully downloaded artwork roles and persists the
matched SteamGridDB game ID for stable future refreshes.

Game descriptions are treated as user-curated state. IGDB refreshes preserve
the current description and expose the provider summary separately through the
`igdb_summary` database field and `game.igdb_summary` list-item property.

IGDB fields include publisher, franchise, engine, release date, community
rating, genres, platforms, game modes, player perspectives and time-to-beat
estimates. List items expose these through `game.*` properties. Related-list
plugin paths are exposed for games sharing the same release year, publisher or
genre so a Games-specific More Info layout can render those widget rows.

## Building the companion

Build the frontend package before compiling the companion binary:

```powershell
Set-Location resources/companion/web-ui-app
pnpm install
pnpm run build
Set-Location ../../..
```

The frontend build is statically bundled. Preact is a build-time dependency;
the packaged overlay does not load JavaScript, CSS or fonts from the network.

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
