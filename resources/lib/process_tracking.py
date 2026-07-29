"""Small Windows process helpers used to follow launcher-to-game handoffs."""

import ctypes
import os
import time
from ctypes import wintypes


TH32CS_SNAPPROCESS = 0x00000002
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
SYNCHRONIZE = 0x00100000
WAIT_OBJECT_0 = 0
STILL_ACTIVE = 259
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * 260),
    ]


kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
kernel32.CreateToolhelp32Snapshot.argtypes = (wintypes.DWORD, wintypes.DWORD)
kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
kernel32.Process32FirstW.argtypes = (wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W))
kernel32.Process32FirstW.restype = wintypes.BOOL
kernel32.Process32NextW.argtypes = (wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W))
kernel32.Process32NextW.restype = wintypes.BOOL
kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.QueryFullProcessImageNameW.argtypes = (
    wintypes.HANDLE,
    wintypes.DWORD,
    wintypes.LPWSTR,
    ctypes.POINTER(wintypes.DWORD),
)
kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
kernel32.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
kernel32.WaitForSingleObject.restype = wintypes.DWORD
kernel32.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
kernel32.GetExitCodeProcess.restype = wintypes.BOOL
kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
kernel32.CloseHandle.restype = wintypes.BOOL


def _processes():
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snapshot == INVALID_HANDLE_VALUE:
        return {}
    rows = {}
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        if not kernel32.Process32FirstW(snapshot, ctypes.byref(entry)):
            return rows
        while True:
            rows[int(entry.th32ProcessID)] = {
                "pid": int(entry.th32ProcessID),
                "parent": int(entry.th32ParentProcessID),
                "name": entry.szExeFile,
            }
            if not kernel32.Process32NextW(snapshot, ctypes.byref(entry)):
                break
    finally:
        kernel32.CloseHandle(snapshot)
    return rows


def _image_path(pid):
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return ""
    try:
        length = wintypes.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(length.value)
        if kernel32.QueryFullProcessImageNameW(
            handle, 0, buffer, ctypes.byref(length)
        ):
            return buffer.value
    finally:
        kernel32.CloseHandle(handle)
    return ""


class AttachedProcess:
    """subprocess-like wrapper around an already-running Windows process."""

    def __init__(self, pid):
        self.pid = int(pid)
        self.returncode = None
        self._handle = kernel32.OpenProcess(
            SYNCHRONIZE | PROCESS_QUERY_LIMITED_INFORMATION,
            False,
            self.pid,
        )
        if not self._handle:
            raise OSError(ctypes.get_last_error(), f"Unable to attach to PID {pid}")

    def poll(self):
        if self.returncode is not None:
            return self.returncode
        if kernel32.WaitForSingleObject(self._handle, 0) != WAIT_OBJECT_0:
            return None
        code = wintypes.DWORD()
        if kernel32.GetExitCodeProcess(self._handle, ctypes.byref(code)):
            self.returncode = int(code.value)
        else:
            self.returncode = 0
        return self.returncode

    def wait(self):
        kernel32.WaitForSingleObject(self._handle, 0xFFFFFFFF)
        return self.poll()

    def close(self):
        if self._handle:
            kernel32.CloseHandle(self._handle)
            self._handle = None

    def __del__(self):
        self.close()


def find_descendant(root_pid, requested_executable, working_directory, timeout=5):
    """Find the real game process created by a short-lived launcher process.

    Preference is given to descendants whose executable name matches the
    requested game and whose path remains inside the configured game folder.
    """

    requested_name = os.path.basename(requested_executable).casefold()
    game_root = os.path.normcase(os.path.abspath(working_directory or os.path.dirname(requested_executable)))
    deadline = time.monotonic() + timeout
    best = None

    while time.monotonic() < deadline:
        rows = _processes()
        descendants = {}
        changed = True
        while changed:
            changed = False
            for pid, row in rows.items():
                if pid == root_pid or pid in descendants:
                    continue
                parent = row["parent"]
                if parent == root_pid:
                    descendants[pid] = 1
                    changed = True
                elif parent in descendants:
                    descendants[pid] = descendants[parent] + 1
                    changed = True

        for pid, depth in descendants.items():
            row = rows.get(pid)
            path = _image_path(pid)
            normalized_path = os.path.normcase(os.path.abspath(path)) if path else ""
            same_name = row["name"].casefold() == requested_name
            inside_game = bool(
                normalized_path
                and os.path.commonpath([game_root, normalized_path]) == game_root
            )
            score = (100 if same_name else 0) + (40 if inside_game else 0) + depth
            if best is None or score > best[0]:
                best = (score, pid, row["name"], path)

        # A same-name descendant is the strongest possible handoff signal.
        if best and best[0] >= 100:
            try:
                return AttachedProcess(best[1]), best
            except OSError:
                best = None
        time.sleep(0.25)

    if best and best[0] >= 40:
        try:
            return AttachedProcess(best[1]), best
        except OSError:
            pass
    return None, None
