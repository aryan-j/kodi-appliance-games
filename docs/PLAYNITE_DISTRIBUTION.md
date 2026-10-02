# Playnite distribution plan

## Recommended product boundary

Ship one shared overlay host and two thin connectors:

- The Playnite `.pext` contains the Playnite GenericPlugin, named-pipe server,
  settings UI, and the shared companion host/web UI.
- The Kodi add-on contains the Kodi connector and the same companion host/web UI.
- Do not make users download a separate overlay product for the first public
  release. A separate host package can become useful later for other launchers,
  but it would add versioning and support friction now.

The UI host is connector-neutral. Playnite owns title, genres, studio, logo,
session start, total playtime, and game exit. Kodi owns the equivalent values
through the existing add-on launch path. Both integrations keep audio,
connectivity, power, controller navigation, and rendering in the shared host.

## Settings

The Playnite extension should expose only integration settings: enable the
connector, start the host with a game, show immediately, suspend behavior,
logo preference, and an optional host-path override for development. The
overlay should not gain a separate settings application in v1. Visual settings
belong in a future shared host configuration only when a second non-Playnite,
non-Kodi connector needs them.

## Forum release sequence

1. Publish the Playnite `.pext` and source/release notes in the Playnite add-on
   database/forum with the transport and bundled-runtime requirements clearly
   stated.
2. Publish the Kodi add-on separately in the Kodi forum, documenting that the
   same overlay host is embedded and that Kodi remains optional to the host
   architecture.
3. Keep the repository as the canonical issue tracker and source location;
   forum posts should link to versioned releases rather than attach changing
   binaries manually.
