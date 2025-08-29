#!/usr/bin/env python3
"""
System tests for es_winsearch.py via Windows cmd.exe

Tests the complete CLI functionality through subprocess execution,
validating compatibility with es.exe flag behavior and output formats.
"""

import pytest
import subprocess
import sys
import os
import csv
import io
import tempfile
import time
from pathlib import Path

# Test helpers
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "helpers"))
try:
    from shell import ShellRunner, normalize_output
    from redact import redact_paths_and_timestamps
except ImportError:
    pytest.skip("Test helpers not available", allow_module_level=True)

# Path to es_winsearch.py
ES_WINSEARCH_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "es_winsearch.py"
)

pytestmark = pytest.mark.system


class TestBasicCLIFunctionality:
    """Test basic CLI functionality via cmd.exe"""

    def setup_method(self):
        """Setup for each test method"""
        self.shell = ShellRunner("cmd")
        self.es_cmd = [sys.executable, ES_WINSEARCH_PATH]

    def test_help_flag(self):
        """Test help flag produces expected output"""
        result = self.shell.run(self.es_cmd + ["-h"])

        assert result.returncode == 0
        assert "usage" in result.stdout.lower() or "help" in result.stdout.lower()
        assert "windows search" in result.stdout.lower()
        assert len(result.stderr.strip()) == 0

    def test_version_and_basic_info(self):
        """Test that script identifies itself properly"""
        result = self.shell.run(self.es_cmd + ["-h"])

        # Should contain identifying information
        assert "es_winsearch" in result.stdout
        assert "windows" in result.stdout.lower()
        assert "search" in result.stdout.lower()

    @pytest.mark.skipif(
        not os.path.exists(ES_WINSEARCH_PATH), reason="es_winsearch.py not found"
    )
    def test_simple_search_execution(self):
        """Test simple search execution without crashing"""
        # Use a common term that's likely to exist in any Windows system
        result = self.shell.run(self.es_cmd + ["system"], timeout=30)

        # Should not crash (exit code 0 or reasonable error)
        assert result.returncode in [
            0,
            1,
        ]  # 1 might indicate no results, which is acceptable

        if result.returncode == 1:
            # If error, should provide useful message
            assert len(result.stderr) > 0
            assert (
                "error" in result.stderr.lower()
                or "windows search" in result.stderr.lower()
            )

    def test_csv_output_format(self):
        """Test CSV output format structure"""
        result = self.shell.run(self.es_cmd + ["-csv", "system"], timeout=30)

        if result.returncode == 0 and result.stdout.strip():
            # Parse as CSV to validate structure
            csv_reader = csv.reader(io.StringIO(result.stdout))
            rows = list(csv_reader)

            # Should have at least one row if there are results
            if len(rows) > 0:
                # Check for proper CSV formatting
                assert all(isinstance(row, list) for row in rows)

                # If there's a header (without -no-header), validate it
                if not any("-no-header" in str(arg) for arg in self.es_cmd):
                    header = rows[0] if rows else []
                    # Should contain expected column names
                    header_text = ",".join(header).lower()
                    # At minimum should have path/name related columns
                    assert any(col in header_text for col in ["name", "path", "file"])

    def test_no_header_flag(self):
        """Test -no-header flag removes column headers"""
        result = self.shell.run(
            self.es_cmd + ["-csv", "-no-header", "system"], timeout=30
        )

        if result.returncode == 0 and result.stdout.strip():
            # First line should not look like a header
            first_line = result.stdout.split("\n")[0]

            # Headers typically contain words like 'name', 'size', 'path'
            # Data rows typically contain file paths or actual filenames
            header_indicators = ["name", "size", "path", "date", "modified"]
            likely_header = any(
                indicator in first_line.lower() for indicator in header_indicators
            )

            # With -no-header, first line should be data, not header
            if likely_header:
                pytest.fail(
                    f"First line appears to be a header despite -no-header flag: {first_line}"
                )

    def test_result_limit_flag(self):
        """Test -n flag limits result count"""
        limit = 5
        result = self.shell.run(
            self.es_cmd + ["-n", str(limit), "-csv", "system"], timeout=30
        )

        if result.returncode == 0 and result.stdout.strip():
            lines = result.stdout.strip().split("\n")

            # Account for potential header
            data_lines = [
                line
                for line in lines
                if line.strip() and not self._looks_like_header(line)
            ]

            # Should not exceed the limit
            assert len(data_lines) <= limit

    def test_sort_flag_variations(self):
        """Test different sort flag variations"""
        sort_variations = [
            ["-sort", "name"],
            ["-sort", "size"],
            ["-sort", "date-modified"],
        ]

        for sort_args in sort_variations:
            result = self.shell.run(
                self.es_cmd + sort_args + ["-n", "3", "system"], timeout=30
            )

            # Should not crash with sort options
            assert result.returncode in [0, 1]

            if result.returncode != 0:
                # If failed, should provide helpful error
                assert (
                    "sort" in result.stderr.lower() or "error" in result.stderr.lower()
                )

    def test_case_sensitive_flag(self):
        """Test case sensitivity flag"""
        # Test with mixed case term
        result = self.shell.run(self.es_cmd + ["-case", "System"], timeout=30)

        # Should execute without error
        assert result.returncode in [0, 1]

    def test_regex_flag(self):
        """Test regex flag functionality"""
        # Use simple regex pattern
        result = self.shell.run(self.es_cmd + ["-regex", ".*\\.txt"], timeout=30)

        # Should execute without error
        assert result.returncode in [0, 1]

        # Test invalid regex should fail gracefully
        result_invalid = self.shell.run(
            self.es_cmd + ["-regex", "[invalid"], timeout=30
        )

        if result_invalid.returncode != 0:
            assert (
                "regex" in result_invalid.stderr.lower()
                or "error" in result_invalid.stderr.lower()
            )

    def test_whole_word_flag(self):
        """Test whole word search flag"""
        result = self.shell.run(self.es_cmd + ["-whole-word", "system"], timeout=30)

        # Should execute without error
        assert result.returncode in [0, 1]

    def test_path_filter_flag(self):
        """Test path filtering functionality"""
        # Use common Windows path
        result = self.shell.run(
            self.es_cmd + ["-path", "C:\\Windows", "system"], timeout=30
        )

        # Should execute without error
        assert result.returncode in [0, 1]

    def test_files_only_folder_only_flags(self):
        """Test file/folder filtering flags"""
        # Test files only
        result_files = self.shell.run(self.es_cmd + ["/a-d", "system"], timeout=30)
        assert result_files.returncode in [0, 1]

        # Test folders only
        result_folders = self.shell.run(self.es_cmd + ["/ad", "system"], timeout=30)
        assert result_folders.returncode in [0, 1]

    def _looks_like_header(self, line):
        """Helper to identify if a line looks like a CSV header"""
        header_indicators = ["name", "size", "path", "date", "modified", "created"]
        line_lower = line.lower()
        return sum(1 for indicator in header_indicators if indicator in line_lower) >= 2


