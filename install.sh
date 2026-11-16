#!/usr/bin/env bash
# VPS installer for Ubuntu/Debian, using a public IPv4 address.
set -Eeuo pipefail
umask 077

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
HOST=""
PORT=80
AUTH_PORT=9000
CONFIGURE_ONLY=0
usage() {
  echo "Usage: sudo bash install.sh --host SERVER_IP [--port 80] [--auth-port 9000] [--configure-only]"
}
while (($#)); do
  case "$1" in
    --host|--port|--auth-port)
      (($# >= 2)) || { usage; exit 2; }
      case "$1" in --host) HOST="$2";; --port) PORT="$2";; --auth-port) AUTH_PORT="$2";; esac
      shift 2 ;;
    --configure-only) CONFIGURE_ONLY=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) usage; exit 2 ;;
  esac
done
[[ -n "$HOST" ]] || { usage; exit 2; }
[[ "$(uname -s)" == Linux ]] || { echo "Run this installer on the Linux VPS." >&2; exit 1; }
[[ "$EUID" == 0 || "$CONFIGURE_ONLY" == 1 ]] || { echo "Run with sudo." >&2; exit 1; }

if ! command -v python3 >/dev/null; then
  [[ "$EUID" == 0 ]] || { echo "python3 is required." >&2; exit 1; }
  apt-get update
  apt-get install -y python3
fi
python3 "$ROOT/infra/scripts/configure_vps.py" --host "$HOST" --port "$PORT" --auth-port "$AUTH_PORT"
[[ "$CONFIGURE_ONLY" == 0 ]] || exit 0

if ! command -v docker >/dev/null; then
  # Install from Docker's signed apt repository; never replace an existing engine.
  source /etc/os-release
  case "$ID" in ubuntu|debian) ;; *) echo "Docker auto-install supports Ubuntu/Debian only." >&2; exit 1;; esac
  CODENAME="${UBUNTU_CODENAME:-${VERSION_CODENAME:-}}"
  [[ "$CODENAME" =~ ^[a-z]+$ ]] || { echo "Unknown distribution codename." >&2; exit 1; }
  apt-get update
  apt-get install -y ca-certificates curl
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL "https://download.docker.com/linux/$ID/gpg" -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  cat > /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/$ID
Suites: $CODENAME
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
  apt-get update
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  systemctl enable --now docker
fi
docker info >/dev/null
docker compose version >/dev/null || { echo "Docker Compose v2 is required." >&2; exit 1; }
cd "$ROOT"
compose() { docker compose --env-file "$ROOT/infra/vps/.env" -f "$ROOT/infra/compose.vps.yml" "$@"; }
trap 'echo "Installation failed. Config and data are preserved. Check: sudo docker compose --env-file infra/vps/.env -f infra/compose.vps.yml logs --tail=60" >&2' ERR

compose config --quiet
compose build core web
compose up -d --wait --wait-timeout 600 postgresql redis server worker
# Fresh Authentik queues its default flows after migrations. Our provider must wait for them.
oidc_ready() {
  python3 - "$AUTH_PORT" <<'PY'
import sys
from urllib.request import urlopen
try:
    with urlopen('http://127.0.0.1:' + sys.argv[1] + '/application/o/shtab/.well-known/openid-configuration', timeout=5):
        pass
except OSError:
    sys.exit(1)
PY
}
OIDC_READY=0
for attempt in {1..30}; do
  if compose exec -T worker ak apply_blueprint /blueprints/shtab/shtab.yaml > "$ROOT/infra/vps/blueprint.log" 2>&1 && oidc_ready; then
    OIDC_READY=1
    break
  fi
  sleep 3
done
if [[ "$OIDC_READY" != 1 ]]; then
  tail -n 40 "$ROOT/infra/vps/blueprint.log" >&2
  echo "Authentik provider is not ready; see infra/vps/blueprint.log." >&2
  exit 1
fi
# Stop only this installation's app before changing its plugin environment.
compose stop core web
compose run --rm --no-deps bootstrap
compose up -d --wait --wait-timeout 300 core web
compose exec -T core .venv/bin/python core/scripts/check_installation.py
echo "Ready. Open http://$HOST:$PORT and complete organization setup."
echo "Login: akadmin. Password: $ROOT/infra/vps/credentials.txt (root only)."
echo "HTTP mode: credentials and content are not encrypted. Add a domain and HTTPS before regular use."
