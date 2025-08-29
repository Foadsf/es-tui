# tests/data/setup_corpus.py
"""
Optional one-shot corpus setup script if you prefer a static corpus in the repo
instead of the dynamic fixture in conftest.py.
"""
from __future__ import annotations
import pathlib
import os
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]
TARGET = ROOT / "tests" / "data" / "golden_corpus_static"


def main():
    TARGET.mkdir(parents=True, exist_ok=True)
    (TARGET / "basic").mkdir(exist_ok=True)
    (TARGET / "basic" / "report_2024.pdf").write_bytes(
        b"%PDF-1.4\n% quarterly revenue\n"
    )
    print(f"Wrote {TARGET}")

    if os.name == "nt":
        subprocess.run(
            ["attrib", "+h", str(TARGET / "basic" / "report_2024.pdf")], check=False
        )


if __name__ == "__main__":
    main()
