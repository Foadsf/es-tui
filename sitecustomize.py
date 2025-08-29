# Auto-imported by Python if found on sys.path.
# Provide os.startfile on non-Windows so unit tests can patch it.
import os

if not hasattr(os, "startfile"):

    def _startfile_placeholder(_path: str) -> None:  # pragma: no cover
        raise NotImplementedError("os.startfile is only available on Windows")

    os.startfile = _startfile_placeholder  # type: ignore[attr-defined]
