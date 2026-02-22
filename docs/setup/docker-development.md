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
docker compose -f docker-compose.dev.yml exec dev bash -lc 'cd /workspace/godzilla && godzilla-api --host 0.0.0.0 --port 8787'
```

## VS Code connection to the running image
1. Start the container with `docker compose -f docker-compose.dev.yml up -d dev`.
2. In VS Code, run `Dev Containers: Attach to Running Container...`.
3. Select the running container for this project.
4. Open `/workspace/godzilla` inside the attached session.

The `.devcontainer/devcontainer.json` file is configured for the same service, but this pure named-volume workflow expects the repository content inside `/workspace/godzilla`.
If that command is missing, install the Dev Containers extension (`ms-vscode-remote.remote-containers`) in the host VS Code and reload.

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
