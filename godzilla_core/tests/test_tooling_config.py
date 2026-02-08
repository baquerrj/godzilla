"""Tooling configuration tests.

REQ: SEC-DATA-004
"""

import tomllib
import unittest
from pathlib import Path


class ToolingConfigTests(unittest.TestCase):
    """Tests that enforce packaging and lint tooling expectations.

    REQ: SEC-DATA-004
    """

    def test_black_config_matches_ruff_rules(self) -> None:
        """Ensure Black and Ruff share key formatting configuration values.

        REQ: SEC-DATA-004
        """
        pyproject_path = Path(__file__).resolve().parents[2] / "pyproject.toml"
        config = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))

        black_config = config["tool"]["black"]
        ruff_config = config["tool"]["ruff"]

        self.assertEqual(black_config["line-length"], ruff_config["line-length"])
        self.assertEqual(black_config["target-version"], [ruff_config["target-version"]])

    def test_black_is_installed_with_dev_dependencies(self) -> None:
        """Ensure Black is included in development dependencies.

        REQ: SEC-DATA-004
        """
        pyproject_path = Path(__file__).resolve().parents[2] / "pyproject.toml"
        config = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))

        dev_dependencies = config["project"]["optional-dependencies"]["dev"]
        self.assertTrue(
            any(dependency.startswith("black") for dependency in dev_dependencies),
            "Black must be part of dev dependencies so it can be run locally.",
        )
