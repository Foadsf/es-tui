#!/usr/bin/env python3
"""
ES TUI - Comprehensive Text User Interface for Everything Search (es.exe)
A full-featured TUI that provides access to all ES functionality in an intuitive manner.
"""

import os
import sys
import subprocess
import json
import shlex
import threading
import time
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import argparse
import copy


import logging
from datetime import datetime

try:
    import curses
    from curses import panel
    from curses import ascii as cascii

    BACKSPACE_KEYS = {curses.KEY_BACKSPACE, 8, 127, cascii.BS, cascii.DEL}
    ENTER_KEYS = {curses.KEY_ENTER, 10, 13}
    DELETE_KEYS = {curses.KEY_DC, 330}  # many curses builds map KEY_DC to 330
except ImportError:
    print("Error: curses module not available. This TUI requires curses support.")
    sys.exit(1)


# ---------- FileTypeIcons ----------
class FileTypeIcons:
    UNICODE = {
        # Documents
        ".txt": "📄",
        ".doc": "📄",
        ".docx": "📄",
        ".pdf": "📕",
        ".rtf": "📄",
        ".odt": "📄",
        # Images
        ".jpg": "🖼️",
        ".jpeg": "🖼️",
        ".png": "🖼️",
        ".gif": "🖼️",
        ".bmp": "🖼️",
        ".svg": "🖼️",
        ".ico": "🖼️",
        # Video
        ".mp4": "🎬",
        ".avi": "🎬",
        ".mkv": "🎬",
        ".mov": "🎬",
        ".wmv": "🎬",
        ".flv": "🎬",
        # Audio
        ".mp3": "🎵",
        ".wav": "🎵",
        ".flac": "🎵",
        ".ogg": "🎵",
        ".m4a": "🎵",
        ".wma": "🎵",
        # Archives
        ".zip": "📦",
        ".rar": "📦",
        ".7z": "📦",
        ".tar": "📦",
        ".gz": "📦",
        ".bz2": "📦",
        # Code
        ".py": "🐍",
        ".js": "💛",
        ".html": "🌐",
        ".css": "🎨",
        ".cpp": "⚡",
        ".c": "⚡",
        ".java": "☕",
        ".php": "🔵",
        # Executables
        ".exe": "⚙️",
        ".msi": "⚙️",
        ".bat": "⚙️",
        ".cmd": "⚙️",
        # Folders/default
        "folder": "📁",
        "default": "📄",
    }

    ASCII = {
        ".txt": "T",
        ".doc": "W",
        ".docx": "W",
        ".pdf": "P",
        ".rtf": "R",
        ".odt": "W",
        ".jpg": "I",
        ".jpeg": "I",
        ".png": "I",
        ".gif": "I",
        ".bmp": "I",
        ".svg": "I",
        ".ico": "I",
        ".mp4": "V",
        ".avi": "V",
        ".mkv": "V",
        ".mov": "V",
        ".wmv": "V",
        ".flv": "V",
        ".mp3": "A",
        ".wav": "A",
        ".flac": "A",
        ".ogg": "A",
        ".m4a": "A",
        ".wma": "A",
        ".zip": "Z",
        ".rar": "R",
        ".7z": "7",
        ".tar": "T",
        ".gz": "G",
        ".bz2": "B",
        ".py": "P",
        ".js": "J",
        ".html": "H",
        ".css": "C",
        ".cpp": "C",
        ".c": "C",
        ".java": "J",
        ".php": "P",
        ".exe": "X",
        ".msi": "M",
        ".bat": "B",
        ".cmd": "B",
        "folder": "D",
        "default": "F",
    }

    @classmethod
    def get_icon(cls, result, use_unicode: bool = True) -> str:
        if getattr(result, "is_folder", False):
            return cls.UNICODE["folder"] if use_unicode else cls.ASCII["folder"]
        ext = os.path.splitext(getattr(result, "filename", ""))[1].lower()
        table = cls.UNICODE if use_unicode else cls.ASCII
        return table.get(ext, table["default"])


# --- PyExifTool integration ---
try:
    import exiftool  # from PyExifTool package

    HAVE_PYEXIFTOOL = True
except Exception:
    exiftool = None
    HAVE_PYEXIFTOOL = False
    logging.warning("PyExifTool not available. Extended metadata will be disabled.")

# ---------- Properties helpers (Windows-first) ----------
import datetime as _dt


def _fmt_ts(ts: float) -> str:
    try:
        # local time, human-friendly
        return _dt.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ""


def _fmt_bytes(n: int) -> str:
    try:
        for unit in ["B", "KB", "MB", "GB", "TB", "PB"]:
            if n < 1024 or unit == "PB":
                return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
            n /= 1024.0
    except Exception:
        return str(n)


def _windows_get_attrs(path: str) -> Dict[str, str]:
    import ctypes
    from ctypes import wintypes as wt

    attrs = {}
    # Attributes
    GetFileAttributesW = ctypes.windll.kernel32.GetFileAttributesW
    GetFileAttributesW.argtypes = [wt.LPCWSTR]
    GetFileAttributesW.restype = wt.DWORD
    fa = GetFileAttributesW(path)
    flags = []
    if fa != 0xFFFFFFFF:
        pairs = [
            (0x0001, "READONLY"),
            (0x0002, "HIDDEN"),
            (0x0004, "SYSTEM"),
            (0x0010, "DIR"),
            (0x0020, "ARCHIVE"),
            (0x0400, "COMPRESSED"),
            (0x2000, "ENCRYPTED"),
            (0x04000, "REPARSE"),
            (0x0800, "NOTINDEXED"),
            (0x1000, "OFFLINE"),
            (0x0200, "TEMP"),
        ]
        for bit, name in pairs:
            if fa & bit:
                flags.append(name)
    attrs["attributes"] = " ".join(flags) if flags else ""

    # Size on disk (allocated/“compressed” size is what Explorer shows)
    GetCompressedFileSizeW = ctypes.windll.kernel32.GetCompressedFileSizeW
    GetCompressedFileSizeW.argtypes = [wt.LPCWSTR, wt.LPDWORD]
    GetCompressedFileSizeW.restype = wt.DWORD
    high = wt.DWORD(0)
    low = GetCompressedFileSizeW(path, ctypes.byref(high))
    if low == 0xFFFFFFFF:
        # failure → fall back to logical size
        sz_on_disk = os.path.getsize(path) if os.path.isfile(path) else 0
    else:
        sz_on_disk = (high.value << 32) | low
    attrs["size_on_disk"] = sz_on_disk

    # Associated type & app
    attrs.update(_windows_assoc_info(path))

    # Owner (PowerShell – no backslashes inside f-string expressions)
    try:
        # PowerShell single-quoted literal: escape single quotes by doubling them
        ps_path = path.replace("'", "''")
        ps_cmd = f"(Get-Acl -LiteralPath '{ps_path}').Owner"

        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            capture_output=True,
            text=True,
            timeout=2,
        )
        owner = r.stdout.strip() or ""
    except Exception:
        owner = ""
    attrs["owner"] = owner

    # MOTW / “blocked”?
    blocked = False
    try:
        if os.path.isfile(path):
            with open(path + ":Zone.Identifier", "r", encoding="utf-8") as f:
                blocked = True
    except Exception:
        blocked = False
    attrs["blocked"] = "Yes" if blocked else "No"

    return attrs


def _windows_assoc_info(path: str) -> Dict[str, str]:
    """Best-effort file type description and associated open command."""
    import winreg

    info = {"type": "", "opens_with": ""}
    ext = os.path.splitext(path)[1].lower()
    progid = ""

    # UserChoice first
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            rf"Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\{ext}\UserChoice",
        ) as k:
            progid, _ = winreg.QueryValueEx(k, "ProgId")
    except Exception:
        pass

    # Fallback: HKCR\.ext default
    if not progid:
        try:
            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, ext) as k:
                progid, _ = winreg.QueryValueEx(k, None)
        except Exception:
            pass

    # Type (friendly)
    if progid:
        try:
            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, progid) as k:
                type_desc, _ = winreg.QueryValueEx(k, None)
                info["type"] = str(type_desc)
        except Exception:
            pass
        # Open command
        try:
            with winreg.OpenKey(
                winreg.HKEY_CLASSES_ROOT, rf"{progid}\shell\open\command"
            ) as k:
                cmd, _ = winreg.QueryValueEx(k, None)
                exe = ""
                if cmd.startswith('"'):
                    exe = cmd.split('"')[1]
                else:
                    exe = cmd.split(" ")[0]
                info["opens_with"] = exe
        except Exception:
            pass

    # Last resort friendly type
    if not info["type"]:
        info["type"] = f"{ext.upper()} file" if ext else "File"
    return info


def gather_file_properties(path: str) -> Dict[str, str]:
    """Portable wrapper to collect Explorer-like properties."""
    d: Dict[str, str] = {}
    try:
        st = os.stat(path)
    except Exception as e:
        logging.error(f"stat failed for {path}: {e}")
        return {"Error": str(e)}

    d["Name"] = os.path.basename(path.rstrip("\\/"))
    d["Location"] = os.path.dirname(path)
    d["Size"] = _fmt_bytes(st.st_size) if os.path.isfile(path) else ""
    d["Created"] = _fmt_ts(st.st_ctime)
    d["Modified"] = _fmt_ts(st.st_mtime)
    d["Accessed"] = _fmt_ts(st.st_atime)

    if sys.platform.startswith("win"):
        w = _windows_get_attrs(path)
        if d.get("Size"):
            d["Size on disk"] = _fmt_bytes(w.get("size_on_disk", 0))
        d["Type"] = w.get("type", "")
        d["Opens with"] = w.get("opens_with", "")
        if w.get("owner"):
            d["Owner"] = w["owner"]
        if w.get("attributes"):
            d["Attributes"] = w["attributes"]
        d["Blocked"] = w.get("blocked", "No")
    else:
        # simple hints for non-Windows
        d["Type"] = (
            "Folder"
            if os.path.isdir(path)
            else (os.path.splitext(path)[1].upper() + " file")
        )
    return d


def open_with_default_app(path: str) -> bool:
    """Open a file/folder with the OS default application. Non-blocking."""
    try:
        if sys.platform.startswith("win"):
            # Equivalent to: start "" "<path>" → uses Shell file associations
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
        logging.debug(f"Opened with default app: {path}")
        return True
    except Exception as e:
        logging.error(f"Open failed for {path}: {e}", exc_info=True)
        return False


class SearchMode(Enum):
    NORMAL = "normal"
    REGEX = "regex"
    WHOLE_WORD = "whole_word"
    CASE_SENSITIVE = "case_sensitive"
    MATCH_PATH = "match_path"


class SortMode(Enum):
    NAME = "name"
    PATH = "path"
    SIZE = "size"
    EXTENSION = "extension"
    DATE_CREATED = "date-created"
    DATE_MODIFIED = "date-modified"
    DATE_ACCESSED = "date-accessed"
    ATTRIBUTES = "attributes"


class OutputFormat(Enum):
    DEFAULT = "default"
    CSV = "csv"
    EFU = "efu"
    TXT = "txt"
    M3U = "m3u"
    M3U8 = "m3u8"


@dataclass
class SearchOptions:
    query: str = ""
    mode: SearchMode = SearchMode.NORMAL
    sort_field: SortMode = SortMode.NAME
    sort_ascending: bool = True
    max_results: int = 1000
    offset: int = 0
    match_diacritics: bool = False
    show_size: bool = True
    show_date_modified: bool = True
    show_date_created: bool = False
    show_date_accessed: bool = False
    show_attributes: bool = False
    show_extension: bool = True
    files_only: bool = False
    folders_only: bool = False
    highlight: bool = True
    path_filter: str = ""
    parent_path_filter: str = ""
    instance_name: str = ""
    timeout: int = 0
    attributes_filter: str = ""
    size_format: int = 1  # 0=Auto, 1=Bytes, 2=KB, 3=MB
    date_format: int = 0  # 0=System, 1=ISO-8601, 2=FILETIME, 3=ISO-8601 UTC
    custom_columns: List[str] = field(default_factory=list)
    show_icons: bool = True
    use_unicode_icons: bool = True  # set False for ASCII fallback


@dataclass
class SearchResult:
    filename: str
    full_path: str
    size: int = 0
    date_modified: str = ""
    date_created: str = ""
    date_accessed: str = ""
    attributes: str = ""
    extension: str = ""
    is_folder: bool = False


@dataclass
class AdvancedSearchOptions:
    """Dataclass to hold the state of the advanced search form."""

    # Basic search fields
    search_text: str = ""
    search_mode: str = "normal"  # normal, regex, case, whole-word, match-path
    match_diacritics: bool = False

    # File type filters
    files_only: bool = False
    folders_only: bool = False
    file_extensions: str = ""  # comma-separated

    # Size filters
    size_min: str = ""
    size_max: str = ""
    size_format: str = "auto"  # auto, bytes, kb, mb

    # Date filters
    date_created_min: str = ""
    date_created_max: str = ""
    date_modified_min: str = ""
    date_modified_max: str = ""
    date_accessed_min: str = ""
    date_accessed_max: str = ""

    # Path filters
    path_filter: str = ""
    parent_path_filter: str = ""

    # Attributes (Windows DIR style)
    attributes_include: str = ""  # e.g., "rhs" for read-only, hidden, system
    attributes_exclude: str = ""  # e.g., "d" to exclude directories

    # Sort options
    sort_field: str = "name"
    sort_order: str = "ascending"

    # Display options
    max_results: str = "1000"
    offset: str = "0"
    highlight_results: bool = False

    # Instance
    instance_name: str = ""


