# Docker Development Environment (Linux MVP)

Requirements: SEC-DATA-004

## What the image includes
The dev image defined by `Dockerfile.dev` contains:
- Python 3.12 and `pip`, `setuptools`, `wheel`, `nox`
- Node.js 24 LTS and npm 11
- Rust stable toolchain (`rustc`, `cargo`, `rustup`)
- Git, OpenSSH client, curl, wget, and common Linux build tooling
- Tauri Linux prerequisites already used by this project:
  - `libwebkit2gtk-4.1-dev`
  - `libxdo-dev`
  - `libssl-dev`
  - `libayatana-appindicator3-dev`
  - `librsvg2-dev`

## Storage model (pure named volumes)
- Source workspace volume: `godzilla-workspace` mounted at `/workspace`
- App data volume: `godzilla-data` mounted at `/home/vscode/.local/share/godzilla`
- Dependency cache volumes:
  - `godzilla-pip-cache`
  - `godzilla-npm-cache`
  - `godzilla-cargo-registry`
  - `godzilla-cargo-git`

Compose includes an `init-perms` helper service that runs as root before `dev`
starts. It ensures these named-volume mountpoints are owned by the `vscode`
user so SQLCipher, npm, and Cargo can write without manual permission fixes.

The application DB and secrets DB paths are set by compose as:
- `GODZILLA_DB_PATH=/home/vscode/.local/share/godzilla/godzilla.db`
- `GODZILLA_SECRETS_PATH=/home/vscode/.local/share/godzilla/secrets.db`

The dev container is pinned to a stable name for repeatable manual commands:
- `godzilla-dev`

## Prerequisites on the host
- Docker Engine with Compose plugin (`docker compose`)
- VS Code with the "Dev Containers" extension if you want editor attach support

## Installation and first build
From the repository root (this repository only provides the compose and image definitions):

```bash
docker compose -f docker-compose.dev.yml build dev
docker compose -f docker-compose.dev.yml up -d dev
docker compose -f docker-compose.dev.yml exec dev git clone <repo-url> /workspace/godzilla
docker compose -f docker-compose.dev.yml exec dev bash -lc 'cd /workspace/godzilla && python3 -m pip install -e ".[dev]" && npm install'
```

Manual `docker exec` is now stable:

```bash
docker exec -it godzilla-dev bash
```

## Run and use locally
Start or restart the development container:

```bash
docker compose -f docker-compose.dev.yml up -d dev
```

If you need to re-apply ownership on existing volumes, run:

```bash
docker compose -f docker-compose.dev.yml up --force-recreate init-perms
```

Open an interactive shell:

```bash
docker compose -f docker-compose.dev.yml exec dev bash
```

Run quality checks inside the container:

```bash
docker compose -f docker-compose.dev.yml exec dev bash -lc 'cd /workspace/godzilla && nox -s lint'
docker compose -f docker-compose.dev.yml exec dev bash -lc 'cd /workspace/godzilla && nox -s tests'
docker compose -f docker-compose.dev.yml exec dev bash -lc 'cd /workspace/godzilla && nox -s build'
```

Run the API server from inside the container (example):

```bash
docker compose -f docker-compose.dev.yml exec dev bash -lc 'cd /workspace/godzilla && godzilla-api --host 127.0.0.1 --port 8787'
```

## Tauri GUI requirement in containers
`npm run tauri dev` requires a Linux display server (X11/Wayland). In a
headless container, Tauri may panic with:

- `Failed to initialize GTK`

For headless validation use:

```bash
docker compose -f docker-compose.dev.yml exec dev bash -lc 'cd /workspace/godzilla/ui && npm run dev'
```

## VS Code connection to the running image
1. Start the container with `docker compose -f docker-compose.dev.yml up -d dev`.
2. In VS Code, run `Dev Containers: Attach to Running Container...`.
3. Select the running container for this project.
4. Open `/workspace/godzilla` inside the attached session.

The `.devcontainer/devcontainer.json` file is configured for the same service, but this pure named-volume workflow expects the repository content inside `/workspace/godzilla`.
If that command is missing, install the Dev Containers extension (`ms-vscode-remote.remote-containers`) in the host VS Code and reload.

## Claude CLI inside the container

The dev image installs the Claude Code CLI via the official native installer during the build. The
binary lands at `~/.local/bin/claude`, which is already on `PATH`.

Authentication credentials live in `~/.claude/` on the host. Mount them into the container with the
`docker-compose.dev.claude.yml` override so that no separate login step is required:

```bash
docker compose \
  -f docker-compose.dev.yml \
  -f docker-compose.dev.claude.yml \
  up -d dev
```

If you prefer API-key authentication instead of OAuth, export `ANTHROPIC_API_KEY` in your shell
before starting the container — the override file passes it through automatically.

The auto-updater is disabled inside the container (`DISABLE_AUTOUPDATER=1`). To pick up a new
version of Claude Code, rebuild the image:

```bash
docker compose -f docker-compose.dev.yml build --no-cache dev
```

## Git and network access
- The image includes Git and OpenSSH client tooling.
- Outbound network access is provided by Docker's default bridge networking.
- Git over HTTPS works out of the box once credentials are configured in the container.
- For SSH-based Git remotes, do not copy private keys into the container. Use SSH agent forwarding:

```bash
docker compose \
  -f docker-compose.dev.yml \
  -f docker-compose.dev.ssh-agent.yml \
  up -d dev
```

- The override file mounts the host agent socket (`$SSH_AUTH_SOCK`) to `/ssh-agent` in the container.
- For GitHub host key trust, run once in the container:

```bash
ssh-keyscan -H github.com >> ~/.ssh/known_hosts
chmod 600 ~/.ssh/known_hosts
```

Using a separate SSH key dedicated to containers is also valid and preferred if your security policy requires strict key separation.

## How to update the image
When dependencies change in `Dockerfile.dev`, `docker-compose.dev.yml`, `pyproject.toml`, or `package.json`:

```bash
docker compose -f docker-compose.dev.yml build --no-cache dev
docker compose -f docker-compose.dev.yml up -d dev
docker compose -f docker-compose.dev.yml exec dev bash -lc 'cd /workspace/godzilla && git pull --ff-only'
docker compose -f docker-compose.dev.yml exec dev bash -lc 'cd /workspace/godzilla && python3 -m pip install -e ".[dev]" && npm install'
```

## Stop and cleanup
Stop the running service:

```bash
docker compose -f docker-compose.dev.yml stop dev
```

Remove the service container:

```bash
docker compose -f docker-compose.dev.yml rm -f dev
```

Remove cached volumes as well (destructive to dependency caches):

```bash
docker compose -f docker-compose.dev.yml down -v
```
