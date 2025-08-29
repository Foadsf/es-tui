# tests/helpers/tui_driver.py
"""
A lightweight TUI automation driver for curses apps on Windows.

Primary backend: pywinpty (CONPTY) to spawn an interactive console session,
send keystrokes, and capture screen text frames for snapshot assertions.

Fallback: plain subprocess with stdin/stdout pipes (reduced fidelity).

Notes:
- Designed for es_tui.py; works best when your TUI uses blocking getch()
  and repaints on key events.
- On slow machines/CI, tune the timeouts via env:
  ES_TUI_FRAME_TIMEOUT_MS, ES_TUI_STARTUP_TIMEOUT_MS
"""

from __future__ import annotations
import os
import sys
import time
import shutil
import signal
import contextlib
from dataclasses import dataclass
from typing import List, Optional, Tuple

# Optional dependencies
_HAS_PYWINPTY = False
try:
    import pywinpty  # type: ignore

    _HAS_PYWINPTY = True
except Exception:
    _HAS_PYWINPTY = False

DEFAULT_COLS = 120
DEFAULT_ROWS = 35


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "").strip() or default)
    except Exception:
        return default


FRAME_TIMEOUT = _env_int("ES_TUI_FRAME_TIMEOUT_MS", 500) / 1000.0
STARTUP_TIMEOUT = _env_int("ES_TUI_STARTUP_TIMEOUT_MS", 2500) / 1000.0


@dataclass
class TuiFrame:
    text: str
    when: float


@dataclass
class TuiRunResult:
    frames: List[TuiFrame]
    exit_code: Optional[int]
    crashed: bool