class Colors:
    def __init__(self):
        try:
            curses.start_color()
            curses.use_default_colors()

            # Define custom colors using the new palette
            # Dark slate blue background, light text
            curses.init_pair(
                1, curses.COLOR_WHITE, curses.COLOR_BLUE
            )  # Header - will adjust with custom colors if available
            curses.init_pair(
                2, curses.COLOR_BLACK, curses.COLOR_RED
            )  # Highlight - coral background
            curses.init_pair(
                3, curses.COLOR_WHITE, curses.COLOR_BLACK
            )  # Success - keep as is
            curses.init_pair(
                4, curses.COLOR_RED, curses.COLOR_BLACK
            )  # Error - keep red
            curses.init_pair(
                5, curses.COLOR_BLUE, curses.COLOR_BLACK
            )  # Info - slate blue text
            curses.init_pair(
                6, curses.COLOR_RED, curses.COLOR_BLACK
            )  # Folder - coral text
            curses.init_pair(7, curses.COLOR_WHITE, curses.COLOR_BLACK)  # Normal
            curses.init_pair(
                8, curses.COLOR_BLACK, curses.COLOR_YELLOW
            )  # Selected - cream background

            # Try to define custom colors if terminal supports it
            if curses.can_change_color() and curses.COLORS >= 256:
                try:
                    # Define custom colors (values are 0-1000 in curses)
                    curses.init_color(20, 364, 408, 541)  # Slate blue #5D688A
                    curses.init_color(21, 969, 647, 647)  # Coral pink #F7A5A5
                    curses.init_color(22, 1000, 859, 714)  # Light cream #FFDBB6
                    curses.init_color(23, 1000, 949, 937)  # Very light cream #FFF2EF

                    # Redefine color pairs with custom colors
                    curses.init_pair(
                        1, curses.COLOR_WHITE, 20
                    )  # Header - white on slate blue
                    curses.init_pair(
                        2, curses.COLOR_BLACK, 21
                    )  # Highlight - black on coral
                    curses.init_pair(
                        5, 20, curses.COLOR_BLACK
                    )  # Info - slate blue text
                    curses.init_pair(6, 21, curses.COLOR_BLACK)  # Folder - coral text
                    curses.init_pair(
                        8, curses.COLOR_BLACK, 22
                    )  # Selected - black on cream
                except:
                    pass  # Fall back to standard colors if custom colors fail

            self.HEADER = curses.color_pair(1) | curses.A_BOLD
            self.HIGHLIGHT = curses.color_pair(2) | curses.A_BOLD
            self.SUCCESS = curses.color_pair(3)
            self.ERROR = curses.color_pair(4) | curses.A_BOLD
            self.INFO = curses.color_pair(5)
            self.FOLDER = curses.color_pair(6) | curses.A_BOLD
            self.NORMAL = curses.color_pair(7)
            self.SELECTED = curses.color_pair(8)
        except Exception:
            # Fall back to no-color attributes
            self.HEADER = getattr(curses, "A_BOLD", 0)
            self.HIGHLIGHT = getattr(curses, "A_BOLD", 0)
            self.SUCCESS = 0
            self.ERROR = getattr(curses, "A_BOLD", 0)
            self.INFO = 0
            self.FOLDER = getattr(curses, "A_BOLD", 0)
            self.NORMAL = 0
            self.SELECTED = 0


class StatusBar:
    def __init__(self, stdscr, y: int):
        self.stdscr = stdscr
        self.y = y
        self.height, self.width = stdscr.getmaxyx()

    def update(self, message: str, color_attr=None):
        if color_attr is None:
            color_attr = curses.A_REVERSE

        self.stdscr.move(self.y, 0)
        self.stdscr.clrtoeol()
        self.stdscr.addstr(self.y, 0, message[: self.width - 1], color_attr)
        self.stdscr.refresh()


