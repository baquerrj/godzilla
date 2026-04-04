"""Nox sessions for quality checks and packaging.

REQ: TECH-SEC-DATA-004
"""

import nox

nox.options.reuse_existing_virtualenvs = True


@nox.session(python="3.12")
def lint(session: nox.Session) -> None:
    """Run lint checks for source formatting and static style.

    REQ: TECH-SEC-DATA-004
    """
    session.install("black>=24.0.0", "ruff>=0.6.0")
    session.run("ruff", "check", "godzilla_core")
    session.run("black", "--check", "godzilla_core", "noxfile.py")
    with session.chdir("ui"):
        session.run("npm", "run", "lint", external=True)


@nox.session(python="3.12")
def format(session: nox.Session) -> None:
    """Auto-format source files with Black.

    REQ: TECH-SEC-DATA-004
    """
    session.install("black>=24.0.0")
    session.run("black", "godzilla_core", "noxfile.py")
    with session.chdir("ui"):
        session.run("npm", "run", "format", external=True)


@nox.session(python="3.12")
def tests(session: nox.Session) -> None:
    """Run the automated test suite.

    REQ: TECH-SEC-DATA-004
    """
    session.install(".[dev]")
    session.run("pytest")


@nox.session(python="3.12")
def build(session: nox.Session) -> None:
    """Build a wheel distribution for the project.

    REQ: TECH-SEC-DATA-004
    """
    session.install("build")
    session.run("python", "-m", "build", "--wheel")


@nox.session(python="3.12")
def security(session: nox.Session) -> None:
    """Run dependency vulnerability checks for backend and UI.

    REQ: TECH-SEC-DATA-004
    """
    session.install("pip-audit")
    session.run("pip-audit")
    with session.chdir("ui"):
        session.run("npm", "audit", "--audit-level=high", external=True)
