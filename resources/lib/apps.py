"""Static Windows applications exposed by the appliance Games add-on.

The catalog deliberately contains no user- or machine-discovered entries.
Known registered applications are opened through the Windows AppsFolder shell
namespace; Hydra has a narrowly scoped executable fallback for installations
that are not registered there.
"""

import os
import subprocess
from collections import namedtuple
from functools import lru_cache


Application = namedtuple(
    "Application",
    ("key", "label", "app_id", "fallback_executable", "artwork"),
)


HYDRA_EXECUTABLE = r"D:\Programs\Hydra\Hydra.exe"
HYDRA_APP_ID = "gg.hydralauncher.hydra"
CHATGPT_APP_ID = "OpenAI.Codex_2p2nqsd0c76g0!App"


APPLICATIONS = (
    Application(
        key="hydra",
        label="Hydra",
        app_id=HYDRA_APP_ID,
        fallback_executable=HYDRA_EXECUTABLE,
        artwork="hydra.png",
    ),
    Application(
        key="chatgpt",
        label="ChatGPT",
        app_id=CHATGPT_APP_ID,
        fallback_executable="",
        artwork="chatgpt.png",
    ),
)

_APPLICATIONS_BY_KEY = {application.key: application for application in APPLICATIONS}


def all_applications():
    """Return the immutable, statically defined application catalog."""
    return APPLICATIONS


def get_application(key):
    return _APPLICATIONS_BY_KEY.get(key)


def artwork_path(application, addon_root):
    """Resolve checked-in artwork without probing the filesystem."""
    return os.path.join(addon_root, "resources", "media", "apps", application.artwork)


def _fallback_available(application):
    executable = os.path.expandvars(application.fallback_executable or "")
    return bool(executable and os.path.isfile(executable))


@lru_cache(maxsize=16)
def _registered_app_available(app_id):
    """Check one known AppID with a bounded Windows shell namespace lookup.

    This avoids enumerating AppsFolder or spawning a shell process whenever a
    widget refreshes. The cache is process-local and intentionally small: the
    catalog has only known, static entries.
    """
    if not app_id or os.name != "nt":
        return False
    try:
        import ctypes
    except ImportError:
        return False

    shell_path = "shell:AppsFolder\\" + app_id
    pidl = ctypes.c_void_p()
    attributes = ctypes.c_ulong()
    ole32 = ctypes.windll.ole32
    com_initialized = False
    try:
        # Shell namespace parsing requires a COM apartment. Balance only a
        # successful initialization; RPC_E_CHANGED_MODE means the caller's
        # existing apartment must be left untouched.
        com_result = ole32.CoInitializeEx(None, 2)
        com_initialized = com_result in (0, 1)
        result = ctypes.windll.shell32.SHParseDisplayName(
            ctypes.c_wchar_p(shell_path),
            None,
            ctypes.byref(pidl),
            0,
            ctypes.byref(attributes),
        )
    except (AttributeError, OSError, TypeError):
        return False
    finally:
        if pidl.value:
            try:
                ole32.CoTaskMemFree(pidl)
            except (AttributeError, OSError):
                pass
        if com_initialized:
            try:
                ole32.CoUninitialize()
            except (AttributeError, OSError):
                pass
    return result == 0


def is_available(application):
    """Return whether the known launch target appears to be available."""
    if application.app_id and _registered_app_available(application.app_id):
        return True
    return _fallback_available(application)


def command_for(application, registered_available=None):
    """Build a headless launch command, or return ``None`` if unavailable.

    Registered AppIDs always take precedence. ``registered_available`` is an
    optional test seam; omitted calls use the bounded registry check above.
    """
    if application.app_id:
        if registered_available is None:
            registered_available = _registered_app_available(application.app_id)
        if registered_available:
            return ["explorer.exe", "shell:AppsFolder\\" + application.app_id]
    if _fallback_available(application):
        return [os.path.expandvars(application.fallback_executable)]
    return None


def launch(application, popen=None):
    """Launch one application without a terminal and return its process.

    The caller must check for a ``None`` command and handle its Kodi
    notification. This function does not import or call the game database or
    companion overlay.
    """
    command = command_for(application)
    if not command:
        return None
    if popen is None:
        popen = subprocess.Popen
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return popen(command, cwd=None, creationflags=creationflags)
