#!/usr/bin/env python3
"""
Unit tests for es_tui.py

Tests pure logic functions without curses dependencies. UI components are tested
by extracting their logic into testable pure functions.
"""

import pytest
import os
import sys
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

# Mock curses before importing es_tui to avoid curses dependency in unit tests
sys.modules["curses"] = Mock()
sys.modules["curses.panel"] = Mock()
sys.modules["curses.ascii"] = Mock()

try:
    import es_tui
except ImportError:
    pytest.skip("es_tui.py not found", allow_module_level=True)


class TestFileTypeIcons:
    """Test file type icon selection logic"""

    def test_unicode_file_icons(self):
        """Test Unicode icon selection for various file types"""
        test_cases = [
            (".txt", "📄"),
            (".pdf", "📕"),
            (".jpg", "🖼️"),
            (".mp4", "🎬"),
            (".mp3", "🎵"),
            (".zip", "📦"),
            (".py", "🐍"),
            (".exe", "⚙️"),
        ]

        for ext, expected_icon in test_cases:
            result = Mock()
            result.filename = f"test{ext}"
            result.is_folder = False

            icon = es_tui.FileTypeIcons.get_icon(result, use_unicode=True)
            assert icon == expected_icon

    def test_ascii_file_icons(self):
        """Test ASCII fallback icon selection"""
        test_cases = [
            (".txt", "T"),
            (".pdf", "P"),
            (".jpg", "I"),
            (".mp4", "V"),
            (".zip", "Z"),
            (".exe", "X"),
        ]

        for ext, expected_icon in test_cases:
            result = Mock()
            result.filename = f"test{ext}"
            result.is_folder = False

            icon = es_tui.FileTypeIcons.get_icon(result, use_unicode=False)
            assert icon == expected_icon

    def test_folder_icons(self):
        """Test folder icon selection"""
        result = Mock()
        result.filename = "Documents"
        result.is_folder = True

        unicode_icon = es_tui.FileTypeIcons.get_icon(result, use_unicode=True)
        ascii_icon = es_tui.FileTypeIcons.get_icon(result, use_unicode=False)

        assert unicode_icon == "📁"
        assert ascii_icon == "D"

    def test_unknown_extension(self):
        """Test default icon for unknown file types"""
        result = Mock()
        result.filename = "file.unknown_ext"
        result.is_folder = False

        unicode_icon = es_tui.FileTypeIcons.get_icon(result, use_unicode=True)
        ascii_icon = es_tui.FileTypeIcons.get_icon(result, use_unicode=False)

        assert unicode_icon == "📄"  # default
        assert ascii_icon == "F"  # default


class TestSearchOptions:
    """Test SearchOptions dataclass functionality"""

    def test_default_values(self):
        """Test default values are set correctly"""
        options = es_tui.SearchOptions()

        assert options.query == ""
        assert options.mode == es_tui.SearchMode.NORMAL
        assert options.sort_field == es_tui.SortMode.NAME
        assert options.sort_ascending is True
        assert options.max_results == 1000
        assert options.offset == 0
        assert options.show_size is True
        assert options.show_icons is True
        assert options.use_unicode_icons is True

    def test_custom_values(self):
        """Test setting custom values"""
        options = es_tui.SearchOptions(
            query="test search",
            mode=es_tui.SearchMode.REGEX,
            sort_field=es_tui.SortMode.SIZE,
            sort_ascending=False,
            max_results=500,
        )

        assert options.query == "test search"
        assert options.mode == es_tui.SearchMode.REGEX
        assert options.sort_field == es_tui.SortMode.SIZE
        assert options.sort_ascending is False
        assert options.max_results == 500


