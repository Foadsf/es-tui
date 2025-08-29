# tests/system/test_tui_interaction.py
import os
import sys
import pytest

from tests.helpers.tui_driver import TuiDriver, _HAS_PYWINPTY
from tests.helpers.redact import normalize_for_snapshot, contains_all

pytestmark = [
    pytest.mark.skipif(os.name != "nt", reason="TUI tests currently require Windows"),
    pytest.mark.skipif(not _HAS_PYWINPTY, reason="pywinpty not available"),
]


def test_tui_basic_search(repo_root, golden_corpus, python_exe, tmp_path):
    # Launch es_tui.py
    app = [python_exe, str(repo_root / "es_tui.py")]
    env = {
        "ES_TUI_TEST": "1",
        "PYTHONUNBUFFERED": "1",
    }
    with TuiDriver(cmd=app, env=env) as d:
        d.type_text("report")
        d.press("ENTER")
        frames = d.collect_frames(duration=1.0)
        snap = normalize_for_snapshot(d.snapshot_text())
        # We don't assert exact layout, just that core tokens appear
        assert contains_all(snap, ["report", "pdf"])


def test_tui_header_wraparound(repo_root, python_exe):
    app = [python_exe, str(repo_root / "es_tui.py")]
    with TuiDriver(cmd=app, env={"ES_TUI_TEST": "1"}) as d:
        # Move focus to headers if needed (common TUIs: TAB toggles focus)
        d.press("TAB")  # to headers
        # Navigate across columns; ensure wraparound doesn't crash
        for _ in range(10):
            d.press("RIGHT")
        for _ in range(10):
            d.press("LEFT")
        frames = d.collect_frames(duration=0.6)
        assert d.snapshot_text() is not None  # survived navigation


def test_tui_bad_regex_feedback(repo_root, python_exe):
    app = [python_exe, str(repo_root / "es_tui.py")]
    with TuiDriver(cmd=app, env={"ES_TUI_TEST": "1"}) as d:
        d.type_text("[unclosed")
        d.press("ENTER")
        frames = d.collect_frames(duration=0.8)
        snap = d.snapshot_text().lower()
        # Expect some error messaging; your TUI writes a status line
        assert "error" in snap or "invalid" in snap or "regex" in snap
