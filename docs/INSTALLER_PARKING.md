# Game installer layer parking

This active source branch is the lightweight, locally-installed-games build.
The game acquisition/installation layer is not part of the runtime source.
The historical installer implementation is parked on the non-deployable branch
`codex/games-installation-parked-20260822` at commit `64239c8` (descended from
the complete `codex/smd-wrapper-completion` lineage) so it can be reviewed or
integrated deliberately later without keeping its workers and provider handoff
in Kodi's active process. The earlier `codex/games-installer-parked-20260822`
pointer at `89d5710` is retained as an earlier lifecycle snapshot.

## Active branch boundary

The active branch intentionally contains no `resources/lib/installer/` package,
`resources/vendor/smd/` tree, install-job database schema, provider request
contract, install/retry/cancel/remove routes, startup installer reconciliation,
or installer progress polling. `resources/lib/launch_service.py` remains because
it launches and monitors already-installed games; it is not an acquisition
worker.

The retained game features are deliberately separate:

- IGDB metadata refresh and SteamGridDB artwork refresh remain explicit routes.
- The Games hub/list refresh helper remains the only UI refresh mechanism used
  after catalog, favorite, metadata, artwork, or executable changes.
- `Untrack from Games (keep files)` removes the catalog row and only appliance-
  owned artwork; it never removes the executable or game directory.
- Executable availability checks remain local `os.path.isfile` checks so missing
  games can be hidden or marked without network work.
- The periodic widget refresh is owned by the skin/hub layer, not this add-on;
  this change does not remove or add a scheduler for it.

## Parked implementation inventory

The parked branch contains the installer-specific changes in these surfaces:

| Surface | Installer responsibility | Active branch |
| --- | --- | --- |
| `resources/lib/installer/*.py` | request, manifest, provider bridge, transaction, worker | absent |
| `resources/vendor/smd/` | vendored/sanitized external implementation | absent |
| `resources/lib/database.py` | install-job columns, state transitions, reconciliation | absent |
| `resources/lib/router.py` | install, retry, cancel, remove, jobs UI, provider handoff | absent |
| `resources/lib/launch_service.py` | installer completion polling additions | absent; normal launch monitor retained |
| `service.py` | installer startup/reconciliation polling additions | absent; normal launch service retained |
| `docs/SMD_INTEGRATION.md`, `config/smd-*.json`, and installer tests | installer contract, external inventory, and provider documentation/tests | absent |

The parked branch is for comparison only. It must not be deployed, merged, or
run as Kodi's active add-on without a separate review and authorization.

## Responsiveness notes

The main remaining costs in the active add-on are synchronous and user-driven:

1. `add_game` and the explicit metadata/artwork refresh routes perform network
   calls and artwork downloads on Kodi's plugin thread. They should stay out of
   startup and widget-render paths.
2. Each directory route opens the small SQLite catalog through `database.connect`;
   this is local and bounded, but repeated widget rebuilds multiply the reads.
3. `_refresh_game_surfaces` uses `ReplaceWindow(1102)` while the Games hub is
   active so all static widget paths rebuild together. It should not be called
   from a timer more often than the hub actually changes.
4. `launch_service.run` checks the pending launch queue once per second. This is
   required for launching games and is independent of the removed installer
   worker; it does no network or artwork work while idle.

No background network call, installer queue, child installer process, or SMD
provider poll remains in the active source.

## Runtime reconciliation (2026-08-22)

The deployed runtime at
`C:\Users\Aryan\AppData\Roaming\Kodi\addons\plugin.program.appliance.games`
was not in sync with the active source before this cleanup. It contained the
installer package (`resources/lib/installer/`, 10 Python modules), the full
sanitized SMD vendor tree under `resources/vendor/smd/`, installer-aware
`database.py` and `router.py`, and an installer poll in `launch_service.py`.
The deployed README also described the installer boundary. Those live-only
files are the cause of the installer layer being present at runtime; they are
not required by the active source branch.

The active source branch is therefore the focused removal patch: it is already
installer-free, with the retained untrack/refresh behavior added in this
branch. Deployment must copy the validated source files (or the complete
package) over the live add-on and remove only the live-only installer/vendor
files. Do not delete the parked branch or its history. The live companion
overlay binaries and other historical runtime assets are outside the installer
boundary and were not changed by this source patch.