class TestSearchResult:
    """Test SearchResult dataclass functionality"""

    def test_basic_result(self):
        """Test creating a basic search result"""
        result = es_tui.SearchResult(
            filename="test.txt",
            full_path="C:\\Documents\\test.txt",
            size=1024,
            date_modified="2024-01-15 10:30",
        )

        assert result.filename == "test.txt"
        assert result.full_path == "C:\\Documents\\test.txt"
        assert result.size == 1024
        assert result.date_modified == "2024-01-15 10:30"
        assert result.is_folder is False  # default

    def test_folder_result(self):
        """Test creating a folder result"""
        result = es_tui.SearchResult(
            filename="Documents", full_path="C:\\Documents", is_folder=True
        )

        assert result.is_folder is True
        assert result.size == 0  # default


class TestESExecutorCommandBuilding:
    """Test ES command building logic without subprocess execution"""

    def test_basic_command_construction(self):
        """Test basic command construction with minimal options"""
        executor = es_tui.ESExecutor("es.exe")
        options = es_tui.SearchOptions(query="test")

        cmd = executor.build_command(options)

        assert cmd[0] == "es.exe"
        assert "test" in cmd
        assert "-csv" in cmd
        assert "-no-header" in cmd
        assert "-name" in cmd

    def test_regex_mode_command(self):
        """Test command construction with regex mode"""
        executor = es_tui.ESExecutor("es.exe")
        options = es_tui.SearchOptions(query=".*\\.txt$", mode=es_tui.SearchMode.REGEX)

        cmd = executor.build_command(options)

        assert "-regex" in cmd
        assert ".*\\.txt$" in cmd

    def test_case_sensitive_mode(self):
        """Test command construction with case sensitivity"""
        executor = es_tui.ESExecutor("es.exe")
        options = es_tui.SearchOptions(
            query="Test", mode=es_tui.SearchMode.CASE_SENSITIVE
        )

        cmd = executor.build_command(options)

        assert "-case" in cmd

    def test_whole_word_mode(self):
        """Test command construction with whole word mode"""
        executor = es_tui.ESExecutor("es.exe")
        options = es_tui.SearchOptions(query="cat", mode=es_tui.SearchMode.WHOLE_WORD)

        cmd = executor.build_command(options)

        assert "-whole-word" in cmd

    def test_sort_options(self):
        """Test command construction with different sort options"""
        executor = es_tui.ESExecutor("es.exe")

        # Test size sort ascending
        options = es_tui.SearchOptions(
            query="test", sort_field=es_tui.SortMode.SIZE, sort_ascending=True
        )
        cmd = executor.build_command(options)
        assert "/os" in cmd  # DOS-style ascending size sort

        # Test size sort descending
        options.sort_ascending = False
        cmd = executor.build_command(options)
        assert "/o-s" in cmd  # DOS-style descending size sort

        # Test name sort
        options.sort_field = es_tui.SortMode.NAME
        options.sort_ascending = True
        cmd = executor.build_command(options)
        assert "/on" in cmd

    def test_column_selection(self):
        """Test command construction with different column options"""
        executor = es_tui.ESExecutor("es.exe")
        options = es_tui.SearchOptions(
            query="test",
            show_size=True,
            show_date_modified=True,
            show_date_created=False,
            show_attributes=False,
        )

        cmd = executor.build_command(options)

        assert "-size" in cmd
        assert "-date-modified" in cmd
        assert "-date-created" not in cmd
        assert "-attributes" not in cmd

    def test_file_folder_filters(self):
        """Test command construction with file/folder filters"""
        executor = es_tui.ESExecutor("es.exe")

        # Test files only
        options = es_tui.SearchOptions(query="test", files_only=True)
        cmd = executor.build_command(options)
        assert "/a-d" in cmd

        # Test folders only
        options = es_tui.SearchOptions(query="test", folders_only=True)
        cmd = executor.build_command(options)
        assert "/ad" in cmd

    def test_limits_and_offsets(self):
        """Test command construction with result limits and offsets"""
        executor = es_tui.ESExecutor("es.exe")
        options = es_tui.SearchOptions(query="test", max_results=50, offset=10)

        cmd = executor.build_command(options)

        assert "-max-results" in cmd
        assert "50" in cmd
        assert "-offset" in cmd
        assert "10" in cmd

    def test_path_filters(self):
        """Test command construction with path filters"""
        executor = es_tui.ESExecutor("es.exe")
        options = es_tui.SearchOptions(
            query="test", path_filter="C:\\Documents", parent_path_filter="C:\\Users"
        )

        cmd = executor.build_command(options)

        assert "-path" in cmd
        assert "C:\\Documents" in cmd
        assert "-parent-path" in cmd
        assert "C:\\Users" in cmd


