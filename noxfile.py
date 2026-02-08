import nox

nox.options.reuse_existing_virtualenvs = True

@nox.session(python="3.12")
def lint(session: nox.Session) -> None:
    session.install("ruff>=0.6.0")
    session.run("ruff", "check", "godzilla_core")


@nox.session(python="3.12")
def tests(session: nox.Session) -> None:
    session.install(".[dev]")
    session.run("pytest")


@nox.session(python="3.12")
def build(session: nox.Session) -> None:
    session.install("build")
    session.run("python", "-m", "build", "--wheel")
