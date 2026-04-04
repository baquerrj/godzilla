"""Tests for the requirements trace HTML visualizer CLI."""

from __future__ import annotations

import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from godzilla_core.scripts.visualize_requirements import (
    load_requirements_trace,
    main,
    render_html,
)


class RequirementsVisualizerCliTests(unittest.TestCase):
    """Tests for the requirements visualization command-line entry point."""

    def test_main_generates_html_visualization(self) -> None:
        """The CLI writes an HTML file beside the YAML input and prints its path."""
        yaml_text = """
- requirement_id: ACC-SYS-001
  title: System purpose
  requirement_type: acceptance
  implementation_status: implemented
  verification_method: system
  verification_notes: End-to-end trace stub
  gap_notes: No single unit test covers the full workflow.
  code_refs:
    - godzilla_core/api/app.py:create_app
  test_refs:
    - godzilla_core/tests/test_requirement_traceability.py:test_sys_001_system_trace_stub
  doc_refs:
    - docs/requirements/requirements.md
- requirement_id: TECH-SYS-004
  title: Timestamp metadata
  requirement_type: technical
  parent_requirement_id: ACC-SYS-001
  implementation_status: implemented
  verification_method: unit
  verification_notes: Focused unit tests
  code_refs:
    - godzilla_core/util/time.py:local_timestamp_metadata
  test_refs:
    - godzilla_core/tests/test_secrets.py:SecretStoreTests
  doc_refs:
    - docs/design/database-schema.md
"""

        with tempfile.TemporaryDirectory() as tmp_dir:
            requirements_path = Path(tmp_dir) / "requirements.yml"
            requirements_path.write_text(yaml_text)

            stdout = StringIO()
            stderr = StringIO()
            with (
                patch.object(sys, "argv", ["visualize-requirements", str(requirements_path)]),
                patch("sys.stdout", stdout),
                patch("sys.stderr", stderr),
            ):
                exit_code = main()

            output_path = requirements_path.with_name("requirements.visualization.html")
            self.assertEqual(exit_code, 0)
            self.assertEqual(stdout.getvalue().strip(), str(output_path))
            self.assertEqual(stderr.getvalue(), "")
            self.assertTrue(output_path.exists())

            html = output_path.read_text()
            self.assertIn("Requirements Trace Visualizer", html)
            self.assertIn("ACC-SYS-001", html)
            self.assertIn("TECH-SYS-004", html)
            self.assertIn("Total requirements", html)
            self.assertIn("parent_requirement_id", html)
            self.assertIn("Relationship Tree", html)
            self.assertIn("focus-requirement-select", html)
            self.assertIn("relationship-graph", html)
            self.assertIn("focus-summary", html)
            self.assertIn("Focused Requirement", html)
            self.assertIn("godzilla_core/util/time.py:local_timestamp_metadata", html)

    def test_main_returns_error_for_missing_file(self) -> None:
        """The CLI exits non-zero when the YAML path does not exist."""
        missing_path = Path("/tmp/does-not-exist-requirements.yml")
        stdout = StringIO()
        stderr = StringIO()
        with (
            patch.object(sys, "argv", ["visualize-requirements", str(missing_path)]),
            patch("sys.stdout", stdout),
            patch("sys.stderr", stderr),
        ):
            exit_code = main()

        self.assertEqual(exit_code, 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("Requirements file does not exist", stderr.getvalue())

    def test_main_returns_error_for_invalid_yaml(self) -> None:
        """The CLI exits non-zero when the YAML is malformed."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            requirements_path = Path(tmp_dir) / "requirements.yml"
            requirements_path.write_text(":\n - broken")

            stdout = StringIO()
            stderr = StringIO()
            with (
                patch.object(sys, "argv", ["visualize-requirements", str(requirements_path)]),
                patch("sys.stdout", stdout),
                patch("sys.stderr", stderr),
            ):
                exit_code = main()

        self.assertEqual(exit_code, 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("Malformed YAML", stderr.getvalue())

    def test_main_returns_error_for_non_list_top_level(self) -> None:
        """The CLI exits non-zero when the top-level YAML object is not a list."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            requirements_path = Path(tmp_dir) / "requirements.yml"
            requirements_path.write_text("requirement_id: ACC-SYS-001\n")

            stderr = StringIO()
            with (
                patch.object(sys, "argv", ["visualize-requirements", str(requirements_path)]),
                patch("sys.stderr", stderr),
            ):
                exit_code = main()

        self.assertEqual(exit_code, 1)
        self.assertIn("top-level list", stderr.getvalue())

    def test_main_returns_error_for_duplicate_requirement_ids(self) -> None:
        """The CLI exits non-zero when duplicate requirement IDs are present."""
        yaml_text = """
- requirement_id: ACC-SYS-001
  title: One
  requirement_type: acceptance
- requirement_id: ACC-SYS-001
  title: Two
  requirement_type: acceptance
"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            requirements_path = Path(tmp_dir) / "requirements.yml"
            requirements_path.write_text(yaml_text)

            stderr = StringIO()
            with (
                patch.object(sys, "argv", ["visualize-requirements", str(requirements_path)]),
                patch("sys.stderr", stderr),
            ):
                exit_code = main()

        self.assertEqual(exit_code, 1)
        self.assertIn("Duplicate requirement_id found: ACC-SYS-001", stderr.getvalue())

    def test_main_returns_error_for_missing_required_fields(self) -> None:
        """The CLI exits non-zero when a required field is missing."""
        yaml_text = """
- requirement_id: ACC-SYS-001
  requirement_type: acceptance
"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            requirements_path = Path(tmp_dir) / "requirements.yml"
            requirements_path.write_text(yaml_text)

            stderr = StringIO()
            with (
                patch.object(sys, "argv", ["visualize-requirements", str(requirements_path)]),
                patch("sys.stderr", stderr),
            ):
                exit_code = main()

        self.assertEqual(exit_code, 1)
        self.assertIn("missing required field(s): title", stderr.getvalue())

    def test_repo_trace_file_renders_known_relationships_and_trace_markers(self) -> None:
        """The renderer preserves known IDs, parent-child relationships, and trace stubs."""
        repo_root = Path(__file__).resolve().parents[2]
        requirements_path = repo_root / "trace" / "requirements.yml"

        entries = load_requirements_trace(requirements_path)
        html = render_html(entries, requirements_path)

        self.assertIn("ACC-SYS-001", html)
        self.assertIn("ACC-SYS-003", html)
        self.assertIn("ACC-ACCT-006", html)
        self.assertIn("Focused Requirement", html)
        self.assertIn("relationship-graph", html)
        self.assertIn("All requirements are visible in one view.", html)
        self.assertIn(
            "godzilla_core/tests/test_requirement_traceability.py:"
            "test_sys_001_system_trace_stub",
            html,
        )
        self.assertIn(
            "godzilla_core/tests/test_plaid_client.py:"
            "PlaidClientPostTests.test_post_retries_429_and_honors_retry_after",
            html,
        )
        self.assertIn('"parent_requirement_id": "ACC-SYS-001"', html)


if __name__ == "__main__":
    unittest.main()
