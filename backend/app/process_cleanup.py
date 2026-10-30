"""Windows process-tree helpers for local benchmark cancellation.

This module is intentionally limited to *synthetic-testable* process lifecycle
behaviour.  It does not know anything about the private benchmark, model
servers, or BenchScope run state.
"""

from __future__ import annotations

import ctypes
import os
import subprocess
import time
from ctypes import wintypes
from dataclasses import dataclass

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True) if os.name == "nt" else None

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_ALL_ACCESS = 0x1F0FFF
STILL_ACTIVE = 259
CTRL_BREAK_EVENT = 1
CREATE_NEW_PROCESS_GROUP = 0x00000200

JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
JOB_OBJECT_BASIC_PROCESS_ID_LIST = 3


class _IO_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_ulonglong),
        ("WriteOperationCount", ctypes.c_ulonglong),
        ("OtherOperationCount", ctypes.c_ulonglong),
        ("ReadTransferCount", ctypes.c_ulonglong),
        ("WriteTransferCount", ctypes.c_ulonglong),
        ("OtherTransferCount", ctypes.c_ulonglong),
    ]


class _JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", wintypes.LARGE_INTEGER),
        ("PerJobUserTimeLimit", wintypes.LARGE_INTEGER),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class _JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ("IoInfo", _IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


class _JOBOBJECT_BASIC_PROCESS_ID_LIST(ctypes.Structure):
    _fields_ = [
        ("NumberOfAssignedProcesses", wintypes.DWORD),
        ("NumberOfProcessIdsInList", wintypes.DWORD),
        ("ProcessIdList", wintypes.DWORD * 1024),
    ]


@dataclass(frozen=True)
class ProcessTreeTerminationResult:
    requested_pid: int
    graceful_attempted: bool
    forced: bool
    remaining_pids: tuple[int, ...]


def _last_error(message: str) -> OSError:
    return OSError(f"{message}: {ctypes.get_last_error()}")


def _require_windows() -> None:
    if kernel32 is None:
        raise RuntimeError("process-tree cleanup is only supported on Windows")


def process_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name != "nt":
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True
    if kernel32 is None:
        return False
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return False
    try:
        exit_code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            return False
        return exit_code.value == STILL_ACTIVE
    finally:
        kernel32.CloseHandle(handle)


def create_job() -> int:
    _require_windows()
    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        raise _last_error("CreateJobObjectW failed")
    info = _JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
    info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not kernel32.SetInformationJobObject(
        job,
        JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
        ctypes.byref(info),
        ctypes.sizeof(info),
    ):
        kernel32.CloseHandle(job)
        raise _last_error("SetInformationJobObject failed")
    return job


def assign_process(job: int, pid: int) -> None:
    handle = kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
    if not handle:
        raise _last_error(f"OpenProcess failed for pid {pid}")
    try:
        if not kernel32.AssignProcessToJobObject(job, handle):
            raise _last_error(f"AssignProcessToJobObject failed for pid {pid}")
    finally:
        kernel32.CloseHandle(handle)


def _job_process_ids(job: int) -> tuple[int, ...]:
    info = _JOBOBJECT_BASIC_PROCESS_ID_LIST()
    returned = wintypes.DWORD()
    if not kernel32.QueryInformationJobObject(
        job,
        JOB_OBJECT_BASIC_PROCESS_ID_LIST,
        ctypes.byref(info),
        ctypes.sizeof(info),
        ctypes.byref(returned),
    ):
        return ()
    count = min(info.NumberOfProcessIdsInList, 1024)
    return tuple(info.ProcessIdList[index] for index in range(count))


def terminate_process_tree(
    pid: int,
    *,
    grace_period: float = 0.25,
    poll_interval: float = 0.05,
) -> ProcessTreeTerminationResult:
    """Terminate a process and descendants using a kill-on-close Job Object.

    The function first attempts a bounded graceful shutdown.  If any process in
    the job is still alive after the grace period, ``TerminateJobObject`` forces
    termination of the entire job.
    """

    _require_windows()
    if not process_exists(pid):
        return ProcessTreeTerminationResult(pid, False, False, ())

    job = create_job()
    graceful_attempted = False
    forced = False
    try:
        assign_process(job, pid)
        graceful_attempted = True
        try:
            kernel32.GenerateConsoleCtrlEvent(CTRL_BREAK_EVENT, pid)
        except OSError:
            pass

        deadline = time.monotonic() + max(grace_period, 0)
        while time.monotonic() < deadline and (
            process_exists(pid) or _job_process_ids(job)
        ):
            time.sleep(poll_interval)

        remaining = _job_process_ids(job)
        if process_exists(pid) or remaining:
            if kernel32.TerminateJobObject(job, 1):
                forced = True
            else:
                raise _last_error("TerminateJobObject failed")

        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and (
            process_exists(pid) or _job_process_ids(job)
        ):
            time.sleep(poll_interval)

        remaining = _job_process_ids(job)
        if process_exists(pid):
            remaining = (pid,) + tuple(p for p in remaining if p != pid)
        return ProcessTreeTerminationResult(
            pid,
            graceful_attempted,
            forced,
            remaining,
        )
    finally:
        kernel32.CloseHandle(job)


def is_windows() -> bool:
    return os.name == "nt"


def terminate_job(
    job: int,
    *,
    grace_period: float = 0.25,
    poll_interval: float = 0.05,
    root_pid: int | None = None,
) -> ProcessTreeTerminationResult:
    """Terminate every process currently assigned to *job*."""

    _require_windows()

    graceful_attempted = True
    forced = False
    if root_pid is not None and process_exists(root_pid):
        try:
            kernel32.GenerateConsoleCtrlEvent(CTRL_BREAK_EVENT, root_pid)
        except OSError:
            pass

    deadline = time.monotonic() + max(grace_period, 0)
    while time.monotonic() < deadline and (
        (root_pid is not None and process_exists(root_pid)) or _job_process_ids(job)
    ):
        time.sleep(poll_interval)

    remaining = _job_process_ids(job)
    if (root_pid is not None and process_exists(root_pid)) or remaining:
        if kernel32.TerminateJobObject(job, 1):
            forced = True
        else:
            raise _last_error("TerminateJobObject failed")

    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline and (
        (root_pid is not None and process_exists(root_pid)) or _job_process_ids(job)
    ):
        time.sleep(poll_interval)

    remaining = _job_process_ids(job)
    if root_pid is not None and process_exists(root_pid):
        remaining = (root_pid,) + tuple(p for p in remaining if p != root_pid)
    return ProcessTreeTerminationResult(
        root_pid or 0,
        graceful_attempted,
        forced,
        remaining,
    )


CREATE_SUSPENDED = 0x00000004
TH32CS_SNAPTHREAD = 0x00000004
THREAD_SUSPEND_RESUME = 0x0002


class _THREADENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ThreadID", wintypes.DWORD),
        ("th32OwnerProcessID", wintypes.DWORD),
        ("tpBasePri", ctypes.c_long),
        ("tpDeltaPri", ctypes.c_long),
        ("dwFlags", wintypes.DWORD),
    ]


