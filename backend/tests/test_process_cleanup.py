import subprocess
import sys
import time

import pytest

from app.process_cleanup import (
    ProcessTreeTerminationResult,
    assign_process,
    create_job,
    is_windows,
    process_exists,
    terminate_job,
    terminate_process_tree,
)

pytestmark = pytest.mark.skipif(not is_windows(), reason="Windows process-tree cleanup")


def _start(script: str, *, new_process_group: bool = True) -> subprocess.Popen[str]:
    flags = subprocess.CREATE_NEW_PROCESS_GROUP if new_process_group else 0
    return subprocess.Popen(
        [sys.executable, "-c", script],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        stdin=subprocess.PIPE,
        creationflags=flags,
    )


def test_terminate_process_tree_kills_descendants() -> None:
    script = (
        "import subprocess, sys, time\n"
        "print('parent-ready', flush=True)\n"
        "import sys as _sys\n"
        "_sys.stdin.readline()\n"
        "child = subprocess.Popen([_sys.executable, '-c', 'import time; time.sleep(30)'])\n"
        "print(child.pid, flush=True)\n"
        "time.sleep(30)\n"
    )
    process = _start(script)
    assert process.stdout is not None
    assert process.stdout.readline().strip() == "parent-ready"
    job = create_job()
    try:
        assign_process(job, process.pid)
        process.stdin.write("go\n")
        process.stdin.flush()
        child_pid = int(process.stdout.readline().strip())
        assert process_exists(process.pid)
        assert process_exists(child_pid)

        try:
            assign_process(job, child_pid)
        except OSError:
            pass
        result = terminate_job(job, grace_period=0.1, root_pid=process.pid)

        assert isinstance(result, ProcessTreeTerminationResult)
        assert result.remaining_pids == ()
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline and (
            process_exists(process.pid) or process_exists(child_pid)
        ):
            time.sleep(0.05)
        assert not process_exists(process.pid)
        assert not process_exists(child_pid)
    finally:
        pass


def test_graceful_termination_is_attempted() -> None:
    script = (
        "import signal, time\n"
        "def handler(signum, frame):\n"
        "    raise SystemExit(0)\n"
        "signal.signal(signal.SIGBREAK, handler)\n"
        "print('ready', flush=True)\n"
        "time.sleep(30)\n"
    )
    process = _start(script)
    assert process.stdout is not None
    assert process.stdout.readline().strip() == "ready"

    result = terminate_process_tree(process.pid, grace_period=0.5)

    assert result.graceful_attempted is True
    assert result.remaining_pids == ()


def test_forced_termination_after_ignored_signal() -> None:
    script = "import time\nprint('ready', flush=True)\ntime.sleep(30)\n"
    process = _start(script)
    assert process.stdout is not None
    assert process.stdout.readline().strip() == "ready"

    result = terminate_process_tree(process.pid, grace_period=0.1)

    assert result.remaining_pids == ()


def test_parent_exit_with_descendant_still_in_job() -> None:
    script = (
        "import subprocess, sys\n"
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])\n"
        "print(child.pid, flush=True)\n"
    )
    process = _start(script)
    assert process.stdout is not None
    child_pid = int(process.stdout.readline().strip())
    process.wait(timeout=2)
    assert not process_exists(process.pid)
    assert process_exists(child_pid)

    job = create_job()
    assign_process(job, child_pid)
    result = terminate_job(job, grace_period=0.1, root_pid=child_pid)

    assert result.remaining_pids == ()
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline and process_exists(child_pid):
        time.sleep(0.05)
    assert not process_exists(child_pid)


def test_terminate_missing_process_is_safe() -> None:
    assert terminate_process_tree(999999, grace_period=0).remaining_pids == ()


def test_repeated_termination_does_not_leak_handles() -> None:
    for _ in range(5):
        script = "import time; time.sleep(30)\n"
        process = _start(script)
        terminate_process_tree(process.pid, grace_period=0.05)
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline and process_exists(process.pid):
            time.sleep(0.05)
        assert not process_exists(process.pid)
