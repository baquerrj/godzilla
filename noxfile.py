"""Nox sessions for quality checks and packaging.

REQ: SEC-DATA-004
"""

import nox

nox.options.reuse_existing_virtualenvs = True


@nox.session(python="3.12")
def lint(session: nox.Session) -> None:
    session.install("black>=24.0.0", "ruff>=0.6.0")
    session.run("ruff", "check", "godzilla_core")
    session.run("black", "--check", "godzilla_core", "noxfile.py", "db_inspect.py")


@nox.session(python="3.12")
def format(session: nox.Session) -> None:
    session.install("black>=24.0.0")
    session.run("black", "godzilla_core", "noxfile.py", "db_inspect.py")


@nox.session(python="3.12")
def tests(session: nox.Session) -> None:
    session.install(".[dev]")
    session.run("pytest")


@nox.session(python="3.12")
def build(session: nox.Session) -> None:
    session.install("build")
    session.run("python", "-m", "build", "--wheel")
