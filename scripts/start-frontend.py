"""Start the Vite dev server as a fully detached Windows process.

Running the frontend through PowerShell's ``Start-Process`` ties the Node process
to the interactive console job. Closing the shell (or the agent harness that
launched it) can then terminate Vite even though the startup script reports
success. This helper spawns it in its own process group with file-backed stdio
so the frontend survives the parent shell and can be stopped through the PID
file written next to the logs.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    if len(argv) != 6:
        print(
            "usage: start-frontend.py <log-file> <error-file> <host> <port> <pid-file>",
            file=sys.stderr,
        )
        return 2

    log_path, err_path, host, port, pid_path = argv[1:]
    frontend_dir = Path(__file__).resolve().parents[1] / "frontend"
    if not (frontend_dir / "package.json").exists():
        print(f"frontend package.json not found under {frontend_dir}", file=sys.stderr)
        return 1

    creation_flags = 0
    if os.name == "nt":
        creation_flags = (
            subprocess.DETACHED_PROCESS
            | subprocess.CREATE_NEW_PROCESS_GROUP
            | subprocess.CREATE_NO_WINDOW
        )

    with open(log_path, "ab") as stdout, open(err_path, "ab") as stderr:
        process = subprocess.Popen(
            [
                "cmd.exe",
                "/c",
                "npm",
                "run",
                "dev",
                "--",
                "--host",
                host,
                "--port",
                str(port),
                "--strictPort",
            ],
            cwd=str(frontend_dir),
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=stderr,
            creationflags=creation_flags,
            close_fds=True,
        )

    Path(pid_path).write_text(str(process.pid), encoding="utf-8")
    print(process.pid)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
