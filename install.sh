#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${OPENINSTINCT_REPO_URL:-https://github.com/samagra14/openinstinct.git}"
REPO_BRANCH="${OPENINSTINCT_REPO_BRANCH:-main}"
SOURCE_DIR="${OPENINSTINCT_SOURCE_DIR:-$HOME/.openinstinct/source}"
BRIDGE_DIR="${OPENINSTINCT_BRIDGE_DIR:-$HOME/.openinstinct/bridge}"
CODEX_HOME_DIR="${OPENINSTINCT_CODEX_HOME:-$HOME/.openinstinct/codex}"
STATE_DIR="${OPENINSTINCT_STATE_DIR:-$HOME/.openinstinct/state}"
PROJECT_DIR="${OPENINSTINCT_PROJECT_DIR:-$HOME/openinstinct-workspace}"
BIN_DIR="${OPENINSTINCT_BIN_DIR:-$HOME/.local/bin}"
ENV_FILE="$STATE_DIR/.env"
UPSTREAM_REPO="https://github.com/inkbox-ai/codex-plugin.git"
UPSTREAM_COMMIT="339d702b99eb8e50b4434f7ddb7e412047e94fb1"
MAIN_MODEL="${OPENINSTINCT_MAIN_MODEL:-gpt-5.6-sol}"
AGENT_BROWSER_VERSION="0.35.1"
UV_VERSION="0.12.5"
SKIP_LOGIN=0
SKIP_SETUP=0
ORIGINAL_ARGS=("$@")

while [ "$#" -gt 0 ]; do
  case "$1" in
    --skip-login) SKIP_LOGIN=1 ;;
    --skip-setup) SKIP_SETUP=1 ;;
    --project-dir) shift; PROJECT_DIR="${1:-}" ;;
    -h|--help)
      echo "Usage: install.sh [--skip-login] [--skip-setup] [--project-dir PATH]"
      exit 0
      ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
  shift
done

say() { echo; echo "==> $*"; }
ok() { echo "    $*"; }
die() { echo "Error: $*" >&2; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-}")" 2>/dev/null && pwd || true)"
if [ ! -f "$SCRIPT_DIR/config/AGENTS.md" ]; then
  say "Downloading OpenInstinct"
  command -v git >/dev/null 2>&1 || die "git is required"
  if [ -d "$SOURCE_DIR/.git" ]; then
    git -C "$SOURCE_DIR" fetch --quiet origin "$REPO_BRANCH"
    git -C "$SOURCE_DIR" checkout --quiet "$REPO_BRANCH"
    git -C "$SOURCE_DIR" pull --ff-only --quiet
  elif [ -e "$SOURCE_DIR" ]; then
    die "$SOURCE_DIR exists but is not an OpenInstinct checkout"
  else
    mkdir -p "$(dirname "$SOURCE_DIR")"
    git clone --quiet --branch "$REPO_BRANCH" "$REPO_URL" "$SOURCE_DIR"
  fi
  exec "$SOURCE_DIR/install.sh" "${ORIGINAL_ARGS[@]}"
fi

mkdir -p "$BIN_DIR"
export PATH="$BIN_DIR:$HOME/.local/bin:$PATH"

find_python() {
  local candidate version major minor
  for candidate in python3.13 python3.12 python3.11 python3 python; do
    command -v "$candidate" >/dev/null 2>&1 || continue
    version="$($candidate -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || true)"
    major="${version%.*}"
    minor="${version#*.}"
    if [ "$major" = "3" ] && [ "$minor" -ge 11 ] 2>/dev/null; then
      command -v "$candidate"
      return 0
    fi
  done
  return 1
}

install_managed_python() {
  say "Installing Python"
  if ! command -v uv >/dev/null 2>&1; then
    curl -LsSf "https://astral.sh/uv/$UV_VERSION/install.sh" | \
      env UV_UNMANAGED_INSTALL="$BIN_DIR" sh
  fi
  uv python install 3.12
  export PATH="$BIN_DIR:$HOME/.local/bin:$PATH"
}

sha256_file() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$1" | awk '{print $1}'
  else
    die "A SHA-256 tool is required to verify the browser download"
  fi
}

agent_browser_asset() {
  local platform machine
  platform="$(uname -s)"
  machine="$(uname -m)"
  case "$platform/$machine" in
    Darwin/arm64)
      echo "agent-browser-darwin-arm64|12be3313ec6d878d8fda62ca5c62b7013c1b6931bf57dd2678788654b01ffe95"
      ;;
    Darwin/x86_64)
      echo "agent-browser-darwin-x64|6cafdc32d0cccbd892310adb7a36d7cd97807ab684338664fc08c7fdfeb2fef2"
      ;;
    Linux/aarch64|Linux/arm64)
      die "Linux ARM VMs cannot use agent-browser's bundled Chrome. Use an x86_64 Ubuntu VM."
      ;;
    Linux/x86_64|Linux/amd64)
      echo "agent-browser-linux-x64|21874b7afbe12a225d01c7f3f7d635c2c2f740660f6ef5e7916737c60c4f1faf"
      ;;
    *)
      die "agent-browser does not publish a binary for $platform/$machine"
      ;;
  esac
}

