# Docker Development Environment (Linux MVP)

Requirements: TECH-SEC-DATA-004

## What the image includes
`Dockerfile.dev` provides the development toolchain:
- Python 3.12 + `pip`/`setuptools`/`wheel`/`nox`
- Node.js 24 LTS + npm 11
- Rust stable (`rustc`, `cargo`, `rustup`)
- Git + OpenSSH client + Linux build prerequisites for this project
- Desktop session helpers for native GTK/Tauri dialogs (`dbus-x11`, `at-spi2-core`)

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
- Running SSH agent with your Git key loaded (`SSH_AUTH_SOCK` exported)
- Host Claude credentials under `~/.claude` (or set `ANTHROPIC_API_KEY`)

## Compose command set (includes all overlays)
Use the same compose file set for all lifecycle commands:

```bash
export COMPOSE_DEV='docker compose -f docker-compose.dev.yml -f docker-compose.dev.ssh-agent.yml -f docker-compose.dev.claude.yml'
```

For GUI/Tauri work on a Linux desktop session, include the GUI overlay:

```bash
export COMPOSE_DEV_GUI='docker compose -f docker-compose.dev.yml -f docker-compose.dev.ssh-agent.yml -f docker-compose.dev.claude.yml -f docker-compose.dev.gui.yml'
```

## Installation and first build
From the repository root:

```bash
export COMPOSE_DEV='docker compose -f docker-compose.dev.yml -f docker-compose.dev.ssh-agent.yml -f docker-compose.dev.claude.yml'
export GODZILLA_REPO_URL=$(git remote get-url origin)
$COMPOSE_DEV build dev
$COMPOSE_DEV up -d dev
$COMPOSE_DEV exec dev git clone $GODZILLA_REPO_URL /workspace/godzilla
$COMPOSE_DEV exec dev bash -lc 'cd /workspace/godzilla && python3 -m venv venv && . venv/bin/activate && pip install -e ".[dev]"'
$COMPOSE_DEV exec dev bash -lc 'cd /workspace/godzilla/ui && npm install'
```

## Run and use locally
Start or restart the development container:

```bash
$COMPOSE_DEV up -d dev
```

Open an interactive shell:

```bash
$COMPOSE_DEV exec dev bash
```
```bash
docker exec -it godzilla-dev bash
```

## Run Tauri GUI from container (Linux X11)
This mode requires a local Linux desktop with an active X server. It will not work in headless-only environments.

The GUI compose overlay defaults to an X11 path (`GDK_BACKEND=x11`) while keeping
hardware acceleration available for better responsiveness.

The dev image includes DBus session support (`dbus-x11`) and accessibility bus
runtime (`at-spi2-core`) because native Linux file dialogs used by Tauri plugins
can render incorrectly or emit `dconf` / `dbus-launch` errors when those pieces
are missing in a containerized desktop session.

The GUI overlay also forwards the host Xauthority cookie into the container so
GTK can authenticate to the host X server. Without `XAUTHORITY`, Tauri may
panic during startup with `Failed to initialize GTK` even when `DISPLAY` and the
X11 socket mount are present.

Allow local Docker X11 clients from the host:

```bash
xhost +local:docker
```

If your host shell does not already export `XAUTHORITY`, set it explicitly
before starting the GUI overlay:

```bash
export XAUTHORITY="${XAUTHORITY:-$HOME/.Xauthority}"
```

Start container with GUI overlay:

```bash
$COMPOSE_DEV_GUI up -d dev
```

If your host has display/GPU instability, enable compatibility mode and recreate
the container:

```bash
export GODZILLA_GUI_SOFTWARE_RENDERING=1
export GODZILLA_GUI_DISABLE_COMPOSITING=1
$COMPOSE_DEV_GUI up -d --force-recreate dev
```

Run Tauri app inside the container:

```bash
$COMPOSE_DEV_GUI exec dev bash -lc 'source /usr/local/cargo/env && cd /workspace/godzilla/ui && npm run tauri dev'
```

If GTK still fails to initialize, verify the forwarded GUI environment inside
the container:

```bash
$COMPOSE_DEV_GUI exec dev bash -lc 'echo DISPLAY=$DISPLAY; echo XAUTHORITY=$XAUTHORITY; ls -l /tmp/.X11-unix; ls -l ${XAUTHORITY:-$HOME/.Xauthority}'
```

