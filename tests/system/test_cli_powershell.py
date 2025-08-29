# tests/system/test_cli_powershell.py
import os
import sys
import pytest
from tests.helpers.shell import run_in_powershell, quote_ps

pytestmark = pytest.mark.skipif(
    os.name != "nt", reason="PowerShell tests require Windows"
)


def _script(python_exe: str, script: str, *args: str) -> str:
    exe = quote_ps(python_exe)
    scr = quote_ps(script)
    tail = " ".join(quote_ps(a) for a in args)
    # Use the call operator & so PowerShell executes the quoted path
    return f"& {exe} {scr} {tail}".strip()


def test_basic_query_powershell(repo_root, golden_corpus, python_exe):
    es_cli = str(repo_root / "es_winsearch.py")
    query = "report"
    cmd = _script(python_exe, es_cli, query, "--path", str(golden_corpus))
    rc, out, err = run_in_powershell(cmd, cwd=str(repo_root))
    assert rc == 0, err
    assert "report_2024.pdf" in out


def test_unknown_flag_rejection_powershell(repo_root, python_exe):
    es_cli = str(repo_root / "es_winsearch.py")
    cmd = _script(python_exe, es_cli, "--definitely-not-a-flag")
    rc, out, err = run_in_powershell(cmd, cwd=str(repo_root))
    assert rc != 0
    comb = (out + err).lower()
    assert "not supported" in comb or "unknown" in comb
    assert "help" in comb