class TuiDriver:
    """
    High-level API:
        with TuiDriver(cmd=[sys.executable, "es_tui.py"]) as d:
            d.wait_ready()
            d.type_text("report")
            d.press("ENTER")
            frames = d.collect_frames(duration=0.8)
            d.quit()

    Keys:
        driver.press("LEFT"), driver.press("RIGHT"), driver.press("UP"), ...
        driver.type_text("hello")
        driver.send("\x1b")  # raw sequences allowed
    """

    def __init__(
        self,
        cmd: List[str],
        cols: int = DEFAULT_COLS,
        rows: int = DEFAULT_ROWS,
        cwd: Optional[str] = None,
        env: Optional[dict] = None,
        shell: Optional[str] = None,
    ):
        self.cmd = cmd
        self.cols = cols
        self.rows = rows
        self.cwd = cwd or os.getcwd()
        self.env = dict(os.environ)
        if env:
            self.env.update(env)
        # Hint for the app to behave nicely for tests (optional)
        self.env.setdefault("ES_TUI_TEST", "1")
        self.shell = shell  # unused; placeholder for parity
        self._frames: List[TuiFrame] = []
        self._pty = None
        self._proc = None
        self._alive = False

    # --- lifecycle ---------------------------------------------------------
    def __enter__(self) -> "TuiDriver":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.quit()

    def start(self) -> None:
        if os.name != "nt" or not _HAS_PYWINPTY:
            # Fallback: non-pty subprocess (limited screen fidelity)
            import subprocess

            self._proc = subprocess.Popen(
                self.cmd,
                cwd=self.cwd,
                env=self.env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=False,
            )
            self._alive = True
            # give app a moment to initialize
            time.sleep(STARTUP_TIMEOUT)
            self._capture_frame_fallback()
            return

        # pywinpty backend
        spawn = pywinpty.Process
        self._pty = pywinpty.PtyProcess.spawn(
            " ".join(self.cmd),
            dimensions=(self.rows, self.cols),
            cwd=self.cwd,
            env=self.env,
        )
        self._alive = True
        self._wait_for_startup()

    def _wait_for_startup(self):
        t0 = time.time()
        while time.time() - t0 < STARTUP_TIMEOUT:
            self._capture_frame_pty()
            # Heuristic: any non-empty output means we are “ready-ish”
            if self._frames and self._frames[-1].text.strip():
                break
            time.sleep(0.05)

    def quit(self) -> TuiRunResult:
        if not self._alive:
            return TuiRunResult(self._frames, None, False)

        crashed = False
        exit_code: Optional[int] = None

        with contextlib.suppress(Exception):
            self.press("q")  # many TUIs use 'q' to quit; harmless otherwise
            time.sleep(0.25)

        if self._pty is not None:  # pywinpty
            with contextlib.suppress(Exception):
                self._pty.write("\x03")  # Ctrl+C
                time.sleep(0.1)
            with contextlib.suppress(Exception):
                crashed = self._pty.isalive() is False
            with contextlib.suppress(Exception):
                # pywinpty doesn't expose an exit code in the same way
                pass
            with contextlib.suppress(Exception):
                self._pty.close()
        elif self._proc is not None:
            with contextlib.suppress(Exception):
                self._proc.send_signal(
                    signal.CTRL_BREAK_EVENT if os.name == "nt" else signal.SIGINT
                )
            t0 = time.time()
            while time.time() - t0 < 1.5:
                if self._proc.poll() is not None:
                    break
                time.sleep(0.05)
            with contextlib.suppress(Exception):
                if self._proc.poll() is None:
                    self._proc.terminate()
            with contextlib.suppress(Exception):
                if self._proc.poll() is None:
                    self._proc.kill()
            with contextlib.suppress(Exception):
                exit_code = self._proc.poll()
        self._alive = False
        return TuiRunResult(self._frames, exit_code, crashed)

    # --- interaction -------------------------------------------------------
    def press(self, key: str) -> None:
        """
        Send a single special key or character.
        Supported names: LEFT, RIGHT, UP, DOWN, HOME, END, PGUP, PGDN, ESC, ENTER, TAB
        """
        special = {
            "LEFT": "\x1b[D",
            "RIGHT": "\x1b[C",
            "UP": "\x1b[A",
            "DOWN": "\x1b[B",
            "HOME": "\x1b[H",
            "END": "\x1b[F",
            "PGUP": "\x1b[5~",
            "PGDN": "\x1b[6~",
            "ESC": "\x1b",
            "ENTER": "\r",
            "TAB": "\t",
        }
        payload = special.get(key.upper(), key)
        self.send(payload)

    def type_text(self, s: str, delay: float = 0.0) -> None:
        for ch in s:
            self.send(ch)
            if delay > 0:
                time.sleep(delay)

    def send(self, s: str) -> None:
        if not self._alive:
            return
        data = s.encode("utf-8", errors="ignore")
        if self._pty is not None:
            with contextlib.suppress(Exception):
                self._pty.write(data.decode("utf-8", errors="ignore"))
            self._capture_frame_pty()
        elif self._proc is not None and self._proc.stdin:
            with contextlib.suppress(Exception):
                self._proc.stdin.write(data)
                self._proc.stdin.flush()
            self._capture_frame_fallback()

    # --- capture -----------------------------------------------------------
    def collect_frames(
        self, duration: float = 0.5, interval: float = 0.05
    ) -> List[TuiFrame]:
        t0 = time.time()
        while time.time() - t0 < duration:
            self._capture_frame_pty() if self._pty else self._capture_frame_fallback()
            time.sleep(interval)
        return list(self._frames)

    def snapshot_text(self) -> str:
        return self._frames[-1].text if self._frames else ""

    def _capture_frame_pty(self):
        if not self._pty:
            return
        with contextlib.suppress(Exception):
            # Read anything available (non-blocking). pywinpty read blocks, so use a small timeout.
            time.sleep(FRAME_TIMEOUT)
            chunk = self._pty.read(4096)
            if chunk:
                txt = chunk.replace("\r", "")
                self._frames.append(TuiFrame(text=txt, when=time.time()))

    def _capture_frame_fallback(self):
        if not self._proc or not self._proc.stdout:
            return
        with contextlib.suppress(Exception):
            time.sleep(FRAME_TIMEOUT)
            # read what’s there without blocking forever
            if os.name == "nt":
                # On Windows, .read may block; use .peek if available
                import msvcrt  # type: ignore

                # No easy non-blocking on pipes; do a small timed read
                self._proc.stdout.flush()
            data = self._proc.stdout.read(1)
            if data:
                tail = (
                    data + self._proc.stdout.read1(4096)
                    if hasattr(self._proc.stdout, "read1")
                    else data + self._proc.stdout.read(4096)
                )
                txt = (tail or b"").decode("utf-8", errors="ignore").replace("\r", "")
                self._frames.append(TuiFrame(text=txt, when=time.time()))