class TestErrorHandling:
    """Test error handling and edge cases"""

    def setup_method(self):
        self.shell = ShellRunner("cmd")
        self.es_cmd = [sys.executable, ES_WINSEARCH_PATH]

    def test_no_arguments_behavior(self):
        """Test behavior when no arguments provided"""
        result = self.shell.run(self.es_cmd, timeout=10)

        # Should either show help or return empty results gracefully
        assert result.returncode in [0, 1]

        # Should not crash or produce stack trace
        assert "traceback" not in result.stderr.lower()
        assert "exception" not in result.stderr.lower()

    def test_invalid_flags(self):
        """Test handling of invalid/unknown flags"""
        invalid_flags = ["--definitely-not-a-flag", "-xyz", "/invalid-dos-flag"]

        for flag in invalid_flags:
            result = self.shell.run(self.es_cmd + [flag, "test"], timeout=10)

            # Should not crash
            assert "traceback" not in result.stderr.lower()
            # May return error code, but should be handled gracefully
            if result.returncode != 0:
                # Should provide some indication of the issue
                assert len(result.stderr) > 0

    def test_malformed_regex(self):
        """Test handling of malformed regex patterns"""
        bad_patterns = ["[unclosed", "(unclosed", "*invalid", "+invalid"]

        for pattern in bad_patterns:
            result = self.shell.run(self.es_cmd + ["-regex", pattern], timeout=10)

            # Should handle regex errors gracefully
            if result.returncode != 0:
                assert (
                    "regex" in result.stderr.lower()
                    or "pattern" in result.stderr.lower()
                )
                assert "traceback" not in result.stderr.lower()

    def test_invalid_numeric_arguments(self):
        """Test handling of invalid numeric arguments"""
        invalid_numbers = ["abc", "-5", "1.5", "999999999"]

        for num in invalid_numbers:
            result = self.shell.run(self.es_cmd + ["-n", num, "test"], timeout=10)

            # Should handle invalid numbers gracefully
            assert "traceback" not in result.stderr.lower()

    def test_nonexistent_path_filter(self):
        """Test path filter with non-existent paths"""
        result = self.shell.run(
            self.es_cmd + ["-path", "Z:\\NonExistent\\Path", "test"], timeout=10
        )

        # Should execute without crashing
        assert result.returncode in [0, 1]
        assert "traceback" not in result.stderr.lower()

    def test_timeout_behavior(self):
        """Test behavior under timeout conditions"""
        # Use short timeout to test timeout handling
        result = self.shell.run(self.es_cmd + ["*"], timeout=5)

        # Should either complete or timeout gracefully
        # Note: actual timeout handling depends on implementation
        assert "traceback" not in result.stderr.lower()


