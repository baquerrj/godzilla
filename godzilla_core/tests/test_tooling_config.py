"""Tooling configuration tests.

REQ: SEC-DATA-004
"""

import json
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

    def test_devcontainer_targets_dev_compose_service(self) -> None:
        """Ensure VS Code devcontainer settings point to the Docker dev service.

        REQ: SEC-DATA-004
        """
        devcontainer_path = (
            Path(__file__).resolve().parents[2] / ".devcontainer" / "devcontainer.json"
        )
        config = json.loads(devcontainer_path.read_text(encoding="utf-8"))

        self.assertEqual(config["service"], "dev")
        self.assertIn("../docker-compose.dev.yml", config["dockerComposeFile"])
        self.assertEqual(config["workspaceFolder"], "/workspace/godzilla")
        self.assertIn("REQ: SEC-DATA-004", config["godzillaRequirementTags"])

    def test_dockerfile_declares_required_dev_toolchain(self) -> None:
        """Ensure Dockerfile includes required language and network tooling.

        REQ: SEC-DATA-004
        """
        dockerfile_path = Path(__file__).resolve().parents[2] / "Dockerfile.dev"
        dockerfile_text = dockerfile_path.read_text(encoding="utf-8")

        self.assertIn("FROM python:3.12-bookworm", dockerfile_text)
        self.assertIn("node_${NODE_MAJOR}.x", dockerfile_text)
        self.assertIn("https://sh.rustup.rs", dockerfile_text)
        self.assertIn("git", dockerfile_text)
        self.assertIn("openssh-client", dockerfile_text)
        self.assertIn("REQ: SEC-DATA-004", dockerfile_text)

    def test_compose_exposes_dev_service_and_ports(self) -> None:
        """Ensure docker compose file runs the dev service with expected ports.

        REQ: SEC-DATA-004
        """
        compose_path = Path(__file__).resolve().parents[2] / "docker-compose.dev.yml"
        compose_text = compose_path.read_text(encoding="utf-8")

        self.assertIn("services:", compose_text)
        self.assertIn("  dev:", compose_text)
        self.assertIn("container_name: godzilla-dev", compose_text)
        self.assertIn("- godzilla-workspace:/workspace", compose_text)
        self.assertIn("- godzilla-data:/home/vscode/.local/share/godzilla", compose_text)
        self.assertIn(
            "GODZILLA_DB_PATH: /home/vscode/.local/share/godzilla/godzilla.db",
            compose_text,
        )
        self.assertIn(
            "GODZILLA_SECRETS_PATH: /home/vscode/.local/share/godzilla/secrets.db",
            compose_text,
        )
        self.assertIn('- "8787:8787"', compose_text)
        self.assertIn('- "8443:8443"', compose_text)
        self.assertIn("REQ: SEC-DATA-004", compose_text)

    def test_ssh_agent_overlay_for_git_authentication(self) -> None:
        """Ensure optional compose overlay forwards SSH agent for Git operations.

        REQ: SEC-DATA-004
        """
        compose_path = Path(__file__).resolve().parents[2] / "docker-compose.dev.ssh-agent.yml"
        compose_text = compose_path.read_text(encoding="utf-8")

        self.assertIn("services:", compose_text)
        self.assertIn("  dev:", compose_text)
        self.assertIn("SSH_AUTH_SOCK: /ssh-agent", compose_text)
        self.assertIn("- ${SSH_AUTH_SOCK}:/ssh-agent", compose_text)
        self.assertIn("REQ: SEC-DATA-004", compose_text)

    def test_docker_setup_doc_includes_install_and_update_workflow(self) -> None:
        """Ensure setup docs describe installation, updates, and VS Code attach.

        REQ: SEC-DATA-004
        """
        doc_path = Path(__file__).resolve().parents[2] / "docs" / "setup" / "docker-development.md"
        doc_text = doc_path.read_text(encoding="utf-8")

        self.assertIn("## What the image includes", doc_text)
        self.assertIn("## Storage model (pure named volumes)", doc_text)
        self.assertIn("## Installation and first build", doc_text)
        self.assertIn("## Run and use locally", doc_text)
        self.assertIn("## How to update the image", doc_text)
        self.assertIn("## VS Code connection to the running image", doc_text)
        self.assertIn("do not copy private keys into the container", doc_text)