def _resume_main_thread(pid: int) -> None:
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0)
    if snapshot == wintypes.HANDLE(-1).value:
        raise _last_error("CreateToolhelp32Snapshot failed")
    try:
        entry = _THREADENTRY32()
        entry.dwSize = ctypes.sizeof(entry)
        if not kernel32.Thread32First(snapshot, ctypes.byref(entry)):
            raise _last_error("Thread32First failed")
        thread_id: int | None = None
        while True:
            if entry.th32OwnerProcessID == pid:
                thread_id = entry.th32ThreadID
                break
            if not kernel32.Thread32Next(snapshot, ctypes.byref(entry)):
                break
        if thread_id is None:
            raise RuntimeError("main thread not found")
        handle = kernel32.OpenThread(THREAD_SUSPEND_RESUME, False, thread_id)
        if not handle:
            raise _last_error("OpenThread failed")
        try:
            if kernel32.ResumeThread(handle) == 0xFFFFFFFF:
                raise _last_error("ResumeThread failed")
        finally:
            kernel32.CloseHandle(handle)
    finally:
        kernel32.CloseHandle(snapshot)


def start_suspended_process(
    command: list[str] | tuple[str, ...],
    *,
    cwd: str,
    env: dict[str, str],
    creationflags: int = 0,
) -> tuple[subprocess.Popen[bytes], int]:
    if kernel32 is None:
        raise RuntimeError("suspended process launch is only supported on Windows")
    job = create_job()
    flags = creationflags | CREATE_SUSPENDED | CREATE_NEW_PROCESS_GROUP
    try:
        process = subprocess.Popen(
            list(command),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd,
            env=env,
            creationflags=flags,
        )
    except Exception:
        kernel32.CloseHandle(job)
        raise
    try:
        assign_process(job, process.pid)
        _resume_main_thread(process.pid)
    except Exception:
        try:
            process.kill()
        except OSError:
            pass
        process.wait()
        kernel32.CloseHandle(job)
        raise
    return process, job
