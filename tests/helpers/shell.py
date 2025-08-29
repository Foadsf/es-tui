# tests/helpers/shell.py
from __future__ import annotations
import os
import sys
import subprocess
from typing import List, Tuple


def run_in_cmd(
    args: List[str], cwd: str | None = None, timeout: int = 30
) -> Tuple[int, str, str]:
    """
    Run a command in Windows cmd.exe and capture (rc, stdout, stderr).
    """
    if os.name != "nt":
        raise RuntimeError("cmd.exe tests require Windows")
    full = ["cmd.exe", "/c"] + args
    p = subprocess.run(full, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    return p.returncode, p.stdout, p.stderr


def run_in_powershell(
    ps_command: str, cwd: str | None = None, timeout: int = 30
) -> Tuple[int, str, str]:
    """
    Run a command string in PowerShell and capture (rc, stdout, stderr).
    """
    if os.name != "nt":
        raise RuntimeError("PowerShell tests require Windows")
    shell = [
        "powershell",
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        ps_command,
    ]
    p = subprocess.run(shell, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    return p.returncode, p.stdout, p.stderr


def quote_ps(s: str) -> str:
    # Simple PowerShell single-quote escaping
    return "'" + s.replace("'", "''") + "'"