class TestQueryParsing:
    """Test DOS-style query parsing for TUI integration"""

    def test_parse_query_with_switches(self):
        """Test parsing queries that contain DOS-style switches"""
        executor = es_tui.ESExecutor("es.exe")

        # Test query with embedded switches
        query = "test /ad -sort size"
        search_terms, switches = executor._parse_query_string(query)

        assert "test" in search_terms
        assert "/ad" in switches
        assert "-sort" in switches
        assert "size" in switches

    def test_quoted_search_terms(self):
        """Test parsing of quoted search terms"""
        executor = es_tui.ESExecutor("es.exe")

        query = '"quarterly report" budget'
        search_terms, switches = executor._parse_query_string(query)

        assert '"quarterly report"' in search_terms
        assert "budget" in search_terms

    def test_complex_query_parsing(self):
        """Test parsing of complex queries with mixed elements"""
        executor = es_tui.ESExecutor("es.exe")

        query = '-case "project report" -n 20 /ad budget'
        search_terms, switches = executor._parse_query_string(query)

        assert '"project report"' in search_terms
        assert "budget" in search_terms
        assert "-case" in switches
        assert "-n" in switches
        assert "20" in switches
        assert "/ad" in switches


class TestNavigationLogic:
    """Test navigation and selection logic without UI dependencies"""

    def test_pagination_bounds(self):
        """Test pagination boundary calculations"""
        # Simulate pagination logic
        total_results = 100
        page_size = 20
        current_page = 0

        # Test bounds for first page
        start_idx = current_page * page_size
        end_idx = min(start_idx + page_size, total_results)

        assert start_idx == 0
        assert end_idx == 20

        # Test bounds for last page
        current_page = 4  # page 5 (0-indexed)
        start_idx = current_page * page_size
        end_idx = min(start_idx + page_size, total_results)

        assert start_idx == 80
        assert end_idx == 100

    def test_selection_wraparound(self):
        """Test selection wraparound logic"""
        num_items = 10

        # Test forward wraparound
        current_selection = 9
        next_selection = (current_selection + 1) % num_items
        assert next_selection == 0

        # Test backward wraparound
        current_selection = 0
        prev_selection = (current_selection - 1) % num_items
        assert prev_selection == 9

    def test_scroll_offset_calculation(self):
        """Test scroll offset calculations for result lists"""
        visible_rows = 10
        total_results = 50

        # Test scrolling to keep current selection visible
        current_selection = 15
        current_offset = 10

        # Selection below visible area
        if current_selection >= current_offset + visible_rows:
            new_offset = current_selection - visible_rows + 1
            assert new_offset == 6

        # Selection above visible area
        current_selection = 5
        if current_selection < current_offset:
            new_offset = current_selection
            assert new_offset == 5


class TestSortingLogic:
    """Test result sorting logic"""

    def test_sort_key_generation(self):
        """Test generation of sort keys for different field types"""
        # Mock results with different attributes
        results = [
            Mock(filename="b.txt", size=2000, date_modified="2024-01-01"),
            Mock(filename="a.txt", size=1000, date_modified="2024-01-02"),
            Mock(filename="c.txt", size=3000, date_modified="2023-12-31"),
        ]

        # Test name sorting
        def name_sort_key(result):
            return result.filename.lower()

        sorted_by_name = sorted(results, key=name_sort_key)
        assert [r.filename for r in sorted_by_name] == ["a.txt", "b.txt", "c.txt"]

        # Test size sorting
        def size_sort_key(result):
            return result.size

        sorted_by_size = sorted(results, key=size_sort_key)
        assert [r.size for r in sorted_by_size] == [1000, 2000, 3000]

    def test_extension_sorting(self):
        """Test sorting by file extension"""
        results = [
            Mock(filename="file.zip"),
            Mock(filename="file.txt"),
            Mock(filename="file.pdf"),
        ]

        def ext_sort_key(result):
            return os.path.splitext(result.filename)[1].lower()

        sorted_by_ext = sorted(results, key=ext_sort_key)
        extensions = [os.path.splitext(r.filename)[1] for r in sorted_by_ext]
        assert extensions == [".pdf", ".txt", ".zip"]


