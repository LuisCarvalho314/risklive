"""Fail closed on operational effects, including during test collection."""
from pathlib import Path
import os
import sys

VIOLATIONS: list[str] = []


def audit(event, args):
    reason = None
    if event in {"socket.connect", "socket.bind", "socket.getaddrinfo", "subprocess.Popen", "os.system", "os.fork", "os.posix_spawn"}:
        reason = event
    if event in {"open", "os.listdir", "os.scandir", "os.mkdir", "os.remove", "os.rename"}:
        for value in args[:2] if event == "os.rename" else args[:1]:
            if not isinstance(value, (str, bytes, os.PathLike)):
                continue
            path = Path(os.fsdecode(value))
            dir_fd = args[1] if event in {"os.remove", "os.mkdir"} else None
            if not path.is_absolute() and isinstance(dir_fd, int) and dir_fd >= 0:
                path = Path(os.readlink(f"/proc/self/fd/{dir_fd}")) / path
            path = path.absolute()
            if str(path).startswith("/home/azureuser/opt/risklive"):
                reason = f"production filesystem access: {path}"
            if event == "open":
                mode, flags = args[1:3]
                writing = (isinstance(mode, str) and any(c in mode for c in "wax+")) or (isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))
            else:
                writing = event in {"os.mkdir", "os.remove", "os.rename"}
            if writing and str(path) != "/dev/null" and not path.is_relative_to(Path('/tmp')):
                reason = f"write outside isolated temporary storage: {path}"
    if reason:
        VIOLATIONS.append(reason)
        raise RuntimeError(f"Test runtime guard: {reason}")


def install():
    sys.dont_write_bytecode = True
    sys.addaudithook(audit)