install_agent_browser() {
  local metadata asset expected actual temporary current_version
  current_version="$(agent-browser --version 2>/dev/null | awk '{print $2}' || true)"
  if [ "$current_version" = "$AGENT_BROWSER_VERSION" ]; then
    ok "agent-browser $current_version"
  else
    metadata="$(agent_browser_asset)"
    asset="${metadata%%|*}"
    expected="${metadata#*|}"
    temporary="$(mktemp "${TMPDIR:-/tmp}/openinstinct-agent-browser.XXXXXX")"
    if ! curl -fsSL \
      "https://github.com/vercel-labs/agent-browser/releases/download/v$AGENT_BROWSER_VERSION/$asset" \
      -o "$temporary"; then
      rm -f "$temporary"
      die "Could not download agent-browser"
    fi
    actual="$(sha256_file "$temporary")"
    if [ "$actual" != "$expected" ]; then
      rm -f "$temporary"
      die "agent-browser download failed its integrity check"
    fi
    install -m 0755 "$temporary" "$BIN_DIR/agent-browser"
    rm -f "$temporary"
    hash -r
    ok "agent-browser $AGENT_BROWSER_VERSION"
  fi

  if [ "$(uname -s)" = "Linux" ]; then
    agent-browser install --with-deps
  else
    agent-browser install
  fi
}

verify_agent_browser() {
  local session profile title stored
  session="openinstinct-install-check-$$"
  profile="$(mktemp -d "${TMPDIR:-/tmp}/openinstinct-browser-profile.XXXXXX")"
  if ! agent-browser doctor --offline --quick >/dev/null; then
    rm -rf "$profile"
    die "agent-browser is installed but its browser runtime is not healthy"
  fi
  if ! agent-browser --session "$session" --profile "$profile" \
    open https://example.com >/dev/null; then
    rm -rf "$profile"
    die "agent-browser could not open a test page"
  fi
  if ! title="$(agent-browser --session "$session" get title)"; then
    agent-browser --session "$session" close >/dev/null 2>&1 || true
    rm -rf "$profile"
    die "agent-browser could not read the test page"
  fi
  if ! agent-browser --session "$session" --profile "$profile" \
    eval "localStorage.setItem('openinstinct_install_check', 'persisted')" >/dev/null; then
    agent-browser --session "$session" close >/dev/null 2>&1 || true
    rm -rf "$profile"
    die "agent-browser could not save browser state"
  fi
  agent-browser --session "$session" close >/dev/null 2>&1 || true
  if ! agent-browser --session "${session}-resume" --profile "$profile" \
    open https://example.com >/dev/null; then
    rm -rf "$profile"
    die "agent-browser could not reopen its persistent profile"
  fi
  if ! stored="$(agent-browser --session "${session}-resume" --profile "$profile" \
    eval "localStorage.getItem('openinstinct_install_check')")"; then
    agent-browser --session "${session}-resume" close >/dev/null 2>&1 || true
    rm -rf "$profile"
    die "agent-browser could not restore browser state"
  fi
  agent-browser --session "${session}-resume" close >/dev/null 2>&1 || true
  rm -rf "$profile"
  [ "$title" = "Example Domain" ] || die "agent-browser returned an unexpected test page"
  [ "$stored" = '"persisted"' ] || die "agent-browser did not preserve browser state"
  ok "Browser opened a live page and preserved state across a restart"
}

say "Checking dependencies"
if ! command -v curl >/dev/null 2>&1 || ! command -v git >/dev/null 2>&1; then
  if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update
    sudo apt-get install -y ca-certificates curl git
  else
    die "Install curl and git, then rerun"
  fi
fi
if ! find_python >/dev/null 2>&1; then
  if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update
    sudo apt-get install -y python3 python3-venv
  elif [ "$(uname -s)" = "Darwin" ]; then
    install_managed_python
  else
    die "Python 3.11 or newer is required"
  fi
fi
PYTHON="$(find_python)" || die "Python 3.11 or newer is required. Ubuntu 24.04 is recommended."
ok "$($PYTHON --version)"

say "Installing Codex"
if ! command -v codex >/dev/null 2>&1; then
  curl -fsSL https://chatgpt.com/codex/install.sh | sh
  export PATH="$BIN_DIR:$HOME/.local/bin:$PATH"
fi
command -v codex >/dev/null 2>&1 || die "Codex installation did not add the CLI to PATH"
ok "$(codex --version)"

mkdir -p "$CODEX_HOME_DIR" "$STATE_DIR" "$PROJECT_DIR" "$BIN_DIR"
"$PYTHON" "$SCRIPT_DIR/scripts/configure.py" \
  --source "$SCRIPT_DIR" \
  --codex-home "$CODEX_HOME_DIR" \
  --project-dir "$PROJECT_DIR" \
  --env-file "$ENV_FILE" \
  --model "$MAIN_MODEL"

say "Installing the real browser"
install_agent_browser
verify_agent_browser