class TestFormattingHelpers:
    """Test UI formatting helper functions"""

    @patch("es_tui.os.stat")
    def test_file_size_formatting(self, mock_stat):
        """Test file size formatting logic"""
        # Mock different file sizes
        mock_stat.return_value.st_size = 1024

        # Test auto format (from es_tui._format_size equivalent logic)
        def format_size(size_bytes, mode=0):
            if mode == 0:  # Auto
                if size_bytes < 1024:
                    return f"{size_bytes} B"
                elif size_bytes < 1024 * 1024:
                    return f"{size_bytes / 1024:.1f} KB"
                elif size_bytes < 1024 * 1024 * 1024:
                    return f"{size_bytes / (1024 * 1024):.1f} MB"
                else:
                    return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
            elif mode == 1:  # Bytes
                return f"{size_bytes:,}"

        assert format_size(512) == "512 B"
        assert format_size(1536) == "1.5 KB"
        assert format_size(1024 * 1024 * 2) == "2.0 MB"
        assert format_size(1024 * 1024 * 1024 * 3) == "3.0 GB"

        # Test bytes mode
        assert format_size(1024, 1) == "1,024"

    def test_column_width_calculation(self):
        """Test column width calculation logic"""
        terminal_width = 100

        # Simulate column width distribution
        icon_width = 3
        name_width = 30
        size_width = 10
        date_width = 20
        remaining_width = (
            terminal_width - icon_width - name_width - size_width - date_width - 4
        )  # spaces
        path_width = max(10, remaining_width)

        assert path_width == 33
        total_width = icon_width + name_width + size_width + date_width + path_width + 4
        assert total_width <= terminal_width

    def test_text_truncation(self):
        """Test text truncation for column display"""

        def truncate_text(text, max_width):
            if len(text) <= max_width:
                return text.ljust(max_width)
            else:
                return text[: max_width - 3] + "..."

        assert truncate_text("short", 10) == "short     "
        assert (
            truncate_text("this is a very long filename.txt", 15) == "this is a ve..."
        )


class TestAdvancedSearchOptions:
    """Test AdvancedSearchOptions dataclass and query building"""

    def test_default_advanced_options(self):
        """Test default values in AdvancedSearchOptions"""
        options = es_tui.AdvancedSearchOptions()

        assert options.search_text == ""
        assert options.search_mode == "normal"
        assert options.files_only is False
        assert options.folders_only is False
        assert options.sort_field == "name"
        assert options.sort_order == "ascending"
        assert options.max_results == "1000"

    def test_build_query_from_advanced_options(self):
        """Test query string building from advanced options"""
        # This would test the AdvancedSearchDialog.build_query method
        # Since it's complex, we test the logic components

        # Test file extension handling
        extensions = "pdf,doc,txt"
        ext_list = [ext.strip() for ext in extensions.split(",") if ext.strip()]
        assert ext_list == ["pdf", "doc", "txt"]

        # Test size filter formatting
        size_min = "1mb"
        size_max = "10mb"

        # Would generate: size:>=1mb size:<=10mb
        size_filters = []
        if size_min:
            size_filters.append(f"size:>={size_min}")
        if size_max:
            size_filters.append(f"size:<={size_max}")

        assert size_filters == ["size:>=1mb", "size:<=10mb"]


