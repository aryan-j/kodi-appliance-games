import os
import subprocess
import time

import xbmc
import xbmcvfs
import xbmcgui
import xbmcaddon

from . import database
from . import process_tracking


STARTUP_QUEUE_GUARD_SECONDS = 5.0


def _startup_session_guard():
    """Reconcile old launch state and return the startup session watermark."""
    try:
        # A process snapshot is read once.  If it cannot be collected, the
        # database helper fails closed and preserves running history.
        active_process_ids = process_tracking.running_process_ids()
    except Exception as exc:
        active_process_ids = None
        xbmc.log(
            f"[Kodi Appliance Games] Startup process reconciliation skipped: {exc}",
            xbmc.LOGWARNING,
        )
    result = database.reconcile_startup_sessions(active_process_ids)
    if result["pending_quarantined"] or result["stale_reconciled"]:
        xbmc.log(
            "[Kodi Appliance Games] Startup session guard: "
            f"quarantined {result['pending_quarantined']} pending, "
            f"reconciled {result['stale_reconciled']} stale",
            xbmc.LOGINFO,
        )
    return result["watermark"]


def _overlay_path():
    addon_path = xbmcvfs.translatePath(xbmcaddon.Addon().getAddonInfo("path"))
    return os.path.join(
        addon_path,
        "resources",
        "companion",
        "KodiApplianceOverlay-0.4.6.exe",
    )


def _translated(value):
    return xbmcvfs.translatePath(value or "")


def _start_overlay(process, session, session_started_epoch):
    if not xbmcaddon.Addon().getSettingBool("overlay_enabled"):
        return None
    overlay = _overlay_path()
    if not os.path.isfile(overlay):
        xbmc.log(
            f"[Kodi Appliance Games] Overlay companion not found: {overlay}",
            xbmc.LOGWARNING,
        )
        return None
    try:
        command = [
            overlay,
            "--web-ui",
            "--pid",
            str(process.pid),
            "--title",
            session["name"],
            "--poster",
            _translated(session["cover"]),
            "--fanart",
            _translated(session["background"]),
            "--genres",
            session["genres"] or "",
            "--studio",
            session["developer"] or session["publisher"] or "",
            "--total-seconds",
            str(session["playtime_seconds"] or 0),
            "--session-start",
            str(session_started_epoch),
            "--font-regular",
            _translated("special://home/addons/skin.arctic.fuse.3/fonts/Inter-Regular.ttf"),
            "--font-bold",
            _translated("special://home/addons/skin.arctic.fuse.3/fonts/Inter-Bold.ttf"),
        ]
        if xbmcaddon.Addon().getSettingBool("overlay_suspend_game"):
            command.append("--suspend-game")
        companion = subprocess.Popen(command, cwd=os.path.dirname(overlay))
        xbmc.log(
            f"[Kodi Appliance Games] Overlay companion started for PID {process.pid}",
            xbmc.LOGINFO,
        )
        return companion
    except Exception as exc:
        # Overlay failure must never prevent the game itself from running.
        xbmc.log(
            f"[Kodi Appliance Games] Overlay companion failed to start: {exc}",
            xbmc.LOGERROR,
        )
        return None


def _command(game):
    executable = os.path.expandvars(game["executable"])
    arguments = os.path.expandvars(game["arguments"] or "")
    # Windows' CreateProcess command-line parser is not POSIX shlex. Passing the
    # executable separately and the original argument string preserves quoting
    # used by game launchers and paths containing spaces.
    return [executable, arguments] if arguments else [executable]


def launch(session):
    session_id = session["session_id"]
    game_id = session["id"]
    started = time.monotonic()
    session_started_epoch = int(time.time())
    companion = None
    try:
        executable = os.path.expandvars(session["executable"])
        if not os.path.isfile(executable):
            raise FileNotFoundError(executable)
        working_directory = os.path.expandvars(session["working_directory"] or os.path.dirname(executable))
        xbmc.log(
            f"[Kodi Appliance Games] Launching {session['name']} from {executable}",
            xbmc.LOGINFO,
        )
        xbmc.executebuiltin("Minimize")
        command = _command(session)
        if len(command) == 2:
            process = subprocess.Popen(
                f'"{command[0]}" {command[1]}',
                executable=command[0],
                cwd=working_directory or None,
            )
        else:
            process = subprocess.Popen(command, cwd=working_directory or None)
        root_pid = process.pid
        database.mark_running(session_id, root_pid)
        launched_at = time.monotonic()
        time.sleep(0.75)
        if process.poll() is None:
            companion = _start_overlay(process, session, session_started_epoch)
        process.wait()
        # Some games use a tiny bootstrap process that immediately creates a
        # launcher and then the real game. Adopt that descendant so overlay,
        # playtime and session completion follow the actual game process.
        if time.monotonic() - launched_at < 15:
            adopted, handoff = process_tracking.find_descendant(
                root_pid,
                executable,
                working_directory,
            )
            if adopted:
                if companion and companion.poll() is None:
                    companion.terminate()
                process = adopted
                database.mark_running(session_id, process.pid)
                xbmc.log(
                    f"[Kodi Appliance Games] Adopted game process PID {process.pid} "
                    f"({handoff[2]}) from launcher PID {root_pid}",
                    xbmc.LOGINFO,
                )
                companion = _start_overlay(process, session, session_started_epoch)
                process.wait()
        database.finish_session(session_id, game_id, started)
        xbmc.log(
            f"[Kodi Appliance Games] Session {session_id} completed with exit code "
            f"{process.returncode}",
            xbmc.LOGINFO,
        )
        xbmc.executebuiltin("ActivateWindow(Home)")
    except Exception as exc:
        database.finish_session(session_id, game_id, started, str(exc))
        xbmc.log(
            f"[Kodi Appliance Games] Session {session_id} failed: {exc}",
            xbmc.LOGERROR,
        )
        xbmcgui.Dialog().notification("Games", f"Launch failed: {exc}", xbmcgui.NOTIFICATION_ERROR)
    finally:
        if companion and companion.poll() is None:
            try:
                companion.terminate()
            except Exception:
                pass


def run():
    database.connect().close()
    startup_watermark = _startup_session_guard()
    launch_after = time.monotonic() + STARTUP_QUEUE_GUARD_SECONDS
    monitor = xbmc.Monitor()
    while not monitor.abortRequested():
        if time.monotonic() >= launch_after:
            session = database.next_pending_session(after_session_id=startup_watermark)
            if session:
                launch(session)
        if monitor.waitForAbort(1):
            break