if [ "$SKIP_LOGIN" = "0" ]; then
  if CODEX_HOME="$CODEX_HOME_DIR" codex login status >/dev/null 2>&1; then
    ok "Codex is signed in"
  else
    say "Sign in to Codex"
    CODEX_HOME="$CODEX_HOME_DIR" codex login --device-auth
  fi
fi

say "Installing the messaging bridge"
if [ ! -d "$BRIDGE_DIR/.git" ]; then
  if [ -e "$BRIDGE_DIR" ]; then
    die "$BRIDGE_DIR exists but is not the expected bridge checkout"
  fi
  git clone --quiet "$UPSTREAM_REPO" "$BRIDGE_DIR"
  git -C "$BRIDGE_DIR" checkout --quiet --detach "$UPSTREAM_COMMIT"
else
  current_commit="$(git -C "$BRIDGE_DIR" rev-parse HEAD)"
  if [ "$current_commit" != "$UPSTREAM_COMMIT" ]; then
    die "Bridge checkout is not on the tested revision. Move it aside and rerun."
  fi
fi

"$PYTHON" "$SCRIPT_DIR/scripts/patch_bridge.py" "$BRIDGE_DIR"
"$PYTHON" "$SCRIPT_DIR/scripts/verify_overlay.py" "$BRIDGE_DIR"

if [ ! -x "$BRIDGE_DIR/.venv/bin/python" ]; then
  "$PYTHON" -m venv "$BRIDGE_DIR/.venv"
fi
"$BRIDGE_DIR/.venv/bin/python" -m pip install --quiet --upgrade pip
"$BRIDGE_DIR/.venv/bin/pip" install --quiet -e "$BRIDGE_DIR"
ln -sfn "$BRIDGE_DIR/.venv/bin/inkbox-codex" "$BIN_DIR/inkbox-codex"
ok "Bridge installed"

if [ "$SKIP_SETUP" = "0" ] && ! grep -q '^INKBOX_API_KEY=' "$ENV_FILE" 2>/dev/null; then
  if [ -n "${INKBOX_API_KEY:-}" ] && [ -n "${INKBOX_IDENTITY:-}" ]; then
    say "Connecting the Inkbox identity"
    printf '%s\n' "$INKBOX_API_KEY" | CODEX_HOME="$CODEX_HOME_DIR" INKBOX_CODEX_ENV_FILE="$ENV_FILE" \
      "$BIN_DIR/inkbox-codex" bootstrap --api-key-stdin --identity "$INKBOX_IDENTITY" \
      --project-dir "$PROJECT_DIR"
  else
    say "Create or connect the Inkbox identity"
    if [ ! -e /dev/tty ]; then
      die "A terminal is required for first-time Inkbox setup"
    fi
    CODEX_HOME="$CODEX_HOME_DIR" INKBOX_CODEX_ENV_FILE="$ENV_FILE" \
      "$BIN_DIR/inkbox-codex" setup < /dev/tty
  fi
fi

SERVICE_FILE="$HOME/.config/systemd/user/openinstinct.service"
"$PYTHON" "$SCRIPT_DIR/scripts/configure.py" \
  --source "$SCRIPT_DIR" \
  --codex-home "$CODEX_HOME_DIR" \
  --project-dir "$PROJECT_DIR" \
  --env-file "$ENV_FILE" \
  --model "$MAIN_MODEL" \
  --service-file "$SERVICE_FILE" \
  --bridge-bin "$BIN_DIR/inkbox-codex"

if command -v systemctl >/dev/null 2>&1; then
  say "Starting OpenInstinct"
  CODEX_HOME="$CODEX_HOME_DIR" INKBOX_CODEX_ENV_FILE="$ENV_FILE" \
    "$BIN_DIR/inkbox-codex" stop >/dev/null 2>&1 || true
  systemctl --user disable --now inkbox-codex.service >/dev/null 2>&1 || true
  systemctl --user daemon-reload
  systemctl --user enable --now openinstinct.service
  if command -v loginctl >/dev/null 2>&1 && sudo -n true >/dev/null 2>&1; then
    sudo loginctl enable-linger "$USER"
  else
    ok "To keep it alive after logout, run: sudo loginctl enable-linger $USER"
  fi
else
  say "Starting OpenInstinct"
  CODEX_HOME="$CODEX_HOME_DIR" INKBOX_CODEX_ENV_FILE="$ENV_FILE" "$BIN_DIR/inkbox-codex" restart >/dev/null 2>&1 || \
    CODEX_HOME="$CODEX_HOME_DIR" INKBOX_CODEX_ENV_FILE="$ENV_FILE" "$BIN_DIR/inkbox-codex" start
fi

say "Checking the setup"
if ! CODEX_HOME="$CODEX_HOME_DIR" INKBOX_CODEX_ENV_FILE="$ENV_FILE" \
  "$BIN_DIR/inkbox-codex" doctor; then
  die "OpenInstinct did not pass its final health check"
fi

echo
echo "OpenInstinct is ready."
echo "Text START to the agent number, then send a normal request."
echo "Workspace: $PROJECT_DIR"