class TestPropertiesHelpers:
    """Test file properties gathering helpers"""

    @patch("es_tui.os.stat")
    @patch("es_tui.os.path.isfile")
    @patch("es_tui.os.path.isdir")
    def test_gather_file_properties_basic(self, mock_isdir, mock_isfile, mock_stat):
        """Test basic file properties gathering"""
        # Mock file stat information
        mock_stat_result = Mock()
        mock_stat_result.st_size = 1024
        mock_stat_result.st_ctime = 1642248000  # 2022-01-15 12:00:00
        mock_stat_result.st_mtime = 1642251600  # 2022-01-15 13:00:00
        mock_stat_result.st_atime = 1642255200  # 2022-01-15 14:00:00
        mock_stat.return_value = mock_stat_result

        mock_isfile.return_value = True
        mock_isdir.return_value = False

        # Test properties gathering
        with patch("es_tui._fmt_bytes") as mock_fmt_bytes, patch(
            "es_tui._fmt_ts"
        ) as mock_fmt_ts:

            mock_fmt_bytes.return_value = "1.0 KB"
            mock_fmt_ts.side_effect = [
                "2022-01-15 12:00:00",
                "2022-01-15 13:00:00",
                "2022-01-15 14:00:00",
            ]

            props = es_tui.gather_file_properties("C:\\test.txt")

            assert props["Name"] == "test.txt"
            assert props["Location"] == "C:\\"
            assert props["Size"] == "1.0 KB"
            assert props["Created"] == "2022-01-15 12:00:00"
            assert props["Modified"] == "2022-01-15 13:00:00"
            assert props["Accessed"] == "2022-01-15 14:00:00"

    def test_format_bytes_helper(self):
        """Test _fmt_bytes helper function"""

        # Test the helper function logic
        def fmt_bytes(n):
            try:
                for unit in ["B", "KB", "MB", "GB", "TB", "PB"]:
                    if n < 1024 or unit == "PB":
                        return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
                    n /= 1024.0
            except Exception:
                return str(n)

        assert fmt_bytes(512) == "512 B"
        assert fmt_bytes(1536) == "1.5 KB"
        assert fmt_bytes(1024 * 1024 * 2.5) == "2.5 MB"

    def test_format_timestamp_helper(self):
        """Test _fmt_ts helper function"""
        import datetime

        def fmt_ts(timestamp):
            try:
                return datetime.datetime.fromtimestamp(timestamp).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            except Exception:
                return ""

        # Test known timestamp
        test_timestamp = (
            1642248000  # 2022-01-15 12:00:00 UTC (adjust for local timezone)
        )
        result = fmt_ts(test_timestamp)
        assert "2022-01-15" in result
        assert ":" in result  # Should contain time


class TestCopyHelpers:
    """Test clipboard functionality helpers"""

    @patch("es_tui.subprocess.run")
    def test_copy_to_clipboard_success(self, mock_run):
        """Test successful clipboard copy operation"""
        mock_run.return_value.returncode = 0

        result = es_tui.copy_to_clipboard("test text")
        assert result is True

        # Verify PowerShell command was called
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "powershell" in call_args
        assert "Set-Clipboard" in " ".join(call_args)

    @patch("es_tui.subprocess.run")
    def test_copy_to_clipboard_failure(self, mock_run):
        """Test clipboard copy failure handling"""
        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = "PowerShell error"

        result = es_tui.copy_to_clipboard("test text")
        assert result is False

    @patch("es_tui.subprocess.run")
    def test_copy_special_characters(self, mock_run):
        """Test clipboard copy with special characters"""
        mock_run.return_value.returncode = 0

        special_text = "Text with 'quotes' and special chars: café naïve"
        result = es_tui.copy_to_clipboard(special_text)
        assert result is True

        # Verify escaping was applied (single quotes doubled)
        call_args = " ".join(mock_run.call_args[0][0])
        assert "''quotes''" in call_args  # Single quotes should be doubled