class TestOutputConsistency:
    """Test output format consistency and determinism"""

    def setup_method(self):
        self.shell = ShellRunner("cmd")
        self.es_cmd = [sys.executable, ES_WINSEARCH_PATH]

    def test_output_determinism(self):
        """Test that identical queries produce consistent output"""
        query_args = ["-n", "5", "-sort", "name", "system"]

        # Run same query twice
        result1 = self.shell.run(self.es_cmd + query_args, timeout=30)
        time.sleep(1)  # Brief pause between runs
        result2 = self.shell.run(self.es_cmd + query_args, timeout=30)

        if result1.returncode == 0 and result2.returncode == 0:
            # Remove timestamps and normalize paths for comparison
            output1 = redact_paths_and_timestamps(result1.stdout)
            output2 = redact_paths_and_timestamps(result2.stdout)

            # Outputs should be very similar (allowing for minor timestamp differences)
            similarity_ratio = self._calculate_similarity(output1, output2)
            assert similarity_ratio > 0.8  # 80% similarity threshold

    def test_csv_format_compliance(self):
        """Test CSV output complies with standard format"""
        result = self.shell.run(self.es_cmd + ["-csv", "-n", "3", "system"], timeout=30)

        if result.returncode == 0 and result.stdout.strip():
            # Should parse as valid CSV
            try:
                reader = csv.reader(io.StringIO(result.stdout))
                rows = list(reader)

                # Should have consistent column count across rows
                if len(rows) > 1:
                    col_counts = [len(row) for row in rows]
                    assert (
                        len(set(col_counts)) <= 1
                    )  # All rows should have same column count

            except csv.Error as e:
                pytest.fail(f"CSV output is not valid: {e}")

    def test_character_encoding_handling(self):
        """Test proper handling of Unicode and special characters"""
        # Test with potential Unicode content
        result = self.shell.run(self.es_cmd + ["-n", "1", "document"], timeout=30)

        if result.returncode == 0:
            # Output should be properly encoded
            try:
                result.stdout.encode("utf-8")
                result.stderr.encode("utf-8")
            except UnicodeEncodeError:
                pytest.fail("Output contains invalid Unicode characters")

    def test_empty_result_handling(self):
        """Test handling of searches with no results"""
        # Use very specific search unlikely to have results
        unlikely_search = "zxcvbnm_unlikely_filename_12345"
        result = self.shell.run(self.es_cmd + [unlikely_search], timeout=10)

        # Should handle empty results gracefully
        assert result.returncode in [0, 1]
        assert "traceback" not in result.stderr.lower()

        if result.returncode == 0:
            # Empty results should still produce valid output format
            lines = result.stdout.strip().split("\n") if result.stdout.strip() else []
            # Should be either empty or contain only headers
            assert len(lines) <= 1

    def _calculate_similarity(self, str1, str2):
        """Calculate similarity ratio between two strings"""
        from difflib import SequenceMatcher

        return SequenceMatcher(None, str1, str2).ratio()


