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
    # Windows Search expects scope like: file:C:\Path\
    path = os.path.abspath(path)
    if not path.endswith("\\"):
        path += "\\"
    return f"file:{path}"


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
    raw_terms: List[str], whole_word: bool = False
) -> Optional[str]:
    if not raw_terms:
        return None
    # Join terms with AND similar to Everything multiple tokens behavior.
    # For phrases with spaces already quoted by the shell, they'll be a single token.
    parts = []
    for t in raw_terms:
        t = t.strip()
        if not t:
            continue
        # Whole word: attempt to enforce word boundary by quoting the term
        # (Windows Search treats quoted tokens as exact phrases; not a strict \b boundary,
        # but closer than bare token.)
        if whole_word:
            parts.append(f'"{t}"')
        else:
            parts.append(t)
    aqs = " AND ".join(parts)
    return aqs


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
        opts["columns"][:] if opts["columns"] else ["full"]
    )  # default: full path+name

    # Build SQL
    # Note: We fetch a superset of rows, apply offset in Python for compatibility.
    top_clause = ""
    top_n: Optional[int] = None
    if isinstance(opts.get("limit"), int) and opts["limit"] is not None:
        # Fetch a little extra for offset slicing
        top_n = max(opts["limit"] + int(opts.get("offset", 0)), 1)
        top_clause = f"TOP {top_n} "
    else:
        # Canonical safeguard: bound large resultsets to keep provider happy
        top_n = 1000
        top_clause = f"TOP {top_n} "

    select_list = ", ".join(f"{col}" for col in select_cols.keys())
    sql = f"SELECT {top_clause} {select_list} FROM SYSTEMINDEX"

    # Start with minimal WHERE clause
    where_parts = []

    # Scope filters
    for p in opts["paths"]:
        where_parts.append(f"SCOPE='{escape_contains(to_file_uri(p))}'")

    # Content searching
    contains_q = build_contains_query(search_terms, whole_word=opts["whole_word"])
    if contains_q:
        where_parts.append(f"CONTAINS('{escape_contains(contains_q)}')")

    # Only add WHERE clause if we have actual filters
    if where_parts:
        sql += " WHERE " + " AND ".join(where_parts)
    elif not search_terms and not opts["paths"]:
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
            # Defaults per es.exe: for size and dates, descending; others ascending
            if sort_key in ("size", "date-created", "date-modified", "date-accessed"):
                order = "DESC"
        sql += f" ORDER BY {SORT_MAP[sort_key]} {order}"  # Remove brackets
    elif sort_key is None:
        # No ORDER BY (explicitly disabled via -sort none)
        pass
    else:
        # Default: robust path ordering
        sql += " ORDER BY System.ItemPathDisplay ASC"  # Remove brackets

    if opts.get("debug_sql"):
        sys.stderr.write("\n[DEBUG SQL] " + sql + "\n\n")

    # Execute
    conn = connect_windows_search()
    rs = None
    try:
        rs = execute_windows_search(conn, sql)
        rows: List[Dict[str, Any]] = []
        # Iterate rows
        while not rs.EOF:
            row = {}
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

    # Build "full" column if requested
    for r in rows:
        path = r.get("path") or ""
        name = r.get("name") or ""
        if path and name and path.endswith("\\"):
            r["full"] = path + name
        elif path and name:
            r["full"] = os.path.join(path, name)
        else:
            r["full"] = name or path or ""

    # Post filters: -regex against name/path/full (NOT content; Windows Search did that part)
    if opts.get("regex"):
        flags = 0
        if not opts.get("case"):
            flags |= re.IGNORECASE
        pattern = re.compile(opts["regex"], flags)

        def keep(r):
            hay = r.get("full") if opts.get("match_path") else r.get("name", "") or ""
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
    w = csv.writer(fp)
    if not no_header:
        w.writerow(out_cols)
    for r in rows:
        rec = []
        for c in out_cols:
            if c == "size":
                rec.append(size_fmt(r.get("size"), size_format))
            else:
                v = r.get(c)
                if isinstance(v, datetime):
                    rec.append(v.isoformat(sep=" "))
                else:
                    rec.append("" if v is None else str(v))
        w.writerow(rec)


def write_txt(
    rows: List[Dict[str, Any]], out_cols: List[str], size_format: int, fp
) -> None:
    # Emulate es.exe: if only "full" column, just print the path; otherwise tab-separated columns.
    if out_cols == ["full"]:
        for r in rows:
            fp.write((r.get("full") or "") + "\n")
        return
    # Tab-separated
    fp.write("\t".join(out_cols) + "\n")
    for r in rows:
        parts = []
        for c in out_cols:
            if c == "size":
                parts.append(size_fmt(r.get("size"), size_format))
            else:
                v = r.get(c)
                if isinstance(v, datetime):
                    parts.append(v.isoformat(sep=" "))
                else:
                    parts.append("" if v is None else str(v))
        fp.write("\t".join(parts) + "\n")


def main(argv: List[str]) -> int:
    if len(argv) == 1 and argv[0] in ("-h", "--help", "/h", "/?"):
        help_text = __doc__ or "es_winsearch.py - Windows Search CLI (type -h for help)"
        sys.stdout.write(help_text + "\n")
        return 0

    opts, search_terms = parse_es_style_args(argv)
    try:
        rows, out_cols = gather_results(opts, search_terms)
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
        die("Error querying Windows Search: " + msg)

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