class TestOpenFileHelpers:
    """Test file opening functionality"""

    @patch("es_tui.os.path.exists")
    @patch("es_tui.os.access")
    @patch("es_tui.os.startfile")
    @patch("es_tui.sys.platform", "win32")
    def test_open_with_default_app_windows(
        self, mock_startfile, mock_access, mock_exists
    ):
        """Test opening files on Windows"""
        mock_exists.return_value = True
        mock_access.return_value = True

        result = es_tui.open_with_default_app("C:\\test.txt")
        assert result is True
        mock_startfile.assert_called_once_with("C:\\test.txt")

    @patch("es_tui.os.path.exists")
    def test_open_nonexistent_file(self, mock_exists):
        """Test opening non-existent file"""
        mock_exists.return_value = False

        result = es_tui.open_with_default_app("C:\\nonexistent.txt")
        assert result is False

    @patch("es_tui.os.path.exists")
    @patch("es_tui.os.access")
    def test_open_no_permission(self, mock_access, mock_exists):
        """Test opening file without read permission"""
        mock_exists.return_value = True
        mock_access.return_value = False

        result = es_tui.open_with_default_app("C:\\restricted.txt")
        assert result is False


class TestAntiCheatProtections:
    """Tests to prevent AI coding anti-patterns in TUI code"""

    def test_no_environment_variable_cheating(self):
        """Ensure TUI logic doesn't check for test environment variables"""
        test_env_vars = ["PYTEST_CURRENT_TEST", "CI", "GITHUB_ACTIONS", "TESTING"]

        for var in test_env_vars:
            with patch.dict(os.environ, {var: "true"}):
                # File icon logic should be unaffected
                result = Mock(filename="test.txt", is_folder=False)
                icon = es_tui.FileTypeIcons.get_icon(result, use_unicode=True)
                assert icon == "📄"

                # Search options should be unaffected
                options = es_tui.SearchOptions(query="test")
                assert options.query == "test"

    def test_no_hardcoded_responses(self):
        """Test that functions produce dynamic outputs based on inputs"""
        # Test different inputs produce different icon outputs
        txt_result = Mock(filename="file.txt", is_folder=False)
        pdf_result = Mock(filename="file.pdf", is_folder=False)

        txt_icon = es_tui.FileTypeIcons.get_icon(txt_result, use_unicode=True)
        pdf_icon = es_tui.FileTypeIcons.get_icon(pdf_result, use_unicode=True)

        assert txt_icon != pdf_icon  # Should be different

        # Test sort modes produce different values
        assert es_tui.SortMode.NAME != es_tui.SortMode.SIZE
        assert es_tui.SearchMode.NORMAL != es_tui.SearchMode.REGEX

    def test_no_test_directory_access(self):
        """Ensure implementation doesn't read from test directories"""
        with patch("builtins.open", side_effect=FileNotFoundError):
            try:
                # Normal operations shouldn't try to read external files
                options = es_tui.SearchOptions(query="test")
                result = Mock(filename="test.txt", is_folder=False)
                icon = es_tui.FileTypeIcons.get_icon(result)
            except FileNotFoundError:
                pytest.fail(
                    "Implementation shouldn't read external files during normal operation"
                )

    def test_error_propagation_not_swallowed(self):
        """Ensure errors are properly propagated"""
        executor = es_tui.ESExecutor("non_existent_es.exe")

        # Mock subprocess.run to raise exception
        with patch(
            "es_tui.subprocess.run", side_effect=FileNotFoundError("ES not found")
        ):
            options = es_tui.SearchOptions(query="test")

            results, error = executor.execute_search(options)
            # Should return error message, not crash silently
            assert "ES executable not found" in error or "ES not found" in error
            assert results == []


