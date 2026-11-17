#!/usr/bin/env bash
# Parse the complete function before git pull can update this script.
main() {
# Local layout: shtab/{core,notes,todo}. Requires committed changes in all three repos.
set -Eeuo pipefail
umask 077
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE="$(dirname -- "$ROOT")"
CHECK_ONLY=0
case "${1:-}" in
  --check) CHECK_ONLY=1 ;;
  -h|--help)
    echo "Usage: $0 [--check]"
    echo "Обновляет core, ../notes и ../todo; пересобирает локальный Docker."
    echo "--check: только проверка, без pull, сборки и изменения контейнеров."
    exit 0 ;;
  '') ;;
  *) echo "Неизвестный аргумент: $1" >&2; exit 2 ;;
esac
[[ $# -le 1 ]] || { echo "Слишком много аргументов" >&2; exit 2; }
fail() { echo "Ошибка: $*" >&2; exit 1; }
for tool in git docker tar gzip; do
  command -v "$tool" >/dev/null || fail "Не найдена команда $tool"
done
# Check every repo before fetching or changing anything. Never stash/reset automatically.
DIRTY=0
for repo in core notes todo; do
  path="$WORKSPACE/$repo"
  [[ -d "$path/.git" || -f "$path/.git" ]] || fail "Нет репозитория $path"
  if [[ -n "$(git -C "$path" status --porcelain --untracked-files=all)" ]]; then
    echo "В $path есть незакоммиченные изменения:" >&2
    git -C "$path" status --short >&2
    DIRTY=1
  fi
  git -C "$path" symbolic-ref -q HEAD >/dev/null || fail "$repo: detached HEAD"
  git -C "$path" rev-parse --abbrev-ref '@{upstream}' >/dev/null 2>&1 || fail "$repo: у ветки нет upstream"
done
[[ "$DIRTY" == 0 ]] || fail "Сначала сохраните изменения коммитами. Скрипт ничего не обновил."
[[ -f "$ROOT/infra/.env" ]] || fail "Нет infra/.env. Выполните python3 infra/scripts/gen_env.py"
if docker compose version >/dev/null 2>&1; then
  COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null && docker-compose version >/dev/null 2>&1; then
  COMPOSE=(docker-compose)
else
  fail "Не найден Docker Compose (docker compose или docker-compose)"
fi
compose() { "${COMPOSE[@]}" --env-file "$ROOT/infra/.env" -f "$ROOT/infra/docker-compose.yml" "$@"; }
docker info >/dev/null 2>&1 || fail "Docker Engine недоступен. Запустите Docker Desktop или Colima."
compose config --quiet
if [[ "$CHECK_ONLY" == 1 ]]; then
  echo "OK: репозитории чистые, upstream настроены, Docker и Compose доступны."
  exit 0
fi
BACKUP=""
trap 'echo "Обновление остановлено. Резервная копия: ${BACKUP:-ещё не создана}. Исправьте ошибку перед повторным запуском; контейнеры приложения могут быть остановлены." >&2' ERR
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
echo "Готово: http://localhost:3000. Обновите страницу: Cmd+Shift+R."
echo "Резервная копия базы и плагинов: $BACKUP"

}
main "$@"
