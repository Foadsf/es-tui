# tests/conftest.py
from __future__ import annotations
import os
import sys
import time
import shutil
import pathlib
import platform
import pytest

HERE = pathlib.Path(__file__).parent
ROOT = HERE.parent


@pytest.fixture(scope="session")
def is_windows() -> bool:
    return os.name == "nt"


@pytest.fixture(scope="session")
def repo_root() -> pathlib.Path:
    return ROOT


@pytest.fixture(scope="session")
def golden_corpus(
    tmp_path_factory: pytest.TempPathFactory, is_windows: bool
) -> pathlib.Path:
    """
    Materialize a tiny corpus we can query reliably.
    """
    base = tmp_path_factory.mktemp("golden_corpus")
    # Layout mirrors the plan
    (base / "basic").mkdir(parents=True, exist_ok=True)
    (base / "unicode").mkdir(parents=True, exist_ok=True)
    (base / "attributes").mkdir(parents=True, exist_ok=True)
    (base / "nested" / "deep" / "very").mkdir(parents=True, exist_ok=True)

    (base / "basic" / "report_2024.pdf").write_bytes(b"%PDF-1.4\n% quarterly revenue\n")
    (base / "basic" / "meeting_notes.txt").write_text(
        "Action items: follow up\n", encoding="utf-8"
    )
    (base / "basic" / "budget_final.xlsx").write_bytes(b"PK\x03\x04")  # zip header

    (base / "unicode" / "cafe_menu.md").write_text(
        "café crème\nnaïve\n", encoding="utf-8"
    )
    (base / "unicode" / "טקסט_עברי.txt").write_text("טקסט לדוגמה\n", encoding="utf-8")
    (base / "unicode" / "файл_кириллица.doc").write_bytes(b"DOCBIN")

    (base / "attributes" / "hidden_file.log").write_text("hidden!\n", encoding="utf-8")
    (base / "attributes" / "system_config.ini").write_text("[sys]\n", encoding="utf-8")
    (base / "attributes" / "temp_data.tmp").write_text("tmp\n", encoding="utf-8")

    (base / "nested" / "deep" / "very" / "long_path_file.txt").write_text(
        "lorem ipsum\n", encoding="utf-8"
    )

    # Set attributes on Windows (hidden, system)
    if is_windows:
        import subprocess

        subprocess.run(
            ["attrib", "+h", str(base / "attributes" / "hidden_file.log")], check=False
        )
        subprocess.run(
            ["attrib", "+s", str(base / "attributes" / "system_config.ini")],
            check=False,
        )

    # Give Windows Search some time to pick up changes (best effort)
    time.sleep(0.2)
    return base


@pytest.fixture
def chdir_tmp(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture(scope="session")
def python_exe() -> str:
    return sys.executable