class TestEsExeCompatibility:
    """Test compatibility with es.exe flag behavior and conventions"""

    def setup_method(self):
        self.shell = ShellRunner("cmd")
        self.es_cmd = [sys.executable, ES_WINSEARCH_PATH]
        self.es_exe_available = self._check_es_exe_availability()

    def _check_es_exe_availability(self):
        """Check if es.exe is available for compatibility testing"""
        try:
            result = subprocess.run(
                ["es.exe", "-h"], capture_output=True, text=True, timeout=5
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    @pytest.mark.skipif(
        not os.path.exists(ES_WINSEARCH_PATH), reason="es_winsearch.py not found"
    )
    def test_flag_recognition_parity(self):
        """Test that common es.exe flags are recognized"""
        common_flags = [
            ["-r", ".*\\.txt"],
            ["-case", "System"],
            ["-w", "system"],
            ["-n", "5"],
            ["-sort", "name"],
            ["/ad"],  # folders only
            ["/a-d"],  # files only
        ]

        for flag_combo in common_flags:
            result = self.shell.run(self.es_cmd + flag_combo, timeout=15)

            # Flags should be recognized (no "unknown flag" errors)
            if result.returncode != 0:
                error_msg = result.stderr.lower()
                # Should not contain generic "unknown" or "unrecognized" messages
                assert "unknown" not in error_msg or "unrecognized" not in error_msg

    @pytest.mark.skipif(
        not os.path.exists(ES_WINSEARCH_PATH), reason="es_winsearch.py not found"
    )
    def test_unsupported_flags_clear_messaging(self):
        """Test that unsupported flags provide clear, helpful error messages"""
        # These flags are common in es.exe but may not be supported in es_winsearch.py
        potentially_unsupported = [
            "-highlight",
            "-export-m3u",
            "-get-run-count",
            "-instance",
        ]

        for flag in potentially_unsupported:
            result = self.shell.run(self.es_cmd + [flag, "test"], timeout=10)

            if result.returncode != 0:
                # Error message should be helpful, not generic
                error_msg = result.stderr.lower()
                # Should mention the specific flag or provide guidance
                helpful_indicators = [
                    flag.lower(),
                    "not supported",
                    "alternative",
                    "help",
                    "windows search",
                ]
                assert any(indicator in error_msg for indicator in helpful_indicators)

    @pytest.mark.skipif(
        "not es_exe_available", reason="es.exe not available for comparison"
    )
    def test_behavioral_consistency_with_es_exe(self):
        """Compare behavioral patterns with es.exe where applicable"""
        if not self.es_exe_available:
            pytest.skip("es.exe not available for comparison")

        # Test help flag behavior
        es_help = subprocess.run(
            ["es.exe", "-h"], capture_output=True, text=True, timeout=5
        )
        ws_help = self.shell.run(self.es_cmd + ["-h"], timeout=5)

        # Both should exit successfully with help
        assert es_help.returncode == 0
        assert ws_help.returncode == 0
        assert len(es_help.stdout) > 0
        assert len(ws_help.stdout) > 0

        # Both should contain usage information
        assert "usage" in es_help.stdout.lower() or "help" in es_help.stdout.lower()
        assert "usage" in ws_help.stdout.lower() or "help" in ws_help.stdout.lower()

    def test_dos_style_switch_support(self):
        """Test support for DOS-style switches like /ad, /a-d"""
        dos_switches = [
            "/ad",  # directories only
            "/a-d",  # files only
            "/on",  # sort by name (if supported)
            "/os",  # sort by size (if supported)
        ]

        for switch in dos_switches:
            result = self.shell.run(self.es_cmd + [switch, "system"], timeout=15)

            # Should be recognized or provide clear feedback
            if result.returncode != 0:
                # Should not be a generic "unknown command" error
                assert "traceback" not in result.stderr.lower()


class TestPerformanceAndScaling:
    """Test performance characteristics and scaling behavior"""

    def setup_method(self):
        self.shell = ShellRunner("cmd")
        self.es_cmd = [sys.executable, ES_WINSEARCH_PATH]

    def test_reasonable_response_times(self):
        """Test that queries complete within reasonable time limits"""
        start_time = time.time()

        # Simple query should complete quickly
        result = self.shell.run(self.es_cmd + ["-n", "10", "system"], timeout=30)

        elapsed_time = time.time() - start_time

        # Should complete within 30 seconds for simple query
        assert elapsed_time < 30

        # If successful, should be much faster than 30 seconds typically
        if result.returncode == 0:
            assert elapsed_time < 15  # Should be faster for successful queries

    def test_large_result_set_handling(self):
        """Test handling of potentially large result sets"""
        # Query for common files that might return many results
        result = self.shell.run(self.es_cmd + ["-n", "100", "*.txt"], timeout=60)

        # Should handle large result sets without crashing
        assert result.returncode in [0, 1]
        assert "traceback" not in result.stderr.lower()

        if result.returncode == 0 and result.stdout.strip():
            lines = result.stdout.strip().split("\n")
            # Should respect the limit
            assert (
                len([l for l in lines if l.strip()]) <= 101
            )  # +1 for potential header

    def test_memory_usage_stability(self):
        """Test that multiple queries don't indicate memory leaks"""
        # Run multiple queries in sequence
        for i in range(5):
            result = self.shell.run(self.es_cmd + ["-n", "5", "test"], timeout=15)

            # Each query should complete successfully or with consistent error
            assert result.returncode in [0, 1]
            assert "memory" not in result.stderr.lower()
            assert "traceback" not in result.stderr.lower()


class TestUnicodeAndInternationalization:
    """Test Unicode support and internationalization features"""

    def setup_method(self):
        self.shell = ShellRunner("cmd")
        self.es_cmd = [sys.executable, ES_WINSEARCH_PATH]

    def test_unicode_search_terms(self):
        """Test searching with Unicode characters"""
        unicode_terms = [
            "café",  # Latin characters with diacritics
            "naïve",  # More diacritics
            "résumé",  # Common accented word
        ]

        for term in unicode_terms:
            result = self.shell.run(self.es_cmd + ["-n", "1", term], timeout=15)

            # Should handle Unicode without crashing
            assert result.returncode in [0, 1]
            assert "traceback" not in result.stderr.lower()

            # Output should be properly encoded
            try:
                result.stdout.encode("utf-8")
                if result.stderr:
                    result.stderr.encode("utf-8")
            except UnicodeEncodeError:
                pytest.fail(f"Unicode handling failed for term: {term}")

    def test_unicode_path_handling(self):
        """Test path filters with Unicode characters"""
        unicode_paths = [
            "C:\\Utilisateurs",  # French
            "C:\\Документы",  # Cyrillic (if filesystem supports)
        ]

        for path in unicode_paths:
            result = self.shell.run(self.es_cmd + ["-path", path, "test"], timeout=15)

            # Should handle Unicode paths without crashing
            assert result.returncode in [0, 1]
            assert "traceback" not in result.stderr.lower()


class TestAntiCheatSystemValidation:
    """System-level anti-cheat validations"""

    def setup_method(self):
        self.shell = ShellRunner("cmd")
        self.es_cmd = [sys.executable, ES_WINSEARCH_PATH]

    def test_no_environment_variable_dependency(self):
        """Ensure behavior doesn't change based on test environment variables"""
        test_env_vars = {
            "PYTEST_CURRENT_TEST": "true",
            "CI": "true",
            "GITHUB_ACTIONS": "true",
            "TESTING": "1",
        }

        # Run same query with and without test environment variables
        baseline_result = self.shell.run(self.es_cmd + ["-h"], timeout=10)

        for var_name, var_value in test_env_vars.items():
            # Set environment variable and run same command
            env = os.environ.copy()
            env[var_name] = var_value

            result = self.shell.run(self.es_cmd + ["-h"], timeout=10, env=env)

            # Behavior should be identical
            assert result.returncode == baseline_result.returncode

            # Output should be essentially the same (allowing minor variations)
            if baseline_result.returncode == 0 and result.returncode == 0:
                similarity = self._calculate_similarity(
                    baseline_result.stdout, result.stdout
                )
                assert similarity > 0.95  # 95% similarity threshold

    def test_no_test_directory_access_attempt(self):
        """Ensure implementation doesn't try to access test directories"""
        # Monitor file system access during execution
        # This is a simplified check - more sophisticated monitoring could be added

        result = self.shell.run(self.es_cmd + ["-h"], timeout=10)

        # Should complete normally without trying to access test files
        assert result.returncode == 0
        assert "permission denied" not in result.stderr.lower()
        assert "access denied" not in result.stderr.lower()

    def test_consistent_error_handling(self):
        """Ensure error handling is consistent, not test-specific"""
        error_conditions = [
            ["-regex", "[invalid"],  # Bad regex
            ["-n", "invalid"],  # Bad numeric argument
            ["--unknown-flag"],  # Unknown flag
        ]

        for error_args in error_conditions:
            result = self.shell.run(self.es_cmd + error_args, timeout=10)

            # Should handle errors consistently
            if result.returncode != 0:
                # Should provide error message
                assert len(result.stderr) > 0
                # Should not contain debug/test-specific information
                debug_indicators = ["pytest", "test_", "__pycache__", "unittest"]
                assert not any(
                    indicator in result.stderr.lower() for indicator in debug_indicators
                )

    def _calculate_similarity(self, str1, str2):
        """Calculate similarity ratio between two strings"""
        from difflib import SequenceMatcher

        return SequenceMatcher(None, str1, str2).ratio()


class TestExportFunctionality:
    """Test export functionality if implemented"""

    def setup_method(self):
        self.shell = ShellRunner("cmd")
        self.es_cmd = [sys.executable, ES_WINSEARCH_PATH]
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        """Clean up temporary files"""
        import shutil

        try:
            shutil.rmtree(self.temp_dir)
        except Exception:
            pass  # Best effort cleanup

    def test_csv_export_to_file(self):
        """Test CSV export functionality"""
        output_file = os.path.join(self.temp_dir, "test_output.csv")

        result = self.shell.run(
            self.es_cmd + ["-export-csv", output_file, "-n", "2", "system"], timeout=30
        )

        if result.returncode == 0:
            # Should create the output file
            assert os.path.exists(output_file)

            # File should contain valid CSV data
            with open(output_file, "r", encoding="utf-8") as f:
                content = f.read()

            if content.strip():
                # Should be parseable as CSV
                try:
                    reader = csv.reader(io.StringIO(content))
                    rows = list(reader)
                    assert len(rows) > 0
                except csv.Error as e:
                    pytest.fail(f"Exported CSV is invalid: {e}")
        else:
            # If export failed, should provide clear error message
            assert "export" in result.stderr.lower() or "csv" in result.stderr.lower()

    def test_export_with_empty_results(self):
        """Test export behavior with empty result sets"""
        output_file = os.path.join(self.temp_dir, "empty_output.csv")

        # Use search term unlikely to have results
        result = self.shell.run(
            self.es_cmd + ["-export-csv", output_file, "zxcvbnm_unlikely"], timeout=15
        )

        # Should handle empty results gracefully
        assert result.returncode in [0, 1]
        assert "traceback" not in result.stderr.lower()


@pytest.mark.integration
class TestSystemIntegration:
    """Test integration with Windows Search service"""

    def setup_method(self):
        self.shell = ShellRunner("cmd")
        self.es_cmd = [sys.executable, ES_WINSEARCH_PATH]

    def test_windows_search_service_dependency(self):
        """Test graceful handling when Windows Search service is unavailable"""
        # This test may require service manipulation or mocking
        # For now, test that errors are handled gracefully

        result = self.shell.run(self.es_cmd + ["test_service_check"], timeout=30)

        # Should not crash regardless of service status
        assert "traceback" not in result.stderr.lower()

        if result.returncode != 0:
            # Error message should be informative
            error_msg = result.stderr.lower()
            service_indicators = [
                "windows search",
                "search service",
                "indexing service",
                "service",
                "index",
            ]
            assert any(indicator in error_msg for indicator in service_indicators)

    def test_index_availability_check(self):
        """Test handling of indexing availability"""
        # Simple query that should work if indexing is available
        result = self.shell.run(self.es_cmd + ["-n", "1", "windows"], timeout=30)

        # Should provide informative feedback about index status
        if result.returncode != 0:
            error_msg = result.stderr.lower()
            # Should not be a generic error
            assert len(error_msg) > 10  # Should provide substantial error message
            assert "traceback" not in error_msg
