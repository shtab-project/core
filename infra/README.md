# Локальное окружение

Из корня репозитория сгенерируйте `infra/.env` и запустите Docker Compose.

```bash
python infra/scripts/gen_env.py
docker compose -f infra/docker-compose.yml up -d --build
```

[Shtab](http://localhost:3000) · [Authentik](http://auth.shtab.localhost:9000/if/admin/).

Вход администратора Authentik использует имя `akadmin` и пароль `AUTHENTIK_BOOTSTRAP_PASSWORD` из `infra/.env`. PostgreSQL, Redis и установленные плагины хранятся в томах Docker.

## Обновление локальной установки

Разместите репозитории рядом: `shtab/core`, `shtab/notes`, `shtab/todo`.
Плагины notes и todo должны быть уже установлены через интерфейс Shtab.
Сохраните локальные изменения коммитами и отправьте их в upstream-ветки.

```bash
cd /Users/admin/projects/shtab/core
./update-local.sh --check
./update-local.sh
```

Скрипт поддерживает `docker compose` и `docker-compose`. Проверяет все три
репозитория, выполняет `fetch` и `pull --ff-only`, собирает core/web и переносит
исходники notes/todo в Docker-том. Выполняет миграции ядра и плагинов,
обновляет сведения об установленных плагинах и проверяет API/OIDC.
Изменения для других установленных плагинов он не переносит.

Во время переноса приложение останавливается. Перед изменением Docker-тома
создаются `infra/local-backups/update-*/shtab.sql.gz` и `plugins.tar`.
При ошибке скрипт останавливается; автоматический откат миграций не выполняется.
Файлы установленного плагина заменяются снимком коммита из локального репозитория;
редактируйте исходники в соседних репозиториях, а не внутри контейнера.
`--check` не обновляет репозитории и не меняет контейнеры.