If you need to suppress accessibility bus noise in a minimal container session,
set `NO_AT_BRIDGE=1` for that shell:

```bash
$COMPOSE_DEV_GUI exec dev bash -lc 'source /usr/local/cargo/env && cd /workspace/godzilla/ui && NO_AT_BRIDGE=1 npm run tauri dev'
```

If you run Tauri outside the GUI overlay and see a crash like
`Gdk-Message: Error reading events from display: Connection reset by peer`,
retry with:

```bash
source /usr/local/cargo/env && GDK_BACKEND=x11 LIBGL_ALWAYS_SOFTWARE=1 WEBKIT_DISABLE_COMPOSITING_MODE=1 npm run tauri dev
```

After you are done, revoke X11 access:

```bash
xhost -local:docker
```

Run quality checks inside the container:

```bash
$COMPOSE_DEV exec dev bash -lc 'cd /workspace/godzilla && . venv/bin/activate && nox -s lint'
$COMPOSE_DEV exec dev bash -lc 'cd /workspace/godzilla && . venv/bin/activate && nox -s tests'
$COMPOSE_DEV exec dev bash -lc 'cd /workspace/godzilla && . venv/bin/activate && nox -s build'
$COMPOSE_DEV exec dev bash -lc 'cd /workspace/godzilla && . venv/bin/activate && nox -s security'
```

Run the API server from inside the container (example):

```bash
$COMPOSE_DEV exec dev bash -lc 'cd /workspace/godzilla && . venv/bin/activate && godzilla-api --host 127.0.0.1 --port 8787'
```

Run the browser UI (Vite) and open it from the host:

```bash
$COMPOSE_DEV exec dev bash -lc 'cd /workspace/godzilla/ui && npm install && npm run dev -- --host 0.0.0.0 --port 8443 --strictPort'
```

Then open `http://localhost:8443`.
In this mode, Vite proxies `/api/*` to the sidecar and injects `X-API-Key`
from container env `GODZILLA_API_TOKEN` on the server side.

## VS Code connection to the running image
1. Start the container with `$COMPOSE_DEV up -d dev`.
2. In VS Code, run `Dev Containers: Attach to Running Container...`.
3. Select the running container for this project.
4. Open `/workspace/godzilla` inside the attached session.

If that command is missing, install extension `ms-vscode-remote.remote-containers` and reload VS Code.

## Git and network access
- The image includes Git and OpenSSH client tooling.
- Outbound network access is provided by Docker's default bridge networking.
- Git over HTTPS works out of the box once credentials are configured in the container.
- For SSH-based Git remotes, do not copy private keys into the container.
- SSH forwarding is provided by `docker-compose.dev.ssh-agent.yml` and Claude auth by `docker-compose.dev.claude.yml`.
- For GitHub host key trust, run once in the container:

```bash
ssh-keyscan -H github.com >> ~/.ssh/known_hosts
chmod 600 ~/.ssh/known_hosts
```

Using a separate SSH key dedicated to containers is valid if your policy requires strict key separation.

## How to update the image
When dependencies change in `Dockerfile.dev`, compose files, `pyproject.toml`, or `package.json`:

```bash
$COMPOSE_DEV build --no-cache dev
$COMPOSE_DEV up -d dev
$COMPOSE_DEV exec dev bash -lc 'cd /workspace/godzilla && git pull --ff-only'
$COMPOSE_DEV exec dev bash -lc 'cd /workspace/godzilla && python3 -m venv venv && . venv/bin/activate && pip install -e ".[dev]"'
$COMPOSE_DEV exec dev bash -lc 'cd /workspace/godzilla/ui && npm install'
```

## Stop and cleanup
Stop containers:

```bash
$COMPOSE_DEV stop dev
```

Remove stopped containers:

```bash
$COMPOSE_DEV rm -f dev
```

Remove containers and local compose image tags:

```bash
$COMPOSE_DEV down --rmi local
```

Remove containers, images, and volumes (destructive to workspace/data caches):

```bash
$COMPOSE_DEV down --rmi local -v
```

# Run API Server on host 
```bash
set -a
source .godenv
set +a
python3 -m venv venv 
. venv/bin/activate
pip install -e ".[dev]"
godzilla-api --host 127.0.0.1 --port 8787
```

# Run Browser UI (Vite) on host
# Terminal 2 (UI)
```bash
set -a
source ../.godenv
set +a
npm install
npm run dev -- --host 127.0.0.1 --port 8443 --strictPort
```