class InputDialog:
    def __init__(self, stdscr, title: str, prompt: str, initial_value: str = ""):
        self.stdscr = stdscr
        self.title = title
        self.prompt = prompt
        self.value = initial_value
        self.colors = Colors()

    def show(self) -> Optional[str]:
        try:
            H, W = self.stdscr.getmaxyx()
            dialog_h = 7
            dialog_w = min(60, max(30, W - 4))
            y0 = (H - dialog_h) // 2
            x0 = (W - dialog_w) // 2

            win = curses.newwin(dialog_h, dialog_w, y0, x0)
            win.keypad(True)
            cursor_pos = len(self.value)

            while True:
                win.clear()
                try:
                    win.box()
                except Exception:
                    pass

                # Title
                title = f" {self.title} "
                tx = max(1, (dialog_w - len(title)) // 2)
                safe_addstr(win, 0, tx, title, getattr(self.colors, "HEADER", 0))

                # Prompt & input field
                safe_addstr(win, 2, 2, self.prompt, getattr(self.colors, "NORMAL", 0))
                field_x = 2
                field_w = dialog_w - 4
                # draw reversed field bg
                safe_addstr(win, 3, field_x, " " * (field_w - 1), curses.A_REVERSE)

                # clip display
                if cursor_pos >= field_w - 1:
                    start = cursor_pos - (field_w - 2)
                else:
                    start = 0
                shown = self.value[start : start + field_w - 1]
                try:
                    win.addstr(3, field_x, shown, curses.A_REVERSE)
                except Exception:
                    safe_addstr(win, 3, field_x, shown)

                safe_addstr(
                    win,
                    dialog_h - 2,
                    2,
                    "Enter: Accept  Esc: Cancel",
                    getattr(self.colors, "INFO", 0),
                )

                # place cursor (avoid last column)
                cx = field_x + min(cursor_pos - start, field_w - 2)
                try:
                    win.move(3, cx)
                except Exception:
                    pass

                win.refresh()
                key = win.getch()

                if key == 27:  # ESC
                    return None
                elif key in (curses.KEY_ENTER, 10, 13):
                    return self.value
                elif key in BACKSPACE_KEYS:
                    if cursor_pos > 0:
                        self.value = (
                            self.value[: cursor_pos - 1] + self.value[cursor_pos:]
                        )
                        cursor_pos -= 1
                elif key == curses.KEY_DC:
                    if cursor_pos < len(self.value):
                        self.value = (
                            self.value[:cursor_pos] + self.value[cursor_pos + 1 :]
                        )
                elif key == curses.KEY_LEFT:
                    cursor_pos = max(0, cursor_pos - 1)
                elif key == curses.KEY_RIGHT:
                    cursor_pos = min(len(self.value), cursor_pos + 1)
                elif key == curses.KEY_HOME:
                    cursor_pos = 0
                elif key == curses.KEY_END:
                    cursor_pos = len(self.value)
                elif 32 <= key <= 126:
                    self.value = (
                        self.value[:cursor_pos] + chr(key) + self.value[cursor_pos:]
                    )
                    cursor_pos += 1
        finally:
            try:
                win.erase()
                win.refresh()
                self.stdscr.touchwin()
                self.stdscr.refresh()
            except Exception:
                pass


class OptionsDialog:
    def __init__(self, stdscr, options: SearchOptions):
        self.stdscr = stdscr
        self.options = options
        self.colors = Colors()
        self.current_item = 0

        # Define option items
        self.items = [
            ("Search Mode", self._get_search_mode_text),
            ("Sort Field", self._get_sort_field_text),
            ("Sort Order", self._get_sort_order_text),
            ("Max Results", lambda: str(self.options.max_results)),
            ("Show Size Column", lambda: "Yes" if self.options.show_size else "No"),
            (
                "Show Date Modified",
                lambda: "Yes" if self.options.show_date_modified else "No",
            ),
            (
                "Show Date Created",
                lambda: "Yes" if self.options.show_date_created else "No",
            ),
            (
                "Show Attributes",
                lambda: "Yes" if self.options.show_attributes else "No",
            ),
            ("Files Only", lambda: "Yes" if self.options.files_only else "No"),
            ("Folders Only", lambda: "Yes" if self.options.folders_only else "No"),
            (
                "Match Diacritics",
                lambda: "Yes" if self.options.match_diacritics else "No",
            ),
            ("Highlight Results", lambda: "Yes" if self.options.highlight else "No"),
            ("Path Filter", lambda: self.options.path_filter or "(none)"),
            ("Instance Name", lambda: self.options.instance_name or "(default)"),
            ("Size Format", self._get_size_format_text),
            ("Date Format", self._get_date_format_text),
        ]

    def _get_search_mode_text(self):
        mode_names = {
            SearchMode.NORMAL: "Normal",
            SearchMode.REGEX: "Regular Expression",
            SearchMode.WHOLE_WORD: "Whole Words",
            SearchMode.CASE_SENSITIVE: "Case Sensitive",
            SearchMode.MATCH_PATH: "Match Full Path",
        }
        return mode_names.get(self.options.mode, "Normal")

    def _get_sort_field_text(self):
        field_names = {
            SortMode.NAME: "Name",
            SortMode.PATH: "Path",
            SortMode.SIZE: "Size",
            SortMode.EXTENSION: "Extension",
            SortMode.DATE_CREATED: "Date Created",
            SortMode.DATE_MODIFIED: "Date Modified",
            SortMode.DATE_ACCESSED: "Date Accessed",
            SortMode.ATTRIBUTES: "Attributes",
        }
        return field_names.get(self.options.sort_field, "Name")

    def _get_sort_order_text(self):
        return "Ascending" if self.options.sort_ascending else "Descending"

    def _get_size_format_text(self):
        formats = ["Auto", "Bytes", "KB", "MB"]
        return (
            formats[self.options.size_format]
            if 0 <= self.options.size_format < len(formats)
            else "Auto"
        )

    def _get_date_format_text(self):
        formats = ["System", "ISO-8601", "FILETIME", "ISO-8601 UTC"]
        return (
            formats[self.options.date_format]
            if 0 <= self.options.date_format < len(formats)
            else "System"
        )

    def show(self) -> bool:
        try:
            logging.debug("OptionsDialog.show() called")
            H, W = self.stdscr.getmaxyx()

            # Build the lines once so we can size the dialog safely
            def render_lines():
                return [
                    " Search Options ",  # title placeholder
                    "",  # spacer
                    *[f"{label:<20}: {value()}" for (label, value) in self.items],
                    "",
                    "↑↓: Navigate  Enter: Edit  Esc: Close",
                ]

            lines = render_lines()
            dialog_h = min(max(10, len(lines) + 2), max(8, H - 2))
            dialog_w = min(max(48, max(len(s) for s in lines) + 4), max(28, W - 4))
            y0 = (H - dialog_h) // 2
            x0 = (W - dialog_w) // 2
            logging.debug(f"Options dialog dims: {dialog_h}x{dialog_w} at ({y0},{x0})")

            win = curses.newwin(dialog_h, dialog_w, y0, x0)
            win.keypad(True)

            top_idx = 0
            visible_rows = dialog_h - 5  # border + title + footer

            while True:
                win.clear()
                try:
                    win.box()
                except Exception:
                    pass

                # Title (centered)
                title = " Options "
                tx = max(1, (dialog_w - len(title)) // 2)
                safe_addstr(win, 0, tx, title, getattr(self.colors, "HEADER", 0))

                # Recompute lines each frame (values can change)
                lines = [f"{label:<20}: {value()}" for (label, value) in self.items]

                # Scroll window around current selection
                if self.current_item < top_idx:
                    top_idx = self.current_item
                if self.current_item >= top_idx + visible_rows:
                    top_idx = self.current_item - visible_rows + 1

                # Body
                for i in range(visible_rows):
                    idx = top_idx + i
                    if idx >= len(lines):
                        break
                    attr = (
                        getattr(self.colors, "SELECTED", 0)
                        if idx == self.current_item
                        else getattr(self.colors, "NORMAL", 0)
                    )
                    safe_addstr(win, 2 + i, 2, lines[idx], attr)

                # Footer
                footer = "↑↓: Navigate  Enter: Edit  Esc: Close"
                safe_addstr(
                    win, dialog_h - 2, 2, footer, getattr(self.colors, "INFO", 0)
                )

                win.refresh()
                key = win.getch()

                if key == 27:  # ESC
                    break
                elif key == curses.KEY_UP:
                    self.current_item = max(0, self.current_item - 1)
                elif key == curses.KEY_DOWN:
                    self.current_item = min(len(self.items) - 1, self.current_item + 1)
                elif key in (curses.KEY_ENTER, 10, 13):
                    try:
                        self._edit_current_option()
                    except Exception:
                        logging.error("Error editing option", exc_info=True)

            # Cleanup
            try:
                win.erase()
                win.refresh()
                self.stdscr.touchwin()
                self.stdscr.refresh()
            except Exception:
                pass
            logging.debug("OptionsDialog.show() finished")
            return True
        except Exception:
            logging.error("OptionsDialog.show() fatal", exc_info=True)
            try:
                self.stdscr.touchwin()
                self.stdscr.refresh()
            except Exception:
                pass
            return False

    def _edit_current_option(self):
        item_name, _ = self.items[self.current_item]

        if item_name == "Search Mode":
            self._cycle_search_mode()
        elif item_name == "Sort Field":
            self._cycle_sort_field()
        elif item_name == "Sort Order":
            self.options.sort_ascending = not self.options.sort_ascending
        elif item_name == "Max Results":
            self._edit_max_results()
        elif item_name in [
            "Show Size Column",
            "Show Date Modified",
            "Show Date Created",
            "Show Attributes",
            "Files Only",
            "Folders Only",
            "Match Diacritics",
            "Highlight Results",
        ]:
            self._toggle_boolean_option(item_name)
        elif item_name in ["Path Filter", "Instance Name"]:
            self._edit_string_option(item_name)
        elif item_name == "Size Format":
            self.options.size_format = (self.options.size_format + 1) % 4
        elif item_name == "Date Format":
            self.options.date_format = (self.options.date_format + 1) % 4

    def _cycle_search_mode(self):
        modes = list(SearchMode)
        current_idx = modes.index(self.options.mode)
        self.options.mode = modes[(current_idx + 1) % len(modes)]

    def _cycle_sort_field(self):
        fields = list(SortMode)
        current_idx = fields.index(self.options.sort_field)
        self.options.sort_field = fields[(current_idx + 1) % len(fields)]

    def _edit_max_results(self):
        dialog = InputDialog(
            self.stdscr,
            "Max Results",
            "Enter maximum results:",
            str(self.options.max_results),
        )
        result = dialog.show()
        if result and result.isdigit():
            self.options.max_results = int(result)

    def _toggle_boolean_option(self, option_name):
        mapping = {
            "Show Size Column": "show_size",
            "Show Date Modified": "show_date_modified",
            "Show Date Created": "show_date_created",
            "Show Attributes": "show_attributes",
            "Files Only": "files_only",
            "Folders Only": "folders_only",
            "Match Diacritics": "match_diacritics",
            "Highlight Results": "highlight",
        }

        attr_name = mapping.get(option_name)
        if attr_name:
            current_value = getattr(self.options, attr_name)
            setattr(self.options, attr_name, not current_value)

    def _edit_string_option(self, option_name):
        mapping = {
            "Path Filter": ("path_filter", "Enter path filter:"),
            "Instance Name": ("instance_name", "Enter instance name:"),
        }

        attr_name, prompt = mapping.get(option_name, ("", ""))
        if attr_name:
            current_value = getattr(self.options, attr_name)
            dialog = InputDialog(self.stdscr, option_name, prompt, current_value)
            result = dialog.show()
            if result is not None:
                setattr(self.options, attr_name, result)


class HelpDialog:
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.colors = Colors()

        self.help_text = [
            "ES TUI - Everything Search Text User Interface",
            "",
            "KEYBOARD SHORTCUTS:",
            "  F1, ?          - Show this help",
            "  F2, Ctrl+O     - Open search options",
            "  F3, Ctrl+E     - Export results",
            "  F4             - Advanced Search",
            "  F5, Ctrl+R     - Refresh/new search",
            "  F6, x          - Show EXIF metadata",
            "  F7             - Toggle file icons",
            "  F8             - Toggle Unicode/ASCII icons",
            "  F10, Ctrl+Q    - Quit",
            "  Tab            - Focus next panel",
            "  Esc            - Return to search field",
            "",
            "SEARCH FIELD:",
            "  Type to search, Enter to execute",
            "  Everything search syntax supported",
            "",
            "RESULTS LIST:",
            "  ↑↓ or j/k      - Navigate results",
            "  PgUp/PgDn      - Scroll by page",
            "  Home/End       - Go to first/last result",
            "  Space          - Toggle properties panel",
            "  c              - Copy path/location to clipboard",
            "",
            "SEARCH MODES:",
            "  Normal         - Standard Everything search",
            "  Regex          - Regular expression search",
            "  Whole Word     - Match whole words only",
            "  Case Sensitive - Case-sensitive search",
            "  Match Path     - Search in full path",
            "",
            "EXPORT FORMATS:",
            "  CSV, EFU, TXT, M3U, M3U8",
            "",
            "Press any key to close help...",
        ]

    def show(self):
        try:
            logging.debug("HelpDialog.show() called")
            H, W = self.stdscr.getmaxyx()
            dialog_h = min(len(self.help_text) + 4, H - 2)
            dialog_w = min(80, W - 4)
            start_y = (H - dialog_h) // 2
            start_x = (W - dialog_w) // 2

            logging.debug(
                f"Dialog dimensions: {dialog_h}x{dialog_w} at ({start_y}, {start_x})"
            )

            win = curses.newwin(dialog_h, dialog_w, start_y, start_x)
            win.keypad(True)
            win.clear()
            win.box()

            # Title
            title = " Help "
            title_x = max(1, (dialog_w - len(title)) // 2)
            safe_addstr(win, 0, title_x, title, self.colors.HEADER)

            # Body (use safe_addstr)
            for i, line in enumerate(self.help_text):
                if i >= dialog_h - 3:
                    break
                y = i + 2
                if line.startswith("  "):
                    safe_addstr(win, y, 2, line, self.colors.INFO)
                elif line.endswith(":"):
                    safe_addstr(win, y, 2, line, self.colors.HIGHLIGHT)
                else:
                    safe_addstr(win, y, 2, line, self.colors.NORMAL)

            win.refresh()
            logging.debug("Help dialog displayed, waiting for key")
            _ = win.getch()

            # Clean up
            win.erase()
            win.refresh()
            self.stdscr.touchwin()
            self.stdscr.refresh()
            logging.debug("Help dialog cleanup complete")

        except Exception as e:
            logging.error(f"Error in HelpDialog.show(): {e}", exc_info=True)
            try:
                self.stdscr.touchwin()
                self.stdscr.refresh()
            except:
                pass


class AdvancedSearchDialog:
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.colors = Colors()
        self.options = AdvancedSearchOptions()
        self.current_field_idx = 0
        self.is_active = True
        self.scroll_offset = 0

        # Define all form fields with their types and options
        self.fields = [
            ("Search Text:", "search_text", "text"),
            (
                "Search Mode:",
                "search_mode",
                "select",
                ["normal", "regex", "case", "whole-word", "match-path"],
            ),
            ("Match Diacritics:", "match_diacritics", "bool"),
            ("", "", "separator"),
            ("Files Only:", "files_only", "bool"),
            ("Folders Only:", "folders_only", "bool"),
            ("File Extensions:", "file_extensions", "text", "Example: pdf,doc,txt"),
            ("", "", "separator"),
            ("Size Min:", "size_min", "text", "Examples: 1mb, 500kb, 1000"),
            ("Size Max:", "size_max", "text", "Examples: 10mb, 5000kb"),
            ("", "", "separator"),
            ("Date Created Min:", "date_created_min", "text", "Example: 2024-01-01"),
            ("Date Created Max:", "date_created_max", "text", "Example: 2024-12-31"),
            ("Date Modified Min:", "date_modified_min", "text", "Example: lastweek"),
            ("Date Modified Max:", "date_modified_max", "text", "Example: today"),
            ("Date Accessed Min:", "date_accessed_min", "text", "Example: yesterday"),
            ("Date Accessed Max:", "date_accessed_max", "text", "Example: now"),
            ("", "", "separator"),
            ("Path Filter:", "path_filter", "text", "Example: C:\\Users\\"),
            (
                "Parent Path Filter:",
                "parent_path_filter",
                "text",
                "Example: C:\\Windows\\",
            ),
            ("", "", "separator"),
            (
                "Attributes Include:",
                "attributes_include",
                "text",
                "Example: rhs (read-only,hidden,system)",
            ),
            (
                "Attributes Exclude:",
                "attributes_exclude",
                "text",
                "Example: d (exclude directories)",
            ),
            ("", "", "separator"),
            (
                "Sort Field:",
                "sort_field",
                "select",
                [
                    "name",
                    "path",
                    "size",
                    "extension",
                    "date-created",
                    "date-modified",
                    "date-accessed",
                    "attributes",
                ],
            ),
            ("Sort Order:", "sort_order", "select", ["ascending", "descending"]),
            ("", "", "separator"),
            ("Max Results:", "max_results", "text"),
            ("Offset:", "offset", "text"),
            ("Highlight Results:", "highlight_results", "bool"),
            ("Instance Name:", "instance_name", "text"),
        ]

    def build_query(self) -> str:
        """Constructs a comprehensive es.exe query string from all fields."""
        parts = []

        # Basic search text
        if self.options.search_text.strip():
            parts.append(self.options.search_text.strip())

        # File type filters using ES syntax
        if self.options.files_only:
            parts.append("/a-d")
        elif self.options.folders_only:
            parts.append("/ad")

        # File extensions
        if self.options.file_extensions.strip():
            exts = [
                ext.strip()
                for ext in self.options.file_extensions.split(",")
                if ext.strip()
            ]
            if len(exts) == 1:
                parts.append(f"*.{exts[0]}")
            elif len(exts) > 1:
                # Multiple extensions: use OR logic
                ext_query = " | ".join([f"*.{ext}" for ext in exts])
                parts.append(f"({ext_query})")

        # Size filters
        if self.options.size_min.strip():
            parts.append(f"size:>={self.options.size_min}")
        if self.options.size_max.strip():
            parts.append(f"size:<={self.options.size_max}")

        # Date filters
        date_filters = [
            ("dc", "date_created_min", "date_created_max"),
            ("dm", "date_modified_min", "date_modified_max"),
            ("da", "date_accessed_min", "date_accessed_max"),
        ]

        for prefix, min_attr, max_attr in date_filters:
            min_val = getattr(self.options, min_attr).strip()
            max_val = getattr(self.options, max_attr).strip()
            if min_val:
                parts.append(f"{prefix}:>={min_val}")
            if max_val:
                parts.append(f"{prefix}:<={max_val}")

        # Path filters
        if self.options.path_filter.strip():
            parts.append(f'path:"{self.options.path_filter}"')
        if self.options.parent_path_filter.strip():
            parts.append(f'parent:"{self.options.parent_path_filter}"')

        # Attributes
        if self.options.attributes_include.strip():
            parts.append(f"/a{self.options.attributes_include}")
        if self.options.attributes_exclude.strip():
            parts.append(f"/a-{self.options.attributes_exclude}")

        return " ".join(parts) if parts else ""

    def build_command_args(self) -> List[str]:
        """Build the complete command line arguments for es.exe."""
        args = []

        # Search mode
        if self.options.search_mode == "regex":
            args.append("-regex")
        elif self.options.search_mode == "case":
            args.append("-case")
        elif self.options.search_mode == "whole-word":
            args.append("-whole-word")
        elif self.options.search_mode == "match-path":
            args.append("-match-path")

        if self.options.match_diacritics:
            args.append("-diacritics")

        # Sort
        if self.options.sort_field != "name":
            args.extend(["-sort", self.options.sort_field])
        if self.options.sort_order == "descending":
            args.append("-sort-descending")

        # Limits
        if self.options.max_results.strip() and self.options.max_results != "1000":
            try:
                max_res = int(self.options.max_results)
                args.extend(["-max-results", str(max_res)])
            except ValueError:
                pass

        if self.options.offset.strip() and self.options.offset != "0":
            try:
                offset = int(self.options.offset)
                args.extend(["-offset", str(offset)])
            except ValueError:
                pass

        # Highlighting
        if self.options.highlight_results:
            args.append("-highlight")

        # Instance
        if self.options.instance_name.strip():
            args.extend(["-instance", self.options.instance_name])

        # Path filters (separate from search text)
        if self.options.path_filter.strip():
            args.extend(["-path", self.options.path_filter])
        if self.options.parent_path_filter.strip():
            args.extend(["-parent-path", self.options.parent_path_filter])

        return args

    def show(self) -> Optional[str]:
        """Display the advanced search dialog and return the query string."""
        H, W = self.stdscr.getmaxyx()
        dialog_h = min(H - 4, 30)
        dialog_w = min(W - 4, 100)
        y0 = (H - dialog_h) // 2
        x0 = (W - dialog_w) // 2

        win = curses.newwin(dialog_h, dialog_w, y0, x0)
        win.keypad(True)

        # Filter out separator fields for navigation
        nav_fields = [
            (i, field) for i, field in enumerate(self.fields) if field[2] != "separator"
        ]

        while self.is_active:
            win.clear()
            win.box()

            # Title
            title = " Advanced Search - ES Command Line Options "
            tx = max(1, (dialog_w - len(title)) // 2)
            safe_addstr(win, 0, tx, title, self.colors.HEADER)

            # Calculate visible area
            content_h = dialog_h - 4

            # Auto-scroll to keep current field visible
            current_nav_idx = next(
                (
                    i
                    for i, (orig_idx, _) in enumerate(nav_fields)
                    if orig_idx >= self.current_field_idx
                ),
                0,
            )
            if current_nav_idx < self.scroll_offset:
                self.scroll_offset = current_nav_idx
            elif current_nav_idx >= self.scroll_offset + content_h:
                self.scroll_offset = current_nav_idx - content_h + 1

            self.scroll_offset = max(
                0, min(self.scroll_offset, len(nav_fields) - content_h)
            )

            # Draw fields
            y = 2
            for i in range(
                self.scroll_offset, min(len(nav_fields), self.scroll_offset + content_h)
            ):
                if y >= dialog_h - 2:
                    break

                field_idx, field_info = nav_fields[i]
                label, attr_name, field_type = field_info[:3]

                # Skip separators in display
                if field_type == "separator":
                    continue

                is_selected = field_idx == self.current_field_idx
                attr = self.colors.SELECTED if is_selected else self.colors.NORMAL

                # Draw label
                safe_addstr(win, y, 2, f"{label:<25}", attr)

                # Draw value based on field type
                if field_type == "bool":
                    value = getattr(self.options, attr_name)
                    display_val = "[X]" if value else "[ ]"
                elif field_type == "select":
                    value = getattr(self.options, attr_name)
                    options = field_info[3] if len(field_info) > 3 else []
                    display_val = f"<{value}>"
                else:  # text
                    value = getattr(self.options, attr_name)
                    display_val = str(value) if value else ""
                    if len(field_info) > 3:  # has hint
                        hint = field_info[3]
                        if not display_val and not is_selected:
                            display_val = f"({hint})"
                            attr = self.colors.INFO

                # Truncate if too long
                max_val_width = dialog_w - 30
                if len(display_val) > max_val_width:
                    display_val = display_val[: max_val_width - 3] + "..."

                safe_addstr(win, y, 27, display_val, attr)
                y += 1

            # Footer with instructions
            footer = "↑↓:Navigate Enter:Edit Tab:Next F5:Search Esc:Cancel"
            safe_addstr(win, dialog_h - 2, 2, footer[: dialog_w - 4], self.colors.INFO)

            win.refresh()
            key = win.getch()

            if key == 27:  # ESC
                self.is_active = False
                return None
            elif key == curses.KEY_F5:
                query = self.build_query()
                self.is_active = False
                return query
            elif key == curses.KEY_UP:
                # Find previous non-separator field
                for i in range(len(nav_fields) - 1, -1, -1):
                    field_idx, field_info = nav_fields[i]
                    if (
                        field_idx < self.current_field_idx
                        and field_info[2] != "separator"
                    ):
                        self.current_field_idx = field_idx
                        break
            elif key == curses.KEY_DOWN or key == ord("\t"):
                # Find next non-separator field
                for i in range(len(nav_fields)):
                    field_idx, field_info = nav_fields[i]
                    if (
                        field_idx > self.current_field_idx
                        and field_info[2] != "separator"
                    ):
                        self.current_field_idx = field_idx
                        break
            elif key in (curses.KEY_ENTER, 10, 13):
                self._edit_current_field(nav_fields)

        # Cleanup
        try:
            win.erase()
            win.refresh()
            self.stdscr.touchwin()
            self.stdscr.refresh()
        except Exception:
            pass
        return None

    def _edit_current_field(self, nav_fields):
        """Edit the currently selected field."""
        # Find current field info
        current_field = None
        for field_idx, field_info in nav_fields:
            if field_idx == self.current_field_idx:
                current_field = field_info
                break

        if not current_field:
            return

        label, attr_name, field_type = current_field[:3]

        if field_type == "bool":
            current_val = getattr(self.options, attr_name)
            setattr(self.options, attr_name, not current_val)
        elif field_type == "select":
            options = current_field[3]
            current_val = getattr(self.options, attr_name)
            try:
                current_idx = options.index(current_val)
                next_idx = (current_idx + 1) % len(options)
                setattr(self.options, attr_name, options[next_idx])
            except ValueError:
                setattr(self.options, attr_name, options[0])
        elif field_type == "text":
            current_val = getattr(self.options, attr_name)
            dialog = InputDialog(
                self.stdscr, f"Edit {label}", f"Enter {label.lower()}:", current_val
            )
            result = dialog.show()
            if result is not None:
                setattr(self.options, attr_name, result)


class ExportDialog:
    def __init__(self, stdscr, results: List[SearchResult]):
        self.stdscr = stdscr
        self.results = results
        self.colors = Colors()
        self.format = OutputFormat.CSV
        self.filename = ""

    def show(self) -> Optional[Tuple[OutputFormat, str]]:
        height, width = self.stdscr.getmaxyx()
        dialog_height = 10
        dialog_width = min(60, width - 4)
        start_y = (height - dialog_height) // 2
        start_x = (width - dialog_width) // 2

        dialog_win = curses.newwin(dialog_height, dialog_width, start_y, start_x)
        dialog_panel = panel.new_panel(dialog_win)

        formats = list(OutputFormat)
        current_format = 0

        while True:
            dialog_win.clear()
            dialog_win.box()

            # Title
            title = " Export Results "
            title_x = (dialog_width - len(title)) // 2
            dialog_win.addstr(0, title_x, title, self.colors.HEADER)

            # Format selection
            dialog_win.addstr(2, 2, "Format:")
            for i, fmt in enumerate(formats):
                y = 3 + i
                if i == current_format:
                    attr = self.colors.SELECTED
                else:
                    attr = self.colors.NORMAL
                dialog_win.addstr(y, 4, fmt.value.upper(), attr)

            # Instructions
            dialog_win.addstr(8, 2, "↑↓: Select format | Enter: Export | Esc: Cancel")

            panel.update_panels()
            curses.doupdate()

            key = dialog_win.getch()

            if key == 27:  # ESC
                result = None
                break
            elif key == curses.KEY_UP:
                current_format = max(0, current_format - 1)
            elif key == curses.KEY_DOWN:
                current_format = min(len(formats) - 1, current_format + 1)
            elif key in (curses.KEY_ENTER, 10, 13):  # Enter
                selected_format = formats[current_format]

                # Get filename
                default_name = f"search_results.{selected_format.value}"
                filename_dialog = InputDialog(
                    self.stdscr, "Export Filename", "Enter filename:", default_name
                )
                filename = filename_dialog.show()

                if filename:
                    result = (selected_format, filename)
                    break
                else:
                    result = None
                    break

        del dialog_panel
        del dialog_win
        self.stdscr.clear()
        self.stdscr.refresh()

        return result


class ESExecutor:
    def __init__(self, es_path: str = "es.exe"):
        self.es_path = es_path

    def build_command(self, options: SearchOptions) -> List[str]:
        cmd = [self.es_path]

        # Parse the query string to extract DOS-style switches and search terms
        query_parts, dos_switches = self._parse_query_string(options.query)

        logging.debug(f"Parsed query parts: {query_parts}")
        logging.debug(f"Parsed DOS switches: {dos_switches}")

        # Add search text (non-switch parts)
        if query_parts:
            cmd.extend(query_parts)

        # Add DOS-style switches from query
        cmd.extend(dos_switches)

        # Use DIR-style sorting for reliability (based on test results)
        has_sort_switch = any(
            sw.startswith("/o") or "-sort" in sw for sw in dos_switches
        )

        if not has_sort_switch:
            if options.sort_field == SortMode.NAME:
                sort_flag = "/on" if options.sort_ascending else "/o-n"
            elif options.sort_field == SortMode.SIZE:
                sort_flag = "/os" if options.sort_ascending else "/o-s"
            elif options.sort_field == SortMode.DATE_MODIFIED:
                sort_flag = "/od" if options.sort_ascending else "/o-d"
            elif options.sort_field == SortMode.EXTENSION:
                sort_flag = "/oe" if options.sort_ascending else "/o-e"
            elif options.sort_field == SortMode.PATH:
                # Path doesn't have a DIR-style equivalent, use -sort syntax
                cmd.extend(["-sort", "path"])
                if not options.sort_ascending:
                    cmd.extend(["-sort-descending"])
                sort_flag = None
            elif options.sort_field == SortMode.ATTRIBUTES:
                cmd.extend(["-sort", "attributes"])
                if not options.sort_ascending:
                    cmd.extend(["-sort-descending"])
                sort_flag = None
            else:
                # Default to name
                sort_flag = "/on" if options.sort_ascending else "/o-n"

            if sort_flag:
                cmd.append(sort_flag)
                logging.debug(f"Using DIR-style sort: {sort_flag}")

        # Modes (but don't override if already specified in query)
        if not any(sw in dos_switches for sw in ["-regex", "-r"]):
            if options.mode == SearchMode.REGEX:
                cmd.extend(["-regex"])

        if not any(sw in dos_switches for sw in ["-case", "-i"]):
            if options.mode == SearchMode.CASE_SENSITIVE:
                cmd.extend(["-case"])

        if not any(sw in dos_switches for sw in ["-whole-word", "-w", "-ww"]):
            if options.mode == SearchMode.WHOLE_WORD:
                cmd.extend(["-whole-word"])

        if not any(sw in dos_switches for sw in ["-match-path", "-p"]):
            if options.mode == SearchMode.MATCH_PATH:
                cmd.extend(["-match-path"])

        if (
            options.match_diacritics
            and "-diacritics" not in dos_switches
            and "-a" not in dos_switches
        ):
            cmd.extend(["-diacritics"])

        # Limits / offset
        max_results_specified = any(
            "-max-results" in str(sw) or "-n" in str(sw) for sw in dos_switches
        )
        if options.max_results > 0 and not max_results_specified:
            cmd.extend(["-max-results", str(options.max_results)])

        offset_specified = any(
            "-offset" in str(sw) or "-o" in str(sw) for sw in dos_switches
        )
        if options.offset > 0 and not offset_specified:
            cmd.extend(["-offset", str(options.offset)])

        # Columns - always specify these for consistent output
        columns = ["-name"]
        if options.show_size:
            columns.append("-size")
        if options.show_date_modified:
            columns.append("-date-modified")
        if options.show_date_created:
            columns.append("-date-created")
        if options.show_date_accessed:
            columns.append("-date-accessed")
        if options.show_attributes:
            columns.append("-attributes")
        if options.show_extension:
            columns.append("-extension")
        columns.append("-path-column")  # directory only; we'll join with name
        cmd.extend(columns)

        # Stable machine-readable output
        cmd.extend(["-csv", "-no-header"])

        # Filters (but don't duplicate file/folder filters from query)
        has_file_folder_filter = any(
            sw in dos_switches for sw in ["/ad", "/a-d"]
        ) or any(
            "files_only" in str(sw) or "folders_only" in str(sw) for sw in dos_switches
        )

        if not has_file_folder_filter:
            if options.files_only:
                cmd.extend(["/a-d"])
            elif options.folders_only:
                cmd.extend(["/ad"])

        if options.path_filter:
            cmd.extend(["-path", options.path_filter])
        if options.parent_path_filter:
            cmd.extend(["-parent-path", options.parent_path_filter])
        if options.instance_name:
            cmd.extend(["-instance", options.instance_name])

        # Formats
        if options.size_format != 1:
            cmd.extend(["-size-format", str(options.size_format)])
        if options.date_format != 0:
            cmd.extend(["-date-format", str(options.date_format)])

        # Highlight (only for console output, not CSV)
        # if options.highlight:
        #     cmd.extend(["-highlight"])

        if options.timeout > 0:
            cmd.extend(["-timeout", str(options.timeout)])

        logging.debug(f"Final ES command: {' '.join(cmd)}")
        return cmd

    def _parse_query_string(self, query: str) -> Tuple[List[str], List[str]]:
        """Parse query string to separate search terms from DOS-style switches.

        Returns:
            Tuple of (search_terms, switches)
        """
        if not query:
            return [], []

        import shlex

        try:
            # Split respecting quotes
            tokens = shlex.split(query)
        except ValueError:
            # Fall back to simple split if shlex fails
            tokens = query.split()

        search_terms = []
        switches = []

        i = 0
        while i < len(tokens):
            token = tokens[i]

            # DOS-style switches
            if token.startswith("/"):
                switches.append(token)
            # Unix-style switches
            elif token.startswith("-"):
                switches.append(token)
                # Check if this switch takes an argument
                if token in [
                    "-sort",
                    "-max-results",
                    "-n",
                    "-offset",
                    "-o",
                    "-path",
                    "-parent-path",
                    "-instance",
                    "-size-format",
                    "-date-format",
                    "-timeout",
                ] and i + 1 < len(tokens):
                    i += 1
                    switches.append(tokens[i])
            else:
                # Regular search term
                search_terms.append(token)
            i += 1

        return search_terms, switches

    def execute_search(self, options: SearchOptions) -> Tuple[List[SearchResult], str]:
        # First try ES sorting
        cmd = self.build_command(options)

        logging.debug(f"Executing ES command: {' '.join(cmd)}")
        logging.debug(f"Query string: '{options.query}'")

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            logging.debug(f"ES process completed with return code: {result.returncode}")

            if result.returncode != 0:
                error_msg = f"ES returned error code {result.returncode}"
                if result.stderr:
                    error_msg += f": {result.stderr.strip()}"
                logging.error(f"ES execution failed: {error_msg}")
                return [], error_msg

            results = self._parse_output(result.stdout, options)

            # Verify ES sorting worked, fall back to Python if needed
            if results:
                sorted_results = self._verify_and_fix_sorting(results, options)
                logging.debug(
                    f"Final results: {len(sorted_results)} (ES + Python verification)"
                )
                return sorted_results, ""
            else:
                return [], ""

        except subprocess.TimeoutExpired:
            logging.error("ES search timed out after 30 seconds")
            return [], "Search timed out"
        except FileNotFoundError:
            logging.error(f"ES executable not found at path: {self.es_path}")
            return [], f"ES executable not found: {self.es_path}"
        except Exception as e:
            logging.error(f"Unexpected error executing ES: {e}", exc_info=True)
            return [], f"Error executing search: {str(e)}"

    def _verify_and_fix_sorting(
        self, results: List[SearchResult], options: SearchOptions
    ) -> List[SearchResult]:
        """Verify ES sorting worked, apply Python sorting if needed."""
        if len(results) < 2:
            return results

        # Check if ES sorting actually worked
        es_sorted_correctly = self._check_es_sorting(results, options)

        if es_sorted_correctly:
            logging.debug(f"ES sorting verified correct for {options.sort_field.value}")
            return results
        else:
            logging.debug(
                f"ES sorting failed verification, applying Python sort for {options.sort_field.value}"
            )
            return self._python_sort_results(results, options)

    def _check_es_sorting(
        self, results: List[SearchResult], options: SearchOptions
    ) -> bool:
        """Check if results are actually sorted as requested."""
        if len(results) < 2:
            return True

        # Sample first few results to check sorting
        sample_size = min(5, len(results))

        for i in range(sample_size - 1):
            current = results[i]
            next_item = results[i + 1]

            # Get comparison values
            if options.sort_field == SortMode.NAME:
                curr_val = current.filename.lower()
                next_val = next_item.filename.lower()
            elif options.sort_field == SortMode.SIZE:
                curr_val = current.size
                next_val = next_item.size
            elif options.sort_field == SortMode.DATE_MODIFIED:
                curr_val = self._parse_date(current.date_modified)
                next_val = self._parse_date(next_item.date_modified)
            elif options.sort_field == SortMode.PATH:
                curr_val = os.path.dirname(current.full_path).lower()
                next_val = os.path.dirname(next_item.full_path).lower()
            elif options.sort_field == SortMode.EXTENSION:
                curr_val = os.path.splitext(current.filename)[1].lower()
                next_val = os.path.splitext(next_item.filename)[1].lower()
            else:
                continue

            # Check sort order
            if options.sort_ascending:
                if curr_val > next_val:
                    logging.debug(
                        f"Sort verification failed: {curr_val} > {next_val} (should be ascending)"
                    )
                    return False
            else:
                if curr_val < next_val:
                    logging.debug(
                        f"Sort verification failed: {curr_val} < {next_val} (should be descending)"
                    )
                    return False

        return True

    def _python_sort_results(
        self, results: List[SearchResult], options: SearchOptions
    ) -> List[SearchResult]:
        """Sort results using Python as fallback."""
        try:

            def get_sort_key(result: SearchResult):
                if options.sort_field == SortMode.NAME:
                    return result.filename.lower()
                elif options.sort_field == SortMode.SIZE:
                    return result.size
                elif options.sort_field == SortMode.DATE_MODIFIED:
                    return self._parse_date(result.date_modified)
                elif options.sort_field == SortMode.PATH:
                    return os.path.dirname(result.full_path).lower()
                elif options.sort_field == SortMode.EXTENSION:
                    return os.path.splitext(result.filename)[1].lower()
                else:
                    return result.filename.lower()

            sorted_results = sorted(
                results, key=get_sort_key, reverse=not options.sort_ascending
            )
            logging.debug(
                f"Python sorting applied: {options.sort_field.value} {'ascending' if options.sort_ascending else 'descending'}"
            )
            return sorted_results

        except Exception as e:
            logging.error(f"Python sorting failed: {e}", exc_info=True)
            return results

    def _parse_date(self, date_str: str) -> datetime:
        """Parse date string to datetime for proper sorting."""
        if not date_str:
            return datetime.min

        try:
            # Handle es.exe format: "28/08/2025 13:05"
            return datetime.strptime(date_str, "%d/%m/%Y %H:%M")
        except ValueError:
            try:
                # Fallback format
                return datetime.strptime(date_str, "%d/%m/%Y")
            except ValueError:
                logging.debug(f"Could not parse date: {date_str}")
                return datetime.min

    def _parse_output(self, output: str, options: SearchOptions) -> List[SearchResult]:
        import csv, io, os

        results: List[SearchResult] = []
        reader = csv.reader(io.StringIO(output))

        # Expected column order we emit in build_command():
        # name, [size], [date-modified], [extension], path-column
        # (the bracketed ones appear only if the option is enabled)
        for row in reader:
            if not row:
                continue

            i = 0

            # 1) name
            name = row[i].strip() if i < len(row) else ""
            i += 1

            # 2) size (optional)
            size = 0
            if options.show_size and i < len(row):
                try:
                    size = int(row[i].strip())
                except Exception:
                    size = 0
                i += 1

            # 3) date modified (optional)
            date_modified = ""
            if options.show_date_modified and i < len(row):
                date_modified = row[i].strip()
                i += 1

            # 4) extension (optional)
            # Everything returns extension with a leading dot (e.g. ".pdf")
            extension = ""
            if getattr(options, "show_extension", True) and i < len(row):
                # Only consume if we *actually* asked for it in the command
                # (Your build_command appends -extension when show_extension is True)
                extension = row[i].strip().lower()
                i += 1

            # 5) path column (directory)
            path_dir = row[i].strip() if i < len(row) else ""
            full_path = os.path.join(path_dir, name) if path_dir else name

            # If extension wasn't requested, derive it from the filename
            if not extension:
                extension = os.path.splitext(name)[1].lower()

            # Best-effort folder flag (Everything output can be stale; guard for speed)
            is_folder = os.path.isdir(full_path) if os.path.exists(full_path) else False

            results.append(
                SearchResult(
                    filename=name,
                    full_path=full_path,
                    size=size,
                    date_modified=date_modified,
                    extension=extension,
                    is_folder=is_folder,
                )
            )

        # (Nice-to-have) small diagnostic like before
        if results:
            sizes = [r.size for r in results[:5]]
            dates = [r.date_modified for r in results[:5]]
            exts = [r.extension for r in results[:5]]
            logging.debug(f"First 5 result sizes: {sizes}")
            logging.debug(f"First 5 result dates: {dates}")
            logging.debug(f"First 5 result extensions: {exts}")

        return results

    def export_results(
        self,
        results: List[SearchResult],
        format_type: OutputFormat,
        filename: str,
        options: SearchOptions,
    ) -> bool:
        try:
            # Build export command
            cmd = self.build_command(options)

            # Add export format
            format_map = {
                OutputFormat.CSV: "-export-csv",
                OutputFormat.EFU: "-export-efu",
                OutputFormat.TXT: "-export-txt",
                OutputFormat.M3U: "-export-m3u",
                OutputFormat.M3U8: "-export-m3u8",
            }

            export_flag = format_map.get(format_type, "-export-csv")
            cmd.extend([export_flag, filename])

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            return result.returncode == 0

        except Exception:
            return False


def copy_to_clipboard(text: str) -> bool:
    """Copy text to Windows clipboard using PowerShell."""
    try:
        import subprocess

        # Escape single quotes for PowerShell
        escaped_text = text.replace("'", "''")

        # Use PowerShell to set clipboard
        ps_command = f"Set-Clipboard -Value '{escaped_text}'"

        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_command],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode == 0:
            logging.debug(f"Clipboard copy successful: {text[:100]}...")
            return True
        else:
            logging.error(f"PowerShell clipboard failed: {result.stderr}")
            return False

    except Exception as e:
        logging.error(f"Clipboard copy exception: {e}")
        return False


class CopyDialog:
    def __init__(self, stdscr, result: SearchResult):
        self.stdscr = stdscr
        self.result = result
        self.colors = Colors()
        self.current_option = 0

        # Define copy options
        self.options = [
            ("Copy Full Path", lambda: self.result.full_path),
            ("Copy Directory", lambda: os.path.dirname(self.result.full_path)),
            ("Copy Filename", lambda: self.result.filename),
        ]

    def show(self) -> Optional[str]:
        """Show copy dialog and return selected text to copy."""
        try:
            H, W = self.stdscr.getmaxyx()
            dialog_h = len(self.options) + 6
            dialog_w = min(60, max(40, W - 4))
            y0 = (H - dialog_h) // 2
            x0 = (W - dialog_w) // 2

            win = curses.newwin(dialog_h, dialog_w, y0, x0)
            win.keypad(True)

            while True:
                win.clear()
                try:
                    win.box()
                except Exception:
                    pass

                # Title
                title = " Copy to Clipboard "
                tx = max(1, (dialog_w - len(title)) // 2)
                safe_addstr(win, 0, tx, title, self.colors.HEADER)

                # Show current file info
                filename = self.result.filename[: dialog_w - 6]
                safe_addstr(win, 2, 2, f"File: {filename}", self.colors.INFO)

                # Show options
                for i, (label, _) in enumerate(self.options):
                    y = 4 + i
                    attr = (
                        self.colors.SELECTED
                        if i == self.current_option
                        else self.colors.NORMAL
                    )
                    safe_addstr(win, y, 4, label, attr)

                # Footer
                footer = "↑↓: Select  Enter: Copy  Esc: Cancel"
                safe_addstr(win, dialog_h - 2, 2, footer, self.colors.INFO)

                win.refresh()
                key = win.getch()

                if key == 27:  # ESC
                    return None
                elif key == curses.KEY_UP:
                    self.current_option = max(0, self.current_option - 1)
                elif key == curses.KEY_DOWN:
                    self.current_option = min(
                        len(self.options) - 1, self.current_option + 1
                    )
                elif key in (curses.KEY_ENTER, 10, 13):
                    _, get_text = self.options[self.current_option]
                    return get_text()

        finally:
            try:
                win.erase()
                win.refresh()
                self.stdscr.touchwin()
                self.stdscr.refresh()
            except Exception:
                pass


class ESTUI:
    def __init__(
        self,
        stdscr,
        es_path: str = "es.exe",
        debug: bool = False,
        verbose: bool = False,
        exiftool_path: Optional[str] = None,
    ):
        self.stdscr = stdscr
        self.colors = Colors()
        self.executor = ESExecutor(es_path)
        self.options = SearchOptions()
        self.results: List[SearchResult] = []
        self.current_result = 0
        self.result_offset = 0
        self.status_message = "Ready"
        self.search_active = False
        self.current_focus = "search"  # "search", "headers", or "results"
        self.current_header_col = 0  # Which header column is selected
        self.debug_mode = debug  # The state variable to toggle
        self.verbose = verbose
        self.debug_log = []  # Store debug messages
        self.spinner_frames = ["|", "/", "-", "\\"]
        self.spinner_index = 0
        self._ui_dirty = False  # set True whenever background work finishes

        # ExifTool path for metadata extraction
        self.exiftool_path = exiftool_path
        self.exif_cache: Dict[str, Dict[str, Any]] = {}  # path -> metadata dict

        # Properties pane state
        self.props_visible = False
        self.props_cache: Dict[str, Dict[str, str]] = {}
        self.props_data: Optional[Dict[str, str]] = None

        # Setup curses
        curses.curs_set(1)
        self.stdscr.keypad(True)
        self.stdscr.timeout(100)

        # Set dimensions FIRST
        self.height, self.width = self.stdscr.getmaxyx()

        # Debug logging
        if self.debug_mode:
            logging.debug("TUI initialized")
            logging.debug(f"Terminal size: {self.height}x{self.width}")
            logging.debug(f"ES path: {es_path}")
            self.detect_terminal_capabilities()  # This method will now use self.debug_mode

        # Initialize UI components
        self.height, self.width = self.stdscr.getmaxyx()
        self.search_field = ""
        self.cursor_pos = 0

        # Create status bar
        self.status_bar = StatusBar(self.stdscr, self.height - 1)

        if self.debug_mode:
            self.log_debug(f"TUI initialized with debug mode enabled")
            self.log_debug(f"Terminal size: {self.width}x{self.height}")
            self.log_debug(f"ES path: {es_path}")

    def copy_selected(self):
        """Show copy dialog for selected result and copy to clipboard."""
        if not self.results or self.current_result >= len(self.results):
            self.status_message = "No selection to copy"
            self._ui_dirty = True
            return

        selected_result = self.results[self.current_result]
        dialog = CopyDialog(self.stdscr, selected_result)
        text_to_copy = dialog.show()

        if text_to_copy:
            success = copy_to_clipboard(text_to_copy)
            if success:
                self.status_message = f"Copied to clipboard: {os.path.basename(text_to_copy) if len(text_to_copy) > 50 else text_to_copy}"
            else:
                self.status_message = "Failed to copy to clipboard"
        else:
            self.status_message = "Copy cancelled"

        self._ui_dirty = True
        self.draw_interface()

    def show_advanced_search(self):
        """Show the advanced search dialog and apply the generated query."""
        logging.debug("F4 pressed - showing advanced search panel")
        self.current_focus = "search"
        self.draw_interface()
        dialog = AdvancedSearchDialog(self.stdscr)

        # Pre-populate with current search if any
        if self.search_field:
            dialog.options.search_text = self.search_field
            logging.debug(f"Pre-populated advanced search with: '{self.search_field}'")

        new_query = dialog.show()

        if new_query is not None:
            logging.debug(f"Advanced search generated query: '{new_query}'")
            self.search_field = new_query
            self.cursor_pos = len(new_query)

            # Also apply the command-line arguments to our search options
            cmd_args = dialog.build_command_args()
            logging.debug(f"Advanced search generated command args: {cmd_args}")

            self._apply_advanced_options(cmd_args, dialog.options)

            self.perform_search()
        else:
            logging.debug("Advanced search cancelled")

    def _apply_advanced_options(
        self, cmd_args: List[str], adv_options: AdvancedSearchOptions
    ):
        """Apply advanced search options to the main search options."""
        # Update search mode based on arguments
        if "-regex" in cmd_args:
            self.options.mode = SearchMode.REGEX
        elif "-case" in cmd_args:
            self.options.mode = SearchMode.CASE_SENSITIVE
        elif "-whole-word" in cmd_args:
            self.options.mode = SearchMode.WHOLE_WORD
        elif "-match-path" in cmd_args:
            self.options.mode = SearchMode.MATCH_PATH
        else:
            self.options.mode = SearchMode.NORMAL

        self.options.match_diacritics = "-diacritics" in cmd_args
        self.options.highlight = "-highlight" in cmd_args

        # Update sort options
        if "-sort" in cmd_args:
            sort_idx = cmd_args.index("-sort")
            if sort_idx + 1 < len(cmd_args):
                sort_field = cmd_args[sort_idx + 1]
                try:
                    self.options.sort_field = SortMode(sort_field)
                except ValueError:
                    pass

        self.options.sort_ascending = "-sort-descending" not in cmd_args

        # Update limits
        if "-max-results" in cmd_args:
            max_idx = cmd_args.index("-max-results")
            if max_idx + 1 < len(cmd_args):
                try:
                    self.options.max_results = int(cmd_args[max_idx + 1])
                except ValueError:
                    pass

        # Update filters
        if "-path" in cmd_args:
            path_idx = cmd_args.index("-path")
            if path_idx + 1 < len(cmd_args):
                self.options.path_filter = cmd_args[path_idx + 1]

        if "-instance" in cmd_args:
            inst_idx = cmd_args.index("-instance")
            if inst_idx + 1 < len(cmd_args):
                self.options.instance_name = cmd_args[inst_idx + 1]

    def detect_terminal_capabilities(self):
        """Detect and log terminal capabilities for Unicode support"""
        try:
            info = {
                "TERM": os.environ.get("TERM", "unknown"),
                "LANG": os.environ.get("LANG", "unknown"),
                "LC_ALL": os.environ.get("LC_ALL", "unknown"),
                "platform": sys.platform,
                "terminal_size": f"{self.height}x{self.width}",
            }
            try:
                test_emoji = "📄"
                (sys.stdout.encoding or "utf-8")  # just to read it
                test_emoji.encode(sys.stdout.encoding or "utf-8")
                info["unicode_encode"] = "OK"
            except Exception as e:
                info["unicode_encode"] = f"FAILED: {e}"

            try:
                info["colors"] = curses.can_change_color()
                info["color_pairs"] = getattr(curses, "COLOR_PAIRS", "unknown")
            except Exception:
                info["colors"] = "unknown"

            # use your existing debug logger
            if hasattr(self, "log_debug"):
                self.log_debug(f"Terminal capabilities: {info}")
            else:
                logging.debug(f"Terminal capabilities: {info}")

            return info
        except Exception as e:
            logging.debug(f"detect_terminal_capabilities failed: {e}")
            return {}

    def _draw_icon(self, y: int, x: int, result, attr) -> int:
        """Draws a file-type icon with comprehensive error handling and fallbacks."""
        if not getattr(self.options, "show_icons", True):
            return 0

        try:
            unicode_icon = FileTypeIcons.get_icon(result, use_unicode=True)
            ascii_icon = FileTypeIcons.get_icon(result, use_unicode=False)

            use_unicode = getattr(self.options, "use_unicode_icons", True)
            target_icon = unicode_icon if use_unicode else ascii_icon
            icon_col_w = 2 if use_unicode else 1  # reserve 2 cells for emoji

            try:
                safe_addstr(self.stdscr, y, x, target_icon, attr)
                return icon_col_w + 1  # +1 space padding
            except Exception:
                # Fallback to ASCII if unicode fails
                if use_unicode and unicode_icon != ascii_icon:
                    try:
                        safe_addstr(self.stdscr, y, x, ascii_icon, attr)
                        return 2  # keep alignment stable
                    except Exception:
                        pass

                # Final fallback: one-letter
                try:
                    fallback = "D" if getattr(result, "is_folder", False) else "F"
                    safe_addstr(self.stdscr, y, x, fallback, attr)
                    return 2
                except Exception:
                    return 2
        except Exception:
            return 2

    def _show_scroll_dialog(self, title: str, lines: List[str]):
        """Centered, scrollable text dialog. Up/Down/PgUp/PgDn/Home/End/ESC."""
        H, W = self.stdscr.getmaxyx()
        dlg_h = min(max(10, H - 6), H - 2)
        dlg_w = min(max(40, int(W * 0.8)), W - 2)
        y0 = (H - dlg_h) // 2
        x0 = (W - dlg_w) // 2

        win = curses.newwin(dlg_h, dlg_w, y0, x0)
        win.keypad(True)

        top = 0
        while True:
            win.clear()
            try:
                win.box()
            except Exception:
                pass

            # Title
            tx = max(1, (dlg_w - len(title) - 2) // 2)
            try:
                win.addstr(0, tx, f" {title} ", self.colors.HEADER)
            except Exception:
                pass

            # Draw a window of lines
            body_h = dlg_h - 4
            view = lines[top : top + body_h]
            for i, line in enumerate(view):
                # wrap long lines
                remaining = line
                col = 2
                row = 2 + i
                maxw = dlg_w - 4
                if len(remaining) > maxw:
                    remaining = remaining[:maxw]
                try:
                    win.addstr(row, col, remaining)
                except Exception:
                    pass

            # Footer
            footer = "↑↓ PgUp/PgDn Home/End  Esc:Close"
            try:
                win.addstr(dlg_h - 1, 2, footer[: dlg_w - 4], self.colors.INFO)
            except Exception:
                pass

            win.refresh()
            k = win.getch()
            if k in (27,):  # ESC
                break
            elif k == curses.KEY_UP:
                top = max(0, top - 1)
            elif k == curses.KEY_DOWN:
                top = min(max(0, len(lines) - body_h), top + 1)
            elif k == curses.KEY_PPAGE:
                top = max(0, top - body_h)
            elif k == curses.KEY_NPAGE:
                top = min(max(0, len(lines) - body_h), top + body_h)
            elif k == curses.KEY_HOME:
                top = 0
            elif k == curses.KEY_END:
                top = max(0, len(lines) - body_h)

        try:
            win.erase()
            win.refresh()
            self.stdscr.touchwin()
            self.stdscr.refresh()
        except Exception:
            pass

    def show_exif_metadata(self):
        """Use PyExifTool to read metadata for the selected file and show it."""
        if not self.results or self.current_result >= len(self.results):
            self.status_message = "No selection"
            self._ui_dirty = True
            return

        path = self.results[self.current_result].full_path

        # Cache to avoid re-spawning exiftool on the same file
        if path in self.exif_cache:
            data = self.exif_cache[path]
        else:
            if not HAVE_PYEXIFTOOL:
                self.status_message = (
                    "PyExifTool not installed (pip install pyexiftool)"
                )
                self._ui_dirty = True
                return
            try:
                # Configure PyExifTool for proper UTF-8 handling on Windows
                kw = {
                    "encoding": "utf-8",  # Force UTF-8 encoding
                    "common_args": [
                        "-charset",
                        "utf8",
                    ],  # Tell ExifTool to output UTF-8
                }

                if self.exiftool_path:
                    kw["executable"] = self.exiftool_path

                with exiftool.ExifToolHelper(**kw) as et:
                    out = et.get_metadata(path)
                data = out[0] if out else {"Error": "No metadata returned"}
                self.exif_cache[path] = data

            except UnicodeDecodeError as ue:
                logging.error(f"Unicode decode error for {path}: {ue}", exc_info=True)
                # Fallback: try with error handling
                try:
                    kw_fallback = {
                        "encoding": "utf-8",
                        "common_args": [
                            "-charset",
                            "utf8",
                            "-overwrite_original_in_place",
                        ],
                    }
                    if self.exiftool_path:
                        kw_fallback["executable"] = self.exiftool_path

                    with exiftool.ExifToolHelper(**kw_fallback) as et:
                        # Try with fewer parameters
                        out = et.get_metadata([path])
                    data = out[0] if out else {"Error": "Unicode decode failed"}
                    self.exif_cache[path] = data
                except Exception as e2:
                    logging.error(
                        f"Fallback ExifTool failed for {path}: {e2}", exc_info=True
                    )
                    data = {"Error": f"ExifTool encoding error: {str(ue)[:100]}..."}
                    self.exif_cache[path] = data

            except Exception as e:
                logging.error(f"ExifTool error: {e}", exc_info=True)
                self.status_message = "ExifTool failed (see log)"
                self._ui_dirty = True
                return

        # Build display lines from the dict. Keep SourceFile first, then sorted keys.
        lines: List[str] = []
        if "SourceFile" in data:
            lines.append(f"SourceFile = {data['SourceFile']}")
        for k in sorted(data.keys()):
            if k == "SourceFile":
                continue
            v = data[k]
            # normalize values with better Unicode handling
            try:
                if isinstance(v, (list, tuple)):
                    v = ", ".join(str(x) for x in v)
                elif isinstance(v, dict):
                    v = json.dumps(v, ensure_ascii=False)
                else:
                    v = str(v)
                lines.append(f"{k} = {v}")
            except UnicodeEncodeError:
                # Handle problematic Unicode characters
                v_safe = str(v).encode("ascii", "backslashreplace").decode("ascii")
                lines.append(f"{k} = {v_safe}")

        title = "ExifTool Metadata"
        self._show_scroll_dialog(title, lines)
        self._ui_dirty = True
        self.draw_interface()

    def toggle_properties(self):
        """Toggle the properties pane for the current selection."""
        if not self.results:
            self.status_message = "No selection"
            self._ui_dirty = True
            return

        self.props_visible = not getattr(self, "props_visible", False)
        if self.props_visible:
            sel = self.results[max(0, min(self.current_result, len(self.results) - 1))]
            path = getattr(sel, "full_path", sel.filename)
            # cache
            if path not in self.props_cache:
                try:
                    self.props_cache[path] = gather_file_properties(path)
                except Exception as e:
                    logging.error(f"gather_file_properties failed: {e}", exc_info=True)
                    self.props_cache[path] = {"Error": str(e)}
            self.props_data = self.props_cache[path]
        else:
            self.props_data = None
        self._ui_dirty = True
        self.draw_interface()

    def _draw_kv_lines(self, x, y, w, items):
        """Key: Value table writer using safe_addstr with wrapping."""
        line = y
        for k, v in items:
            key = f"{k}:"
            safe_addstr(self.stdscr, line, x, key, getattr(self.colors, "HIGHLIGHT", 0))
            # wrap value
            val = str(v or "")
            avail = max(1, w - len(key) - 1)
            start = 0
            first = True
            while start < len(val) or first:
                chunk = val[start : start + avail]
                safe_addstr(
                    self.stdscr,
                    line,
                    x + len(key) + 1,
                    chunk,
                    getattr(self.colors, "NORMAL", 0),
                )
                start += len(chunk)
                if start < len(val):
                    line += 1
                else:
                    break
                first = False
            line += 1
        return line

    def draw_properties_pane(self):
        """Draw a right-side properties pane if visible."""
        if not self.props_visible or not self.props_data:
            return
        H, W = self.height, self.width
        pane_w = min(56, max(30, W // 3))
        x0 = W - pane_w
        y0 = 1  # below the title bar
        h = H - 2

        # separator
        for r in range(y0, y0 + h):
            safe_addstr(self.stdscr, r, x0 - 1, "│", getattr(self.colors, "INFO", 0))

        # title
        title = " Properties "
        tx = x0 + max(1, (pane_w - len(title)) // 2)
        safe_addstr(self.stdscr, y0, tx, title, getattr(self.colors, "HEADER", 0))

        # body
        body_y = y0 + 2
        items = []
        # Choose an informative ordering
        keys = [
            "Name",
            "Type",
            "Opens with",
            "Location",
            "Size",
            "Size on disk",
            "Created",
            "Modified",
            "Accessed",
            "Owner",
            "Attributes",
            "Blocked",
        ]
        for k in keys:
            if k in self.props_data and self.props_data[k]:
                items.append((k, self.props_data[k]))
        self._draw_kv_lines(x0 + 1, body_y, pane_w - 2, items)

        # footer
        footer = "Space: Close  Enter: Open  Esc: Back"
        safe_addstr(
            self.stdscr,
            y0 + h - 1,
            x0 + 1,
            footer[: pane_w - 2],
            getattr(self.colors, "INFO", 0),
        )

    def log_debug(self, message: str):
        """Log debug message with timestamp"""
        if self.debug_mode:
            timestamp = time.strftime("%H:%M:%S")
            debug_msg = f"[{timestamp}] {message}"
            self.debug_log.append(debug_msg)

            # Keep only last 100 debug messages to prevent memory issues
            if len(self.debug_log) > 100:
                self.debug_log.pop(0)

    def run(self):
        """Main TUI loop with idle redraws for background work."""
        self.draw_interface()
        while True:
            self.handle_input()  # getch() returns every 100 ms (timeout set)
            if self.should_exit:
                break
            # While searching: animate & redraw on every idle tick.
            # When results land: redraw once (_ui_dirty is set by the worker).
            if self.search_active or getattr(self, "_ui_dirty", False):
                if self.search_active:
                    self.spinner_index = (self.spinner_index + 1) % len(
                        self.spinner_frames
                    )
                self.draw_interface()
                self._ui_dirty = False

    def draw_interface(self):
        """Draw the complete TUI interface"""
        self.stdscr.clear()

        # Draw title bar
        title = "ES TUI - Everything Search"
        self.stdscr.addstr(0, 0, " " * self.width, self.colors.HEADER)
        self.stdscr.addstr(0, 2, title, self.colors.HEADER)

        # Show current options in title bar
        options_text = (
            f"Mode: {self.options.mode.value} | Sort: {self.options.sort_field.value}"
        )
        if len(options_text) < self.width - len(title) - 10:
            self.stdscr.addstr(
                0, self.width - len(options_text) - 2, options_text, self.colors.HEADER
            )

        # Draw search field
        self.draw_search_field()

        # Draw results
        self.draw_results()

        # Draw context-sensitive help line
        if self.current_focus == "headers":
            help_text = "←→:Select Column Enter:Sort ↓:Results Tab:Search ESC:Search"
        elif self.current_focus == "results" and self.results:
            help_text = "c:Copy F1:Help F2:Options F3:Export F4:Advanced F5:Search F6:EXIF F7:Icons F10:Quit Tab:Switch ESC:Search"
        else:
            help_text = "F1:Help F2:Options F3:Export F4:Advanced F5:Search F6:EXIF F7:Icons F8:ASCII/Unicode F9:Debug F10:Quit Tab:Switch ESC:Search"

        self.stdscr.addstr(
            self.height - 2, 0, help_text[: self.width - 1], self.colors.INFO
        )

        # Update status bar
        result_count = len(self.results)
        if result_count > 0:
            status = f"Found {result_count} results | Selected: {self.current_result + 1}/{result_count}"
            if self.current_focus == "headers":
                # Show which column is selected
                header_names = []
                if getattr(self.options, "show_icons", True):
                    header_names.append("Icon")
                header_names.extend(["Name"])
                if getattr(self.options, "show_size", False):
                    header_names.append("Size")
                if getattr(self.options, "show_date_modified", False):
                    header_names.append("Modified")
                header_names.append("Path")

                if 0 <= self.current_header_col < len(header_names):
                    status += f" | Header: {header_names[self.current_header_col]}"
        else:
            status = self.status_message

        self.status_bar.update(status)

        self.draw_properties_pane()

        # Bottom-right progress bar while searching
        if self.search_active:
            bar_w = 12
            filled = self.spinner_index % (bar_w - 2)
            bar = "[" + ("=" * filled).ljust(bar_w - 2) + "]"
            y = self.height - 1
            x = max(0, self.width - len(bar) - 2)
            try:
                self.stdscr.addstr(y, x, bar, self.colors.INFO)
            except Exception:
                pass

        self.stdscr.refresh()

    def draw_search_field(self):
        """Draw the search input field"""
        y = 2
        label = "Search: "

        # Draw label
        self.stdscr.addstr(y, 2, label, self.colors.NORMAL)

        # Draw search field background
        field_start = 2 + len(label)
        field_width = self.width - field_start - 2

        if self.current_focus == "search":
            attr = curses.A_REVERSE
        else:
            attr = curses.A_UNDERLINE

        self.stdscr.addstr(y, field_start, " " * field_width, attr)

        # Draw search text
        display_text = self.search_field
        if len(display_text) > field_width:
            # Scroll text if too long
            start_pos = max(0, self.cursor_pos - field_width + 1)
            display_text = display_text[start_pos : start_pos + field_width]
            cursor_display_pos = self.cursor_pos - start_pos
        else:
            cursor_display_pos = self.cursor_pos

        self.stdscr.addstr(y, field_start, display_text, attr)

        # Position cursor if search field is active
        if self.current_focus == "search":
            curses.curs_set(1)
            self.stdscr.move(y, field_start + cursor_display_pos)
        else:
            curses.curs_set(0)

    def draw_results(self):
        """Draw the results list with an optional icon and extension column.
        Respects the right-side Properties pane if visible.
        """
        results_start_y = 4
        results_height = self.height - results_start_y - 3
        left_pad = 2

        # If a Properties pane is visible, reserve space on the right
        reserved_right = 0
        if getattr(self, "props_visible", False) and getattr(self, "props_data", None):
            # Keep in sync with draw_properties_pane()
            pane_w = min(56, max(30, self.width // 3))
            reserved_right = pane_w + 1  # +1 for the vertical separator

        effective_width = max(20, self.width - reserved_right)

        # No results: write a centered message (within effective area)
        if not self.results:
            if self.search_active:
                msg = "Searching..."
            elif self.search_field:
                msg = "No results found"
            else:
                msg = "Enter search term and press Enter"

            y = results_start_y + results_height // 2
            x = max(left_pad, (effective_width - len(msg)) // 2)
            safe_addstr(self.stdscr, y, x, msg, self.colors.INFO)
            return

        # Calculate visible range (scrolling)
        if self.current_result < self.result_offset:
            self.result_offset = self.current_result
        elif self.current_result >= self.result_offset + results_height:
            self.result_offset = self.current_result - results_height + 1

        # ----- Column widths -----
        # Icon column (optional)
        icon_w = 0
        if getattr(self.options, "show_icons", True):
            # reserve 2 cells for emoji (often double-width), plus 1 space padding
            icon_w = 3 if getattr(self.options, "use_unicode_icons", True) else 2

        # Name column
        name_w = min(40, effective_width // 3)
        # Remaining width (header area includes left padding)
        remaining = (
            effective_width - left_pad - icon_w - name_w - 1
        )  # -1 space after name
        headers, widths = [], []

        # Icon header is blank
        if icon_w:
            headers.append("")
            widths.append(icon_w)

        headers.append("Name")
        widths.append(name_w)

        # Fixed width for Size (right-aligned) if enabled
        size_w = 0
        if getattr(self.options, "show_size", False) and remaining > 11:
            size_w = 10
            headers.append("Size")
            widths.append(size_w)
            remaining -= size_w + 1  # +1 for spacing

        # Fixed width for Modified (left-aligned) if enabled
        date_w = 0
        if getattr(self.options, "show_date_modified", False) and remaining > 18:
            date_w = 19
            headers.append("Modified")
            widths.append(date_w)
            remaining -= date_w + 1

        # Dedicated extension column (optional)
        ext_w = 0
        if getattr(self.options, "show_extension", True) and remaining > 7:
            ext_w = 6
            headers.append("Ext")
            widths.append(ext_w)
            remaining -= ext_w + 1

        # Path column takes the rest
        path_w = max(10, remaining)
        headers.append("Path")
        widths.append(path_w)

        # ----- Draw headers -----
        header_y = results_start_y - 1
        x_pos = left_pad
        for i, (header, width) in enumerate(zip(headers, widths)):
            # Determine header attribute
            if self.current_focus == "headers" and i == self.current_header_col:
                attr = self.colors.SELECTED
            else:
                attr = self.colors.HEADER

            # Add sort indicator to current sort column
            display_header = header
            if header == "Name" and self.options.sort_field == SortMode.NAME:
                display_header += " ↑" if self.options.sort_ascending else " ↓"
            elif header == "Size" and self.options.sort_field == SortMode.SIZE:
                display_header += " ↑" if self.options.sort_ascending else " ↓"
            elif (
                header == "Modified"
                and self.options.sort_field == SortMode.DATE_MODIFIED
            ):
                display_header += " ↑" if self.options.sort_ascending else " ↓"
            elif header == "Ext" and self.options.sort_field == SortMode.EXTENSION:
                display_header += " ↑" if self.options.sort_ascending else " ↓"
            elif header == "Path" and self.options.sort_field == SortMode.PATH:
                display_header += " ↑" if self.options.sort_ascending else " ↓"

            safe_addstr(
                self.stdscr,
                header_y,
                x_pos,
                display_header.ljust(width)[:width],
                attr,
            )
            x_pos += width + 1

        # ----- Draw rows -----
        for i in range(results_height):
            idx = self.result_offset + i
            if idx >= len(self.results):
                break

            r = self.results[idx]
            y = results_start_y + i

            # Row attribute
            if idx == self.current_result:
                attr = (
                    self.colors.SELECTED
                    if self.current_focus == "results"
                    else self.colors.HIGHLIGHT
                )
            elif getattr(r, "is_folder", False):
                attr = self.colors.FOLDER
            else:
                attr = self.colors.NORMAL

            # Draw each column; do NOT clrtoeol to avoid erasing the properties pane
            x_pos = left_pad
            col_i = 0

            # Icon
            if icon_w:
                consumed = self._draw_icon(y, x_pos, r, attr)
                x_pos += consumed
                col_i += 1

            # Name
            name_text = getattr(r, "filename", "")
            safe_addstr(
                self.stdscr,
                y,
                x_pos,
                name_text[: widths[col_i]].ljust(widths[col_i]),
                attr,
            )
            x_pos += widths[col_i] + 1
            col_i += 1

            # Size
            if size_w and col_i < len(widths):
                size_text = ""
                try:
                    if isinstance(r.size, int) and r.size > 0:
                        size_text = self._format_size(r.size)
                    elif isinstance(r.size, str):
                        size_text = r.size
                except Exception:
                    size_text = ""
                safe_addstr(
                    self.stdscr,
                    y,
                    x_pos,
                    size_text.rjust(widths[col_i])[: widths[col_i]],
                    attr,
                )
                x_pos += widths[col_i] + 1
                col_i += 1

            # Modified
            if date_w and col_i < len(widths):
                dt = getattr(r, "date_modified", "") or ""
                safe_addstr(
                    self.stdscr,
                    y,
                    x_pos,
                    dt[: widths[col_i]].ljust(widths[col_i]),
                    attr,
                )
                x_pos += widths[col_i] + 1
                col_i += 1

            # Extension
            if ext_w and col_i < len(widths):
                ext_text = getattr(r, "extension", "") or ""
                safe_addstr(
                    self.stdscr,
                    y,
                    x_pos,
                    ext_text[: widths[col_i]].ljust(widths[col_i]),
                    attr,
                )
                x_pos += widths[col_i] + 1
                col_i += 1

            # Path (parent directory)
            if col_i < len(widths):
                full_path = getattr(r, "full_path", "") or ""
                parent = os.path.dirname(full_path) if full_path else ""
                safe_addstr(
                    self.stdscr,
                    y,
                    x_pos,
                    parent[: widths[col_i]].ljust(widths[col_i]),
                    attr,
                )

        # ----- Scrollbar (skip if a Properties pane is visible to avoid overlap) -----
        if len(self.results) > results_height and not getattr(
            self, "props_visible", False
        ):
            self._draw_scrollbar(results_start_y, results_height)

    def _draw_scrollbar(self, start_y: int, height: int):
        """Draw a scrollbar on the right side"""
        scrollbar_x = self.width - 1

        # Calculate scrollbar position
        total_results = len(self.results)
        thumb_size = max(1, height * height // total_results)
        thumb_pos = (
            self.result_offset * (height - thumb_size) // max(1, total_results - height)
        )

        # Draw scrollbar track
        for y in range(start_y, start_y + height):
            self.stdscr.addch(y, scrollbar_x, "│", self.colors.INFO)

        # Draw thumb
        for y in range(start_y + thumb_pos, start_y + thumb_pos + thumb_size):
            if y < start_y + height:
                self.stdscr.addch(y, scrollbar_x, "█", self.colors.HIGHLIGHT)

    def _format_size(self, size_bytes: int) -> str:
        """Format file size according to current settings"""
        if self.options.size_format == 0:  # Auto
            if size_bytes < 1024:
                return f"{size_bytes} B"
            elif size_bytes < 1024 * 1024:
                return f"{size_bytes / 1024:.1f} KB"
            elif size_bytes < 1024 * 1024 * 1024:
                return f"{size_bytes / (1024 * 1024):.1f} MB"
            else:
                return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
        elif self.options.size_format == 1:  # Bytes
            return f"{size_bytes:,}"
        elif self.options.size_format == 2:  # KB
            return f"{size_bytes / 1024:.1f}"
        elif self.options.size_format == 3:  # MB
            return f"{size_bytes / (1024 * 1024):.1f}"
        else:
            return str(size_bytes)

    def handle_input(self):
        """Handle keyboard input"""
        self.should_exit = False
        key = self.stdscr.getch()

        if key == -1:  # No input (timeout)
            return

        if self.debug_mode:
            logging.debug(
                f"Key pressed: {key} (0x{key:02x}) - '{chr(key) if 32 <= key <= 126 else '?'}'"
            )
            logging.debug(f"Current focus: {self.current_focus}")

        try:
            # Global shortcuts (work from any focus mode)
            if key == curses.KEY_F1 or key == ord("?"):
                self.show_help()
            elif key == curses.KEY_F2 or key == 15:  # F2 or Ctrl+O
                self.show_options()
            elif key == curses.KEY_F3 or key == 5:  # F3 or Ctrl+E
                self.export_results()
            elif key == curses.KEY_F4:
                self.show_advanced_search()
                return
            elif key == curses.KEY_F5 or key == 18:  # F5 or Ctrl+R
                self.perform_search()
            elif key == curses.KEY_F6 or key in (ord("x"), ord("X")):
                self.show_exif_metadata()
            elif key == curses.KEY_F7:
                self.options.show_icons = not self.options.show_icons
                self.draw_interface()
                return
            elif key == curses.KEY_F8:
                self.options.use_unicode_icons = not self.options.use_unicode_icons
                self.draw_interface()
                return
            elif key == curses.KEY_F9:
                self.debug_mode = not self.debug_mode
                if self.debug_mode:
                    logging.basicConfig(level=logging.DEBUG)
                    logging.debug("Debug mode activated by F9.")
                else:
                    logging.basicConfig(level=logging.INFO)
                    logging.info("Debug mode deactivated by F9.")
                self.draw_interface()
                return
            elif key == curses.KEY_F10 or key == 17:  # F10 or Ctrl+Q
                if self.debug_mode:
                    logging.debug("F10/Ctrl+Q pressed - exiting")
                self.should_exit = True
            elif key == ord("\t"):  # Tab
                if self.debug_mode:
                    logging.debug("Tab pressed - switching focus")
                self.switch_focus()
            elif key == 27:  # ESC
                if self.debug_mode:
                    logging.debug("ESC pressed - focus to search")
                self.current_focus = "search"
                self.draw_interface()
            elif key == 3:  # Ctrl+C
                if self.current_focus == "results" and self.results:
                    self.copy_selected()

            # Context-specific shortcuts
            elif self.current_focus == "search":
                self.handle_search_input(key)
            elif self.current_focus == "headers":
                self.handle_header_input(key)
            elif self.current_focus == "results":
                self.handle_results_input(key)

        except Exception as e:
            logging.error(f"Error handling key {key}: {str(e)}", exc_info=True)
            if self.debug_mode:
                self.status_message = f"Key handling error: {str(e)}"
                self.draw_interface()

    def show_help(self):
        """Show help dialog"""
        try:
            if self.debug_mode:
                logging.debug("Creating help dialog")

            help_dialog = HelpDialog(self.stdscr)

            if self.debug_mode:
                logging.debug("Showing help dialog")

            help_dialog.show()

            if self.debug_mode:
                logging.debug("Help dialog closed, redrawing interface")

            self.draw_interface()

        except Exception as e:
            logging.error(f"Error in show_help: {str(e)}", exc_info=True)
            self.status_message = f"Help error: {str(e)}"
            self.draw_interface()

    def _get_key_name(self, key: int) -> str:
        """Get human-readable key name for debugging"""
        key_names = {
            curses.KEY_F1: "F1",
            curses.KEY_F2: "F2",
            curses.KEY_F3: "F3",
            curses.KEY_F4: "F4",
            curses.KEY_F5: "F5",
            curses.KEY_F10: "F10",
            curses.KEY_UP: "UP",
            curses.KEY_DOWN: "DOWN",
            curses.KEY_LEFT: "LEFT",
            curses.KEY_RIGHT: "RIGHT",
            curses.KEY_ENTER: "ENTER",
            curses.KEY_BACKSPACE: "BACKSPACE",
            curses.KEY_DC: "DELETE",
            curses.KEY_HOME: "HOME",
            curses.KEY_END: "END",
            curses.KEY_PPAGE: "PAGE_UP",
            curses.KEY_NPAGE: "PAGE_DOWN",
            27: "ESC",
            9: "TAB",
            10: "ENTER",
            13: "ENTER",
            127: "BACKSPACE",
            15: "Ctrl+O",
            5: "Ctrl+E",
            18: "Ctrl+R",
            17: "Ctrl+Q",
            8: "BACKSPACE",
            330: "DELETE",
        }

        if key in key_names:
            return key_names[key]
        elif 32 <= key <= 126:
            return f"'{chr(key)}'"
        else:
            return f"UNKNOWN({key})"

    def handle_search_input(self, key):
        """Handle input when the search field is focused.

        Works across Windows terminals by accepting multiple keycodes for Backspace,
        Delete, and Enter. Keeps cursor within bounds and redraws after each edit.
        """
        # Normalize cursor in case the field length changed elsewhere
        if self.cursor_pos > len(self.search_field):
            self.cursor_pos = len(self.search_field)
        if self.cursor_pos < 0:
            self.cursor_pos = 0

        # ---- Key groups (don’t require global constants) ----
        BACKSPACE_KEYS = {curses.KEY_BACKSPACE, 8, 127}  # 8=Ctrl-H, 127=DEL
        ENTER_KEYS = {curses.KEY_ENTER, 10, 13}  # LF/CR
        DELETE_KEYS = {curses.KEY_DC, 330}  # many builds map KEY_DC to 330

        # ---- Actions ----
        if key in ENTER_KEYS:
            # Start a search immediately
            self.perform_search()
            return

        elif key in BACKSPACE_KEYS:
            if self.cursor_pos > 0:
                self.search_field = (
                    self.search_field[: self.cursor_pos - 1]
                    + self.search_field[self.cursor_pos :]
                )
                self.cursor_pos -= 1
                self.draw_interface()
            return

        elif key in DELETE_KEYS:
            if self.cursor_pos < len(self.search_field):
                self.search_field = (
                    self.search_field[: self.cursor_pos]
                    + self.search_field[self.cursor_pos + 1 :]
                )
                self.draw_interface()
            return

        elif key == curses.KEY_LEFT:
            self.cursor_pos = max(0, self.cursor_pos - 1)
            self.draw_interface()
            return

        elif key == curses.KEY_RIGHT:
            self.cursor_pos = min(len(self.search_field), self.cursor_pos + 1)
            self.draw_interface()
            return

        elif key == curses.KEY_HOME:
            self.cursor_pos = 0
            self.draw_interface()
            return

        elif key == curses.KEY_END:
            self.cursor_pos = len(self.search_field)
            self.draw_interface()
            return

        # --- Optional, familiar shortcuts ---
        elif key == 21:  # Ctrl+U  (kill to start)
            self.search_field = self.search_field[self.cursor_pos :]
            self.cursor_pos = 0
            self.draw_interface()
            return

        elif key == 11:  # Ctrl+K  (kill to end)
            self.search_field = self.search_field[: self.cursor_pos]
            self.draw_interface()
            return

        elif key == 23:  # Ctrl+W  (delete previous word)
            import re

            left = self.search_field[: self.cursor_pos]
            left2 = re.sub(r"\s*\w+\Z", "", left)
            # update after computing left2 to set correct cursor
            self.cursor_pos = len(left2)
            self.search_field = (
                left2 + self.search_field[self.cursor_pos + (len(left) - len(left2)) :]
            )
            # Simpler: just rebuild
            self.search_field = left2 + self.search_field[len(left) :]
            self.draw_interface()
            return

        # Printable characters (accept extended ASCII too)
        elif 32 <= key <= 255:
            self.search_field = (
                self.search_field[: self.cursor_pos]
                + chr(key)
                + self.search_field[self.cursor_pos :]
            )
            self.cursor_pos += 1
            self.draw_interface()
            return

        # Ignore everything else (function keys are handled in handle_input)
        return

    def handle_results_input(self, key):
        """Handle keys while the results table has focus.

        Enter: open selected
        Space: toggle Properties pane
        F6 / x / X: show ExifTool metadata (if integrated)
        Arrows / PgUp / PgDn / Home / End: navigate
        o / O: open selected
        """
        if not self.results:
            return

        ENTER_KEYS = {curses.KEY_ENTER, 10, 13}
        EXIF_KEYS = {curses.KEY_F6, ord("x"), ord("X")}

        def _refresh_props_if_open():
            # Rebuild the Properties pane for the new selection without changing visibility.
            if getattr(self, "props_visible", False):
                self.toggle_properties()
                self.toggle_properties()

        # Actions
        if key in ENTER_KEYS:
            self.open_selected()
            return

        elif key == ord(" "):  # Space toggles properties pane
            self.toggle_properties()
            return

        elif key in EXIF_KEYS:  # Show PyExifTool metadata dialog
            self.show_exif_metadata()
            return

        elif key in (ord("o"), ord("O")):  # 'o' also opens
            self.open_selected()
            return

        # Navigation
        elif key in (curses.KEY_UP, ord("k")):
            if self.current_result > 0:
                self.current_result -= 1
                if self.current_result < self.result_offset:
                    self.result_offset = self.current_result
                _refresh_props_if_open()
                self.draw_interface()
            return

        elif key in (curses.KEY_DOWN, ord("j")):
            if self.current_result < len(self.results) - 1:
                self.current_result += 1
                visible_rows = max(1, self.height - 6)
                if self.current_result >= self.result_offset + visible_rows:
                    self.result_offset = self.current_result - visible_rows + 1
                _refresh_props_if_open()
                self.draw_interface()
            return

        elif key in (ord("c"), ord("C")):  # 'c' or 'C' for copy
            self.copy_selected()
            return

        elif key == curses.KEY_PPAGE:
            visible_rows = max(1, self.height - 6)
            self.current_result = max(0, self.current_result - visible_rows)
            self.result_offset = max(0, self.result_offset - visible_rows)
            _refresh_props_if_open()
            self.draw_interface()
            return

        elif key == curses.KEY_NPAGE:
            visible_rows = max(1, self.height - 6)
            self.current_result = min(
                len(self.results) - 1, self.current_result + visible_rows
            )
            self.result_offset = min(
                max(0, len(self.results) - visible_rows),
                self.result_offset + visible_rows,
            )
            _refresh_props_if_open()
            self.draw_interface()
            return

        elif key == curses.KEY_HOME:
            self.current_result = 0
            self.result_offset = 0
            _refresh_props_if_open()
            self.draw_interface()
            return

        elif key == curses.KEY_END:
            self.current_result = max(0, len(self.results) - 1)
            visible_rows = max(1, self.height - 6)
            self.result_offset = max(0, len(self.results) - visible_rows)
            _refresh_props_if_open()
            self.draw_interface()
            return

        # Ignore everything else while in results mode
        return

    def switch_focus(self):
        """Switch focus between search field, headers, and results"""
        if self.current_focus == "search":
            if self.results:  # Only switch to headers if we have results
                self.current_focus = "headers"
                self.current_header_col = 0
            else:
                self.current_focus = "search"  # Stay in search if no results
        elif self.current_focus == "headers":
            self.current_focus = "results"
        else:  # results
            self.current_focus = "search"
        self.draw_interface()

    def handle_header_input(self, key):
        """Handle input when headers are focused"""
        if not self.results:
            self.switch_focus()  # Switch away if no results
            return

        # Build column list to match draw_results exactly
        columns = []

        # Icon column (if enabled)
        if getattr(self.options, "show_icons", True):
            columns.append(("", "icon"))

        # Name column
        columns.append(("Name", "name"))

        # Size column (if enabled)
        if getattr(self.options, "show_size", False):
            columns.append(("Size", "size"))

        # Date Modified column (if enabled)
        if getattr(self.options, "show_date_modified", False):
            columns.append(("Modified", "date_modified"))

        # Extension column (if enabled)
        if getattr(self.options, "show_extension", True):
            columns.append(("Ext", "extension"))

        # Path column
        columns.append(("Path", "path"))

        # Handle navigation
        if key == curses.KEY_LEFT:
            self.current_header_col = max(0, self.current_header_col - 1)
            self.draw_interface()
        elif key == curses.KEY_RIGHT:
            self.current_header_col = min(len(columns) - 1, self.current_header_col + 1)
            self.draw_interface()
        elif key in (curses.KEY_ENTER, 10, 13):
            self._sort_by_column(columns)
        elif key == curses.KEY_DOWN:
            # Switch to results mode and select first result
            self.current_focus = "results"
            self.current_result = 0
            self.draw_interface()

    def _sort_by_column(self, columns):
        """Sort results by the currently selected column"""
        if self.current_header_col >= len(columns):
            return

        _, col_type = columns[self.current_header_col]

        logging.debug(f"Sorting by column: {col_type}")

        # Determine new sort mode
        new_sort_mode = None
        if col_type == "icon":
            # Sort by extension since we can't sort by file type
            new_sort_mode = SortMode.EXTENSION
            logging.debug("Icon column - sorting by file extension instead")
        elif col_type == "name":
            new_sort_mode = SortMode.NAME
        elif col_type == "size":
            new_sort_mode = SortMode.SIZE
        elif col_type == "date_modified":
            new_sort_mode = SortMode.DATE_MODIFIED
        elif col_type == "extension":
            new_sort_mode = SortMode.EXTENSION
        elif col_type == "path":
            new_sort_mode = SortMode.PATH

        if new_sort_mode is None:
            logging.debug(f"Unknown column type for sorting: {col_type}")
            return

        logging.debug(
            f"Current sort field: {self.options.sort_field}, New sort mode: {new_sort_mode}"
        )

        # Toggle sort order if same column, otherwise default to ascending
        if self.options.sort_field == new_sort_mode:
            self.options.sort_ascending = not self.options.sort_ascending
            logging.debug(
                f"Toggling sort order to: {'ascending' if self.options.sort_ascending else 'descending'}"
            )
        else:
            self.options.sort_field = new_sort_mode
            self.options.sort_ascending = True
            logging.debug(f"Changing sort field to: {new_sort_mode.value} ascending")

        logging.debug(
            f"Final sort: {self.options.sort_field.value} {'ascending' if self.options.sort_ascending else 'descending'}"
        )

        # Re-run the search with new sort parameters
        self.perform_search()

    def perform_search(self):
        """Execute search in a separate thread"""
        if not self.search_field.strip():
            self.status_message = "Enter a search term"
            self.draw_interface()
            return

        self.options.query = self.search_field.strip()
        self.search_active = True
        self.status_message = "Searching..."

        logging.debug(f"Starting search with query: '{self.options.query}'")
        logging.debug(
            f"Search options: mode={self.options.mode}, files_only={self.options.files_only}, folders_only={self.options.folders_only}"
        )

        self.draw_interface()

        # Execute search in thread to avoid blocking UI
        def search_thread():
            try:
                logging.debug("Search thread started")
                start_time = time.time()

                results, error = self.executor.execute_search(self.options)

                elapsed_time = time.time() - start_time
                logging.debug(f"Search completed in {elapsed_time:.3f} seconds")

                self.results = results
                self.current_result = 0
                self.result_offset = 0
                self.search_active = False
                self._ui_dirty = True

                if error:
                    self.status_message = f"Error: {error}"
                    logging.error(f"Search error: {error}")
                else:
                    self.status_message = f"Found {len(results)} results"
                    logging.debug(f"Search successful: {len(results)} results")

            except Exception as e:
                self.search_active = False
                self._ui_dirty = True
                self.status_message = f"Search failed: {str(e)}"
                logging.error(f"Search thread exception: {e}", exc_info=True)

        threading.Thread(target=search_thread, daemon=True).start()

    def show_debug_log(self):
        """Show debug log dialog (debug mode only)"""
        if not self.debug_mode or not self.debug_log:
            return

        height, width = self.stdscr.getmaxyx()
        dialog_height = min(len(self.debug_log) + 6, height - 2)
        dialog_width = min(
            max(80, max(len(line) for line in self.debug_log[-20:]) + 4), width - 4
        )
        start_y = (height - dialog_height) // 2
        start_x = (width - dialog_width) // 2

        dialog_win = curses.newwin(dialog_height, dialog_width, start_y, start_x)
        dialog_panel = panel.new_panel(dialog_win)

        scroll_pos = max(0, len(self.debug_log) - (dialog_height - 4))

        while True:
            dialog_win.clear()
            dialog_win.box()

            # Title
            title = " Debug Log (F4 in debug mode) "
            title_x = (dialog_width - len(title)) // 2
            dialog_win.addstr(0, title_x, title, self.colors.HEADER)

            # Display debug messages
            visible_lines = dialog_height - 4
            for i, line in enumerate(
                self.debug_log[scroll_pos : scroll_pos + visible_lines]
            ):
                y = i + 2
                dialog_win.addstr(y, 2, line[: dialog_width - 4], self.colors.INFO)

            # Instructions
            instructions = "↑↓: Scroll | Esc: Close"
            dialog_win.addstr(dialog_height - 2, 2, instructions)

            panel.update_panels()
            curses.doupdate()

            key = dialog_win.getch()

            if key == 27:  # ESC
                break
            elif key == curses.KEY_UP:
                scroll_pos = max(0, scroll_pos - 1)
            elif key == curses.KEY_DOWN:
                scroll_pos = min(len(self.debug_log) - visible_lines, scroll_pos + 1)

        del dialog_panel
        del dialog_win
        self.stdscr.clear()
        self.draw_interface()

    def show_options(self):
        try:
            logging.debug("show_options(): creating dialog")
            dlg = OptionsDialog(self.stdscr, self.options)
            ok = dlg.show()
            logging.debug(f"show_options(): dialog returned {ok}")
        except Exception:
            logging.error("show_options(): fatal", exc_info=True)
            self.status_message = "Options error (see log)"
        finally:
            self.draw_interface()

    def export_results(self):
        """Show export dialog and export results"""
        if not self.results:
            self.status_message = "No results to export"
            self.draw_interface()
            return

        export_dialog = ExportDialog(self.stdscr, self.results)
        result = export_dialog.show()

        if result:
            format_type, filename = result
            success = self.executor.export_results(
                self.results, format_type, filename, self.options
            )

            if success:
                self.status_message = f"Results exported to {filename}"
            else:
                self.status_message = f"Export failed"

        self.draw_interface()

    def open_selected_result(self):
        """Open the currently selected result"""
        if not self.results or self.current_result >= len(self.results):
            return

        result = self.results[self.current_result]

        try:
            if os.name == "nt":  # Windows
                os.startfile(result.full_path)
            elif os.name == "posix":  # Unix/Linux/Mac
                subprocess.run(["xdg-open", result.full_path])

            self.status_message = f"Opened: {result.filename}"
        except Exception as e:
            self.status_message = f"Failed to open: {str(e)}"

        self.draw_interface()

    def preview_selected_result(self):
        """Show preview dialog for selected result"""
        if not self.results or self.current_result >= len(self.results):
            return

        result = self.results[self.current_result]

        # Create preview dialog
        preview_text = [
            f"Name: {result.filename}",
            f"Path: {result.full_path}",
            f"Type: {'Folder' if result.is_folder else 'File'}",
        ]

        if result.size > 0:
            preview_text.append(f"Size: {self._format_size(result.size)}")

        if result.date_modified:
            preview_text.append(f"Modified: {result.date_modified}")

        if result.date_created:
            preview_text.append(f"Created: {result.date_created}")

        if result.attributes:
            preview_text.append(f"Attributes: {result.attributes}")

        # Show simple preview dialog
        self._show_message_dialog("File Information", preview_text)
        self.draw_interface()

    def _show_message_dialog(self, title: str, lines: List[str]):
        """Show a simple message dialog"""
        height, width = self.stdscr.getmaxyx()
        dialog_height = min(len(lines) + 4, height - 4)
        dialog_width = min(max(len(line) for line in lines) + 4, width - 4)
        start_y = (height - dialog_height) // 2
        start_x = (width - dialog_width) // 2

        dialog_win = curses.newwin(dialog_height, dialog_width, start_y, start_x)
        dialog_panel = panel.new_panel(dialog_win)

        dialog_win.clear()
        dialog_win.box()

        # Title
        title_x = (dialog_width - len(title) - 2) // 2
        dialog_win.addstr(0, title_x, f" {title} ", self.colors.HEADER)

        # Content
        for i, line in enumerate(lines):
            if i < dialog_height - 4:
                dialog_win.addstr(i + 2, 2, line, self.colors.NORMAL)

        # Instructions
        dialog_win.addstr(dialog_height - 2, 2, "Press any key to close...")

        panel.update_panels()
        curses.doupdate()

        dialog_win.getch()  # Wait for key press

        del dialog_panel
        del dialog_win

    def open_selected(self):
        """Open the currently highlighted search result with the default app."""
        try:
            if not self.results:
                self.status_message = "No results to open"
                self._ui_dirty = True
                return

            idx = max(0, min(self.current_result, len(self.results) - 1))
            sel = self.results[idx]
            path = getattr(sel, "full_path", None) or getattr(sel, "path", None) or ""

            if not path:
                self.status_message = "Internal error: no path for selection"
                self._ui_dirty = True
                return

            ok = open_with_default_app(path)
            base = os.path.basename(path.rstrip("\\/"))
            self.status_message = f"Opened: {base}" if ok else f"Open failed: {base}"
        except Exception as e:
            logging.error(f"open_selected() failed: {e}", exc_info=True)
            self.status_message = "Open failed (see log)"
        finally:
            # Ensure UI refreshes even if no key was pressed after Enter
            self._ui_dirty = True
            self.draw_interface()


def main():
    # Force UTF-8 encoding for ExifTool on Windows
    if sys.platform.startswith("win"):
        os.environ.setdefault("PYTHONIOENCODING", "utf-8")
        # Ensure ExifTool uses UTF-8
        os.environ.setdefault("EXIFTOOL_ENCODING", "UTF-8")

    parser = argparse.ArgumentParser(
        description="ES TUI - Everything Search Text User Interface"
    )
    parser.add_argument(
        "--es-path",
        default="es.exe",
        help="Path to es.exe executable (default: es.exe)",
    )
    parser.add_argument("--query", help="Initial search query")
    parser.add_argument(
        "--debug", action="store_true", help="Enable debug mode with detailed logging"
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument(
        "--log-file",
        default="es_tui_debug.log",
        help="Debug log file path (default: es_tui_debug.log)",
    )

    parser.add_argument(
        "--exiftool-path",
        default=None,
        help="Path to exiftool executable (exiftool.exe). If omitted, it must be on PATH.",
    )

    args = parser.parse_args()

    # Setup logging – force reconfigure and write UTF-8 to file on Windows
    log_level = (
        logging.DEBUG
        if args.debug
        else (logging.INFO if args.verbose else logging.WARNING)
    )

    handlers = []

    if args.debug:
        # Ensure file handler uses UTF-8 to safely log emoji
        fh = logging.FileHandler(args.log_file, encoding="utf-8")
        handlers.append(fh)

    if args.verbose:
        # Console output may still be cp1252; avoid emitting emoji there
        sh = logging.StreamHandler()

        class _AsciiSafeFilter(logging.Filter):
            def filter(self, record: logging.LogRecord) -> bool:
                try:
                    (sys.stdout.encoding or "utf-8")
                    record.getMessage().encode(sys.stdout.encoding or "utf-8")
                    return True
                except Exception:
                    # Fallback: replace non-encodables so we never crash the console
                    record.msg = (
                        record.getMessage()
                        .encode("ascii", "backslashreplace")
                        .decode("ascii")
                    )
                    record.args = ()
                    return True

        sh.addFilter(_AsciiSafeFilter())
        handlers.append(sh)

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=handlers,
        force=True,  # IMPORTANT: drop any pre-existing handlers from libraries
    )

    if args.debug:
        print(f"Debug mode enabled. Logging to: {args.log_file}")

    def run_tui(stdscr):
        try:
            tui = ESTUI(
                stdscr,
                args.es_path,
                args.debug,
                args.verbose,
                exiftool_path=args.exiftool_path,
            )
            tui.log_debug("TUI initialized")

            # Set initial query if provided
            if args.query:
                tui.search_field = args.query
                tui.cursor_pos = len(args.query)
                tui.log_debug(f"Initial query set: {args.query}")

            tui.run()

        except KeyboardInterrupt:
            pass  # Clean exit on Ctrl+C
        except Exception as e:
            # Log the error first
            logging.error(f"Fatal TUI error: {e}", exc_info=True)

            # Show error and wait for keypress
            stdscr.clear()
            if args.debug or args.verbose:
                import traceback

                error_info = traceback.format_exc()
                lines = error_info.split("\n")
                for i, line in enumerate(lines[:20]):  # Show first 20 lines
                    stdscr.addstr(i, 0, line[: stdscr.getmaxyx()[1] - 1])
                stdscr.addstr(
                    min(21, stdscr.getmaxyx()[0] - 2), 0, "Press any key to exit..."
                )
            else:
                stdscr.addstr(0, 0, f"Error: {str(e)}")
                stdscr.addstr(
                    1, 0, "Press any key to exit... (use --debug for more info)"
                )
            stdscr.getch()

            # Re-raise the exception so it appears in the terminal after curses cleanup
            raise

    # Verify ES executable exists
    def find_executable(name):
        """Find executable in PATH"""
        import shutil

        return shutil.which(name) is not None

    if args.es_path == "es.exe":
        if not find_executable("es.exe") and not os.path.isfile("es.exe"):
            print(f"Warning: es.exe not found in PATH or current directory.")
            print(
                "Make sure es.exe is in your PATH or specify the correct path with --es-path"
            )
            print("Download from: https://www.voidtools.com/downloads/")
            print()

            response = input("Continue anyway? (y/N): ")
            if response.lower() != "y":
                sys.exit(1)
    elif not os.path.isfile(args.es_path):
        print(f"Error: Specified es.exe path not found: {args.es_path}")
        sys.exit(1)

    # Initialize curses and run TUI
    try:
        curses.wrapper(run_tui)
    except Exception as e:
        print(f"Failed to initialize TUI: {e}")
        sys.exit(1)


# ---------- safer screen write ----------
def safe_addstr(win, y, x, text, attr=0):
    """Write within bounds with detailed error logging."""
    try:
        height, width = win.getmaxyx()
        if y < 0 or y >= height or x < 0 or x >= width:
            logging.debug(
                f"safe_addstr: Position ({y},{x}) out of bounds {height}x{width}"
            )
            return

        # Leave last column alone (Windows quirk)
        maxlen = max(0, width - x - 1)
        if maxlen <= 0:
            logging.debug(f"safe_addstr: No space available at ({y},{x})")
            return

        display_text = str(text)[:maxlen]
        try:
            display_text.encode(sys.stdout.encoding or "utf-8", errors="replace")
        except Exception as enc_e:
            logging.debug(f"safe_addstr: Encoding failed for {repr(text)}: {enc_e}")
            display_text = (
                str(text)[:maxlen].encode("ascii", errors="replace").decode("ascii")
            )

        win.addstr(y, x, display_text, attr)

    except Exception as e:
        logging.debug(f"safe_addstr FAILED at ({y},{x}) with {repr(text)}: {e}")
        try:
            # last-ditch: strip zero-width/FEFF and write without attrs
            fallback = str(text)[:maxlen].replace("\u200b", "").replace("\ufeff", "")
            win.addstr(y, x, fallback)
        except Exception:
            pass


if __name__ == "__main__":
    main()
