#!/usr/bin/env bash
# Parse the complete function before git pull can update this script.
main() {
# Source layout: shtab/{core,notes,todo}; installed plugin code lives in a Docker volume.
set -Eeuo pipefail
umask 077
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE="$(dirname -- "$ROOT")"
CHECK_ONLY=0
MODE=""
while (($#)); do
  case "$1" in
    --check) CHECK_ONLY=1 ;;
    --vps|--local)
      [[ -z "$MODE" ]] || { echo "Укажите только один режим: --vps или --local" >&2; exit 2; }
      MODE="${1#--}" ;;
    -h|--help)
      echo "Usage: $0 [--local | --vps] [--check]"
      echo "Обновляет core, notes и todo, код плагинов в Docker-томе и контейнеры."
      echo "--vps: infra/compose.vps.yml + infra/vps/.env; недостающие репозитории клонируются."
      echo "--local: infra/docker-compose.yml + infra/.env."
      echo "Без флага режим определяется по существующему .env; при двух .env выберите явно."
      echo "--check: только проверка, без clone, pull, сборки и изменения контейнеров."
      exit 0 ;;
    *) echo "Неизвестный аргумент: $1" >&2; exit 2 ;;
  esac
  shift
done
fail() { echo "Ошибка: $*" >&2; exit 1; }
if [[ -z "$MODE" ]]; then
  if [[ -f "$ROOT/infra/vps/.env" && -f "$ROOT/infra/.env" ]]; then
    fail "Найдены локальный и VPS .env. Укажите --local или --vps."
  elif [[ -f "$ROOT/infra/vps/.env" ]]; then
    MODE=vps
  else
    MODE=local
  fi
fi
if [[ "$MODE" == vps ]]; then
  ENV_FILE="$ROOT/infra/vps/.env"
  COMPOSE_FILE="$ROOT/infra/compose.vps.yml"
else
  ENV_FILE="$ROOT/infra/.env"
  COMPOSE_FILE="$ROOT/infra/docker-compose.yml"
fi
for tool in git docker tar gzip; do
  command -v "$tool" >/dev/null || fail "Не найдена команда $tool"
done
# Check every repo before fetching or changing anything. Never stash/reset automatically.
DIRTY=0
for repo in core notes todo; do
  path="$WORKSPACE/$repo"
  if [[ ! -d "$path/.git" && ! -f "$path/.git" ]]; then
    if [[ "$MODE" == vps && "$repo" != core && ! -e "$path" ]]; then
      echo "$repo: локальная копия отсутствует; при обновлении будет клонирован shtab-project/$repo."
      continue
    fi
    fail "Нет репозитория $path. Установленные плагины находятся в Docker-томе; для VPS используйте --vps."
  fi
  if [[ -n "$(git -C "$path" status --porcelain --untracked-files=all)" ]]; then
    echo "В $path есть незакоммиченные изменения:" >&2
    git -C "$path" status --short >&2
    DIRTY=1
  fi
  git -C "$path" symbolic-ref -q HEAD >/dev/null || fail "$repo: detached HEAD"
  git -C "$path" rev-parse --abbrev-ref '@{upstream}' >/dev/null 2>&1 || fail "$repo: у ветки нет upstream"
done
[[ "$DIRTY" == 0 ]] || fail "Сначала сохраните изменения коммитами. Скрипт ничего не обновил."
[[ -f "$ENV_FILE" ]] || fail "Нет файла $ENV_FILE"
if docker compose version >/dev/null 2>&1; then
  COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null && docker-compose version >/dev/null 2>&1; then
  COMPOSE=(docker-compose)
else
  fail "Не найден Docker Compose (docker compose или docker-compose)"
fi
compose() { "${COMPOSE[@]}" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" "$@"; }
docker info >/dev/null 2>&1 || fail "Docker Engine недоступен. Запустите Docker Desktop или Colima."
compose config --quiet
if [[ "$CHECK_ONLY" == 1 ]]; then
  echo "OK: режим $MODE; существующие репозитории чистые, upstream настроены, Docker и Compose доступны."
  exit 0
fi
BACKUP=""
trap 'echo "Обновление остановлено. Резервная копия: ${BACKUP:-ещё не создана}. Исправьте ошибку перед повторным запуском; контейнеры приложения могут быть остановлены." >&2' ERR
# VPS installs plugins in a volume, so host checkouts may not exist yet.
for repo in notes todo; do
  if [[ ! -e "$WORKSPACE/$repo" ]]; then
    git clone -- "https://github.com/shtab-project/$repo.git" "$WORKSPACE/$repo"
  fi
done
# Fetch all first, so divergence is detected before the first pull.
for repo in core notes todo; do git -C "$WORKSPACE/$repo" fetch; done
for repo in core notes todo; do
  git -C "$WORKSPACE/$repo" merge-base --is-ancestor HEAD '@{upstream}' \
    || fail "$repo: локальная ветка опережает upstream или разошлась с ним. Сначала синхронизируйте её вручную."
done
for repo in core notes todo; do git -C "$WORKSPACE/$repo" pull --ff-only; done
compose config --quiet
compose build core web
compose up -d --wait --wait-timeout 300 postgresql redis server worker
compose run --rm --no-deps -T core .venv/bin/python core/scripts/update_local_plugins.py --check
# Build first; downtime starts only when the images are ready.
compose stop core web
mkdir -p "$ROOT/infra/local-backups"
BACKUP="$(mktemp -d "$ROOT/infra/local-backups/update-$(date +%Y%m%d-%H%M%S)-XXXXXX")"
compose exec -T postgresql sh -eu -c 'pg_dump -U "$POSTGRES_USER" -d shtab' | gzip > "$BACKUP/shtab.sql.gz"
compose run --rm --no-deps -T core tar -cf - -C /app/core/plugins . > "$BACKUP/plugins.tar"
for repo in core notes todo; do git -C "$WORKSPACE/$repo" rev-parse HEAD > "$BACKUP/$repo.commit"; done
STAGING="$(mktemp -d)"
trap 'rm -rf -- "$STAGING"' EXIT
for repo in notes todo; do
  mkdir "$STAGING/$repo"
  git -C "$WORKSPACE/$repo" archive HEAD | tar -xf - -C "$STAGING/$repo"
done
# Transfer via stdin: works with Docker Desktop and Colima without host bind mounts.
tar -cf - -C "$STAGING" notes todo | compose run --rm --no-deps -T core sh -eu -c '
  staging=$(mktemp -d)
  trap '\''rm -rf "$staging"'\'' EXIT
  tar -xf - -C "$staging"
  for plugin in notes todo; do
    test -f "$staging/$plugin/manifest.json"
    test -f "$staging/$plugin/pyproject.toml"
  done
  for plugin in notes todo; do
    rm -rf "/app/core/plugins/$plugin"
    mv "$staging/$plugin" "/app/core/plugins/$plugin"
  done
  uv sync --all-packages --no-dev
  .venv/bin/alembic -c core/alembic.ini upgrade head
  .venv/bin/python core/scripts/update_local_plugins.py
'
compose up -d --force-recreate --wait --wait-timeout 300 core web
compose exec -T core .venv/bin/python core/scripts/check_installation.py
echo "Готово: режим $MODE. Обновите страницу Shtab (Cmd+Shift+R / Ctrl+F5)."
echo "Резервная копия базы и плагинов: $BACKUP"

}
main "$@"