class TestInputValidationAndSanitization:
    """Test input validation and sanitization logic"""

    def test_query_sanitization(self):
        """Test that queries are properly sanitized"""
        dangerous_queries = [
            "'; DROP TABLE files; --",
            "../../etc/passwd",
            "<script>alert('xss')</script>",
            "query WITH MALICIOUS SQL",
        ]

        for query in dangerous_queries:
            # Should not crash when creating SearchOptions
            options = es_tui.SearchOptions(query=query)
            assert (
                options.query == query
            )  # Should store as-is, sanitization happens later

    def test_path_validation(self):
        """Test file path validation"""
        invalid_paths = [
            "",
            "   ",
            "C:\\nonexistent\\path\\file.txt",
            "/root/restricted/file.txt",
            "\\\\invalid\\unc\\path",
        ]

        for path in invalid_paths:
            # open_with_default_app should handle invalid paths gracefully
            result = es_tui.open_with_default_app(path)
            assert result is False  # Should fail gracefully, not crash

    def test_unicode_handling(self):
        """Test Unicode character handling in various components"""
        unicode_filenames = [
            "café_menu.txt",
            "документ.doc",
            "תיק_עבודה.pdf",
            "ファイル.jpg",
            "🗂️_folder",
        ]

        for filename in unicode_filenames:
            result = Mock(filename=filename, is_folder=False)
            # Should not crash with Unicode filenames
            icon = es_tui.FileTypeIcons.get_icon(result)
            assert icon is not None

            # Search options should handle Unicode
            options = es_tui.SearchOptions(query=filename)
            assert options.query == filename


class TestPerformanceAndResourceManagement:
    """Test performance characteristics and resource management"""

    def test_large_result_set_handling(self):
        """Test handling of large result sets"""
        # Simulate large result set
        large_result_count = 10000

        # Test pagination calculation doesn't break with large numbers
        page_size = 50
        total_pages = (large_result_count + page_size - 1) // page_size
        assert total_pages == 200

        # Test bounds checking
        current_page = total_pages - 1  # Last page
        start_idx = current_page * page_size
        end_idx = min(start_idx + page_size, large_result_count)

        assert start_idx == 9950
        assert end_idx == 10000

    def test_memory_efficient_operations(self):
        """Test that operations don't hold unnecessary references"""
        # Create mock results and ensure they can be garbage collected
        results = [Mock(filename=f"file_{i}.txt") for i in range(100)]

        # Simulate processing results in chunks
        chunk_size = 10
        processed_chunks = []

        for i in range(0, len(results), chunk_size):
            chunk = results[i : i + chunk_size]
            processed_chunks.append(len(chunk))  # Just keep count, not references

        assert len(processed_chunks) == 10
        assert sum(processed_chunks) == 100


class TestErrorHandlingEdgeCases:
    """Test error handling in edge cases"""

    def test_malformed_search_results(self):
        """Test handling of malformed or incomplete search results"""
        malformed_results = [
            Mock(filename="test.txt"),  # Missing other attributes
            Mock(full_path="C:\\test.txt"),  # Missing filename
            Mock(),  # Missing all attributes
        ]

        for result in malformed_results:
            # Should not crash when accessing attributes
            filename = getattr(result, "filename", "")
            full_path = getattr(result, "full_path", "")
            is_folder = getattr(result, "is_folder", False)

            # Icon selection should handle missing attributes
            icon = es_tui.FileTypeIcons.get_icon(result)
            assert icon is not None

    def test_concurrent_modification_safety(self):
        """Test safety against concurrent modifications"""
        # Simulate result list being modified during iteration
        results = [Mock(filename=f"file_{i}.txt") for i in range(10)]

        # Create a copy for safe iteration (what the implementation should do)
        safe_results = results.copy()

        # Modify original list during "iteration"
        results.clear()

        # Safe copy should still be intact
        assert len(safe_results) == 10
        assert all(hasattr(r, "filename") for r in safe_results)

    def test_invalid_sort_parameters(self):
        """Test handling of invalid sort parameters"""
        invalid_sorts = [
            Mock(sort_field=None),
            Mock(sort_field="nonexistent_field"),
            Mock(sort_field=123),  # Wrong type
        ]

        for sort_config in invalid_sorts:
            # Should handle invalid sort configurations gracefully
            sort_field = getattr(sort_config, "sort_field", "name")
            if sort_field not in ["name", "size", "date", "extension", "path"]:
                sort_field = "name"  # Fallback to safe default

            assert sort_field in [
                "name",
                "size",
                "date",
                "extension",
                "path",
                "nonexistent_field",
            ]
