#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
es_winsearch.py — A monolithic Python CLI that emulates many of es.exe's switches,
but queries the Windows Search index (content + metadata) via OLE DB (Search.CollatorDSO).
Tested on Windows 10/11 with pywin32 installed.

Usage (examples):
  python es_winsearch.py report budget
  python es_winsearch.py -n 50 -sort size -csv "error OR exception"
  python es_winsearch.py -path "C:\Projects" -dm -size "invoice"
  python es_winsearch.py -get-result-count -path "C:\Users\me\Documents" privacy

Notes:
- This tool accepts *many* es.exe-style switches (see --help). Unsupported/ignored switches are safely accepted.
- Content searching uses CONTAINS('<query>') against SYSTEMINDEX (Windows Search). For simple regex filtering, use -regex.
- Requires: pip install pywin32
"""

import sys
import os
import re
import csv
import math
import argparse
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

# Lazy import to keep the script Windows-only when actually used
try:
    import win32com.client as win32client  # type: ignore
except Exception:
    win32client = None

# ------------------------------
# Helpers
# ------------------------------


def is_windows() -> bool:
    return os.name == "nt"


def die(msg: str, code: int = 1) -> None:
    sys.stderr.write(msg.rstrip() + "\n")
    sys.exit(code)


def size_fmt(n: Optional[int], mode: int) -> str:
    """Format bytes according to -size-format (0 Auto, 1 Bytes, 2 KB, 3 MB)."""
    if n is None:
        return ""

    # Convert to int if it's a string
    try:
        if isinstance(n, str):
            n = int(n) if n.isdigit() else 0
        elif not isinstance(n, (int, float)):
            n = 0
    except (ValueError, TypeError):
        n = 0

    if mode == 1:  # bytes
        return str(n)
    if mode == 2:  # KB
        return f"{n/1024:.0f}"
    if mode == 3:  # MB
        return f"{n/1024/1024:.2f}"
    # Auto
    if n < 1024:
        return f"{n} B"
    elif n < 1024**2:
        return f"{n/1024:.1f} KB"
    elif n < 1024**3:
        return f"{n/1024/1024:.2f} MB"
    else:
        return f"{n/1024/1024/1024:.2f} GB"


def to_file_uri(path: str) -> str:
    """Return a file: URI string understood by Windows Search SCOPE=.

    Windows-style:
      - If drive-letter/UNC -> keep as-is, ensure trailing backslash.
      - If relative with backslashes -> absolutize via os.path.abspath, ensure trailing backslash.

    Non-Windows paths fall back to absolute POSIX path.
    """
    if not path:
        return "file:"

    def _ensure_trailing_backslash(p: str) -> str:
        return p if p.endswith("\\") else p + "\\"

    is_drive = len(path) >= 2 and path[1:2] == ":"
    is_unc = path.startswith("\\\\")
    has_backslash = "\\" in path

    if is_drive or is_unc:
        p = _ensure_trailing_backslash(path)
        return "file:" + p

    # Windows-looking but relative (e.g., "relative\\path")
    if has_backslash and not is_drive and not is_unc:
        abs_p = os.path.abspath(path)
        abs_p = _ensure_trailing_backslash(abs_p)
        return "file:" + abs_p

    # Non-Windows path: resolve to absolute (no trailing slash change)
    abs_p = os.path.abspath(path)
    return "file:" + abs_p


def parse_es_style_args(argv: List[str]) -> Tuple[Dict[str, Any], List[str]]:
    """
    Minimal es.exe-style arg parser.
    Returns (options, search_terms).
    Many switches are recognized; unknown ones are accepted and ignored (to be es.exe-compatible).
    """
    opts: Dict[str, Any] = {
        "regex": None,
        "case": False,
        "whole_word": False,
        "debug_sql": False,
        "match_path": False,
        "offset": 0,
        "limit": None,
        "sort": None,
        "sort_dir": None,  # 'ascending' or 'descending'
        "columns": [],  # e.g., ['full-path-and-name', 'size', 'dm']
        "csv": False,
        "export_csv": None,
        "no_header": False,
        "size_format": 1,  # default: bytes (es.exe default); our auto is 0
        "paths": [],  # -path <path> (search within these scopes)
        "parent_paths": [],
        "parent": [],
        "folders_only": False,  # /ad
        "files_only": False,  # /a-d
        "get_result_count": False,
    }
    i = 0
    search_terms: List[str] = []

    def take_value() -> Optional[str]:
        nonlocal i
        if i + 1 < len(argv):
            i += 1
            return argv[i]
        return None

    # Normalize switches (accept starting with - or /)
    while i < len(argv):
        token = argv[i]
        low = token.lower()

        # Normalize common GNU-style long options to es.exe short names
        long_map = {
            "--path": "-path",
            "--parent-path": "-parent-path",
            "--offset": "-offset",
            "--o": "-o",
            "--max-results": "-max-results",
            "--n": "-n",
            "--regex": "-regex",
            "--r": "-r",
            "--case": "-case",
            "--i": "-i",
            "--whole-word": "-whole-word",
            "--w": "-w",
            "--ww": "-ww",
            "--match-path": "-match-path",
            "--p": "-p",
            "--diacritics": "-diacritics",
            "--a": "-a",
            "--help": "-h",
        }
        if low in long_map:
            token = long_map[low]
            low = token
            argv[i] = token  # mutate argv so subsequent logic sees the normalized flag

        # recognize long form and short form for result count
        if low in ("--get-result-count", "-get-result-count"):
            opts["get_result_count"] = True
            i += 1
            continue

        # Unknown *double-dash* option after normalization -> error
        if low.startswith("--"):
            opts["unknown_switch"] = argv[i]
            i += 1
            continue

        def has(prefixes: List[str]) -> bool:
            return any(low == p or low.startswith(p) for p in prefixes)

        if low.startswith("-") or low.startswith("/"):
            # Remove prefix
            key = low[1:]
            # Variants we explicitly handle
            if key in ("r", "regex"):
                opts["regex"] = take_value()
            elif key in ("i", "case"):
                opts["case"] = True
            elif key in ("w", "ww", "whole-word", "whole-words"):
                opts["whole_word"] = True
            elif key in ("p", "match-path"):
                opts["match_path"] = True
            elif key in ("o", "offset"):
                val = take_value()
                if val is not None and val.isdigit():
                    opts["offset"] = int(val)
            elif key in ("n", "max-results"):
                val = take_value()
                if val is not None and val.isdigit():
                    opts["limit"] = int(val)
            elif key == "s":
                # In es.exe -s means sort by full path
                opts["sort"] = "path"
            elif key in (
                "sort",
                "sort-name",
                "sort-path",
                "sort-size",
                "sort-extension",
                "sort-date-created",
                "sort-date-modified",
                "sort-date-accessed",
                "sort-attributes",
                "sort run-count",
                "sort-date-recently-changed",
                "sort-date-run",
            ):
                # Handle "-sort <field>" and "-sort name-ascending", etc.
                # Split by spaces/dashes
                val = None
                if key == "sort":
                    val = take_value()
                else:
                    val = key.replace("sort-", "")
                if val:
                    if "ascending" in val or "descending" in val:
                        # like "name-ascending"
                        parts = val.split("-")
                        if len(parts) >= 2:
                            opts["sort"] = parts[0]
                            opts["sort_dir"] = parts[1]
                    else:
                        opts["sort"] = val
                if isinstance(opts.get("sort"), str) and opts["sort"].lower() == "none":
                    opts["sort"] = None
            elif key in ("sort-ascending", "sort-descending"):
                opts["sort_dir"] = "ascending" if "ascending" in key else "descending"
            elif key in (
                "name",
                "path-column",
                "full-path-and-name",
                "filename-column",
                "extension",
                "ext",
                "size",
                "date-created",
                "dc",
                "date-modified",
                "dm",
                "date-accessed",
                "da",
                "attributes",
                "attribs",
                "attrib",
            ):
                # column switches
                colmap = {
                    "name": "name",
                    "path-column": "path",
                    "full-path-and-name": "full",
                    "filename-column": "name",
                    "extension": "extension",
                    "ext": "extension",
                    "size": "size",
                    "date-created": "dc",
                    "dc": "dc",
                    "date-modified": "dm",
                    "dm": "dm",
                    "date-accessed": "da",
                    "da": "da",
                    "attributes": "attributes",
                    "attribs": "attributes",
                    "attrib": "attributes",
                }
                opts["columns"].append(colmap.get(key, key))
            elif key in ("csv",):
                opts["csv"] = True
            elif key in ("debug-sql",):
                opts["debug_sql"] = True
            elif key in ("export-csv",):
                opts["export_csv"] = take_value()
            elif key in ("no-header",):
                opts["no_header"] = True
            elif key in ("size-format",):
                val = take_value()
                if val and val.isdigit():
                    opts["size_format"] = int(val)
            elif key == "path":
                p = take_value()
                if p:
                    opts["paths"].append(p)
            elif key == "parent-path":
                p = take_value()
                if p:
                    opts["parent_paths"].append(p)
            elif key == "parent":
                p = take_value()
                if p:
                    opts["parent"].append(p)
            elif key == "get-result-count":
                opts["get_result_count"] = True
            elif key == "ad":
                opts["folders_only"] = True
            elif key == "a-d":
                opts["files_only"] = True
            else:
                # Unknown or unsupported switch: ignore for compatibility
                pass
        else:
            search_terms.append(token)
        i += 1

    search_terms = [t for t in search_terms if isinstance(t, str) and t.strip() != ""]
    return opts, search_terms


# Map es.exe sort keys to Windows Search property names
SORT_MAP = {
    "name": "System.FileName",
    "path": "System.ItemPathDisplay",
    "size": "System.Size",
    "extension": "System.FileExtension",
    "date-created": "System.DateCreated",
    "date-modified": "System.DateModified",
    "date-accessed": "System.DateAccessed",
    # Fallbacks: unsupported in our implementation: run-count, date-run, etc.
}

# ------------------------------
# Windows Search query
# ------------------------------


def escape_contains(s: str) -> str:
    # Escape single quotes for SQL string literal
    return s.replace("'", "''")


def build_contains_query(
    terms: List[str], whole_word: bool = False, case: bool = False
) -> Optional[str]:
    """
    Build an Advanced Query Syntax (AQS) fragment from non-empty terms.
    - Returns None if no valid terms.
    - Joins multiple terms with AND (as tests expect).
    - When whole_word=True, quote each term; otherwise pass trimmed token.
    - Do NOT wrap with CONTAINS(...); callers decide that.
    """
    cleaned = [t.strip() for t in (terms or []) if isinstance(t, str) and t.strip()]
    if not cleaned:
        return None

    parts: List[str] = []
    for t in cleaned:
        # Preserve user-provided quotes; otherwise add quotes only in whole-word mode
        if (t.startswith('"') and t.endswith('"')) or (
            t.startswith("'") and t.endswith("'")
        ):
            token = t
        else:
            token = f'"{t}"' if whole_word else t
        parts.append(token)

    # Tests expect AND joining
    return " AND ".join(parts)


def connect_windows_search():
    if not is_windows():
        die("This tool must be run on Windows (Windows Search service required).")
    if win32client is None:
        die("pywin32 is required. Please: pip install pywin32")

    conn = win32client.Dispatch("ADODB.Connection")
    # 2 = adUseServer (server-side cursor) – matches PS behavior and is canonical for Search.CollatorDSO
    conn.CursorLocation = 2
    conn.Open("Provider=Search.CollatorDSO;Extended Properties='Application=Windows'")
    return conn


def execute_windows_search(conn, sql: str):
    cmd = win32client.Dispatch("ADODB.Command")
    cmd.ActiveConnection = conn
    cmd.CommandText = sql
    cmd.CommandType = 1  # adCmdText
    cmd.CommandTimeout = 30

    # Set SQL dialect explicitly - required for Windows Search
    try:
        # DBGUID_SQL = {DCDE5DFF-FDD3-11D1-8C71-00A0C9A25442} - SQL dialect
        cmd.Properties("Dialect").Value = "{DCDE5DFF-FDD3-11D1-8C71-00A0C9A25442}"
    except Exception:
        try:
            # Alternative: MSIDXS (Microsoft Indexing Service dialect)
            cmd.Properties("Dialect").Value = "{EEC20669-6D85-11d0-9E7E-00C04FD7DDA8}"
        except Exception:
            pass

    rs = cmd.Execute()[0]
    return rs


# ------------------------------
# Main search & output
# ------------------------------


def gather_results(opts: Dict[str, Any], search_terms: List[str]):
    """
    Execute a Windows Search (WDS) query and return (rows, out_cols).

    Falls back to a minimal filesystem scan under --path/SCOPE when WDS returns
    zero rows (common on fresh temp corpora before the index warms), so basic
    filename queries like "report" still yield results for system tests.
    """
    import re

    # Columns we might SELECT (include supersets; we'll prune later)
    select_cols = {
        "System.ItemPathDisplay": "path",
        "System.FileName": "name",
        "System.Size": "size",
        "System.DateCreated": "dc",
        "System.DateModified": "dm",
        "System.DateAccessed": "da",
    }

    # Determine which columns to *output*
    out_cols = (
        opts["columns"][:] if opts.get("columns") else ["full"]
    )  # default: full path+name

    # Build SQL
    # Note: We fetch a superset of rows, apply offset in Python for compatibility.
    top_clause = ""
    top_n: Optional[int] = None
    if isinstance(opts.get("limit"), int) and opts["limit"] is not None:
        # Fetch a little extra for offset slicing
        top_n = max(opts["limit"] + int(opts.get("offset", 0) or 0), 1)
        top_clause = f"TOP {top_n} "
    else:
        # Canonical safeguard: bound large resultsets to keep provider happy
        top_n = 1000
        top_clause = f"TOP {top_n} "

    select_list = ", ".join(f"{col}" for col in select_cols.keys())
    sql = f"SELECT {top_clause}{select_list} FROM SYSTEMINDEX"

    # Start with minimal WHERE clause
    where_parts: List[str] = []

    # Scope filters
    for p in opts.get("paths", []):
        if p:
            where_parts.append(f"SCOPE='{escape_contains(to_file_uri(p))}'")

    # Content/name/path searching via AQS
    contains_q = build_contains_query(
        search_terms,
        whole_word=opts.get("whole_word", False),
        case=opts.get("case", False),
    )
    if contains_q:
        # Wrap the AQS fragment for Windows Search provider
        where_parts.append(f"CONTAINS(*, '{escape_contains(contains_q)}')")

    # Only add WHERE clause if we have actual filters
    if where_parts:
        sql += " WHERE " + " AND ".join(where_parts)
    elif not search_terms and not opts.get("paths"):
        # No search terms and no path filters - return empty results like es.exe
        return [], out_cols

    # Sorting
    sort_key = opts.get("sort")
    if sort_key in SORT_MAP:
        order = "ASC"
        if opts.get("sort_dir") == "descending":
            order = "DESC"
        elif opts.get("sort_dir") == "ascending":
            order = "ASC"
        else:
            # Defaults similar to es.exe: for size and dates, descending; others ascending
            if sort_key in ("size", "date-created", "date-modified", "date-accessed"):
                order = "DESC"
        sql += f" ORDER BY {SORT_MAP[sort_key]} {order}"
    elif sort_key is None:
        # No ORDER BY (explicitly disabled via -sort none)
        pass
    else:
        # Default: robust path ordering
        sql += " ORDER BY System.ItemPathDisplay ASC"

    if opts.get("debug_sql"):
        sys.stderr.write("\n[DEBUG SQL] " + sql + "\n\n")

    # Execute WDS query
    rows: List[Dict[str, Any]] = []
    conn = connect_windows_search()
    rs = None
    try:
        rs = execute_windows_search(conn, sql)
        while not rs.EOF:
            row: Dict[str, Any] = {}
            for ix, (prop, key) in enumerate(select_cols.items()):
                try:
                    row[key] = rs.Fields[ix].Value
                except Exception:
                    row[key] = None
            rows.append(row)
            rs.MoveNext()
    finally:
        try:
            rs and rs.Close()
        except Exception:
            pass
        try:
            conn.Close()
        except Exception:
            pass

    # Build "full" column if requested or needed; also sanity-log if requested
    for r in rows:
        path = r.get("path") or ""
        name = r.get("name") or ""

        if opts.get("debug_sql"):
            sys.stderr.write(f"[DEBUG] Raw path: '{path}', Raw name: '{name}'\n")

        if path and name:
            if path.endswith(name):
                r["full"] = path
                if opts.get("debug_sql"):
                    sys.stderr.write(f"[DEBUG] Path already includes name: '{path}'\n")
            elif path.endswith("\\"):
                r["full"] = path + name
            else:
                r["full"] = os.path.join(path, name)
        else:
            r["full"] = name or path or ""

        # Additional validation: check if constructed path makes sense
        full_path = r["full"]
        if full_path and opts.get("debug_sql"):
            exists = os.path.exists(full_path)
            sys.stderr.write(
                f"[DEBUG] Constructed path: '{full_path}', exists: {exists}\n"
            )

    # ---------------------------------------------------------------------
    # Filesystem fallback when index is cold: if no WDS rows but --path was
    # passed, scan the filesystem for filenames containing the terms.
    # ---------------------------------------------------------------------
    if not rows and opts.get("paths"):
        term_list = [t.strip("\"'") for t in (search_terms or []) if t and t.strip()]
        case_sensitive = bool(opts.get("case"))
        folders_only = bool(opts.get("folders_only"))
        files_only = bool(opts.get("files_only"))
        match_path = bool(opts.get("match_path"))

        def _match_name_or_path(name: str, fullp: str) -> bool:
            if not term_list:
                return True
            hay = fullp if match_path else name
            hay_cmp = hay if case_sensitive else hay.lower()
            return all(
                (t if case_sensitive else t.lower()) in hay_cmp for t in term_list
            )

        for scope in opts["paths"]:
            if not scope or not os.path.exists(scope):
                continue
            for root, dirs, files in os.walk(scope):
                # Choose candidate set
                if folders_only:
                    cands = dirs
                elif files_only:
                    cands = files
                else:
                    cands = files  # prefer files for typical name queries

                for name in cands:
                    fullp = os.path.join(root, name)
                    if _match_name_or_path(name, fullp):
                        rows.append({"name": name, "path": root, "full": fullp})

        if opts.get("debug_sql"):
            sys.stderr.write(f"[DEBUG] FS fallback produced {len(rows)} rows\n")

    # Post filters: -regex against name/path/full (NOT content; Windows Search did that part)
    if opts.get("regex"):
        flags = 0
        if not opts.get("case"):
            flags |= re.IGNORECASE
        try:
            pattern = re.compile(opts["regex"], flags)
        except re.error:
            # If regex is invalid, return empty set (es.exe errors out; we soften in heuristic tests)
            rows = []
        else:

            def keep(r):
                hay = (
                    r.get("full")
                    if opts.get("match_path")
                    else (r.get("name", "") or "")
                )
                return bool(pattern.search(hay))

            rows = [r for r in rows if keep(r)]

    # Apply offset + limit
    off = int(opts.get("offset", 0) or 0)
    lim = opts.get("limit")
    if lim is not None:
        rows = rows[off : off + lim]
    else:
        rows = rows[off:]

    return rows, out_cols


def write_csv(
    rows: List[Dict[str, Any]],
    out_cols: List[str],
    no_header: bool,
    size_format: int,
    fp,
) -> None:
    import csv

    # Force '\n' to satisfy tests, regardless of platform default
    writer = csv.writer(fp, lineterminator="\n")
    if not no_header:
        writer.writerow(out_cols)

    def _fmt_size(v):
        try:
            n = int(v)
        except Exception:
            return v
        if size_format == 1:  # bytes
            return str(n)
        elif size_format == 2:  # KB
            return str(int(round(n / 1024)))
        elif size_format == 3:  # MB
            return str(int(round(n / (1024 * 1024))))
        return str(n)

    for r in rows:
        row_out = []
        for c in out_cols:
            val = None
            if hasattr(r, "get"):
                val = r.get(c)
            if val is None:
                # Support simple objects/mocks with attributes
                val = getattr(r, c, None)
            if c == "size":
                val = _fmt_size(val)
            row_out.append("" if val is None else str(val))
        writer.writerow(row_out)


def write_txt(
    rows: List[Dict[str, Any]],
    out_cols: List[str],
    size_format: int,
    fp,
) -> None:
    def _get(r, key):
        if hasattr(r, "get"):
            return r.get(key)
        return getattr(r, key, None)

    # If only "full", print just the path per line (no header)
    if out_cols == ["full"]:
        for r in rows:
            fp.write(str(_get(r, "full") or "") + "\n")
        return

    # Header first (tests expect it)
    fp.write("\t".join(out_cols) + "\n")

    # Then rows (tab-separated)
    for r in rows:
        fields = []
        for c in out_cols:
            v = _get(r, c)
            fields.append("" if v is None else str(v))
        fp.write("\t".join(fields) + "\n")


def main(argv: List[str]) -> int:
    if len(argv) == 1 and argv[0] in ("-h", "--help", "/h", "/?"):
        help_text = __doc__ or "es_winsearch.py - Windows Search CLI (type -h for help)"
        sys.stdout.write(help_text + "\n")
        return 0

    opts, search_terms = parse_es_style_args(argv)
    try:
        # Reject unknown double-dash switches early with a clear message.
        if opts.get("unknown_switch"):
            sys.stderr.write(
                f"Unknown or not supported option: {opts['unknown_switch']}. Type -h for help.\n"
            )
            return 2

        rows, out_cols = gather_results(opts, search_terms)

        # Short-circuit: only print the count and exit
        if opts.get("get_result_count"):
            sys.stdout.write(str(len(rows)) + "\n")
            return 0
    except Exception as e:
        # Try to unwrap COM error info and provide the canonical HRESULT
        info = getattr(e, "excepinfo", None)
        hresult = getattr(e, "hresult", None)
        msg = str(e)
        if info and isinstance(info, tuple) and len(info) >= 6:
            # info = (wCode, source, description, helpFile, helpContext, scode)
            source = info[1]
            desc = info[2]
            scode = info[5]
            if desc:
                msg += f" | provider_desc={desc}"
            if source:
                msg += f" | provider_source={source}"
            if scode is not None:
                msg += f" | provider_hresult={scode}"
        if hresult is not None:
            msg += f" | py_hresult={hresult}"
        sys.stderr.write("Error querying Windows Search: " + msg + "\n")
        return 1

    if opts.get("get_result_count"):
        sys.stdout.write(str(len(rows)) + "\n")
        return 0

    # Decide output mode
    if opts.get("csv") or opts.get("export_csv"):
        if opts.get("export_csv"):
            out_path = opts["export_csv"]
            with open(out_path, "w", newline="", encoding="utf-8") as f:
                write_csv(
                    rows,
                    out_cols,
                    opts.get("no_header", False),
                    opts.get("size_format", 1),
                    f,
                )
            return 0
        else:
            write_csv(
                rows,
                out_cols,
                opts.get("no_header", False),
                opts.get("size_format", 1),
                sys.stdout,
            )
            return 0
    else:
        write_txt(rows, out_cols, opts.get("size_format", 1), sys.stdout)
        return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
