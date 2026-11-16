# Shtab

Коротко: [контракт плагина](PLUGIN_CONTRACT.md) · [ближайшие задачи](TODO.md).

Своя рабочая экосистема организации на своём сервере. **Ядро** хранит организацию,
аккаунты, проекты и маркет плагинов. Всё остальное — **плагины**, которые ставятся
из маркета: задачи, заметки, позже мессенджер, мониторинг и интеграции.
ИИ-помощник (ChatGPT / Claude) работает с системой через MCP.

Подробно об архитектуре и принятых решениях — в [docs/PLAN.md](docs/PLAN.md).

```
              Браузер / телефон / ChatGPT / Claude
                              │
                Nginx + Authentik (вход, OIDC)
                              │
 ┌─────────────────────────── ЯДРО ───────────────────────────┐
 │ Организация · Пользователи и роли · Проекты · Маркет · MCP │
 └────────┬────────────────────────────────────────▲──────────┘
  вебхуки │                                REST API │
          ▼                                         │
     📋 Задачи        📝 Заметки        … другие плагины (у каждого своя БД)
```

## Состояние

| Шаг | Что | |
|---|---|---|
| 1 | Локальный фундамент: Nginx, PostgreSQL, Redis, Authentik (настройка blueprint'ом) | ✅ |
| 2 | Ядро: вход через Authentik (OIDC + PKCE), мастер первого запуска, пользователи и роли | ✅ |
| 3 | Веб-интерфейс ядра, каталог GitHub-плагинов и MCP-шлюз | ✅ |

## Структура

```
infra/            Docker Compose, Authentik blueprint, генератор секретов
core/             ядро: FastAPI, SQLAlchemy, Alembic
core/plugins/     установленные плагины (участники workspace)
web/              фронт ядра (React)
```

Python-сервисы — один uv-workspace с общим `uv.lock` (корневой `pyproject.toml`).
Плагины устанавливаются из каталога Shtab. Исходники находятся в отдельных репозиториях организации [shtab-project](https://github.com/shtab-project).

## Запуск локально

Для VPS по IP: [установщик и инструкция](docs/VPS-INSTALL.md).

Нужны Docker Desktop (WSL2) и [uv](https://docs.astral.sh/uv/).

Сгенерировать `infra/.env` со случайными секретами:

```bash
python infra/scripts/gen_env.py
```

Запустить сервисы из корня репозитория:

```bash
docker compose -f infra/docker-compose.yml up -d --build
```

Откройте [Shtab](http://localhost:3000). Для первого запуска используйте учётку `akadmin` с паролем `AUTHENTIK_BOOTSTRAP_PASSWORD` из `infra/.env` и создайте организацию. Затем откройте «Плагины» в боковом меню.

[Админка Authentik](http://auth.shtab.localhost:9000/if/admin/) · [Swagger](http://localhost:3000/api/docs).

## Тесты

```bash
uv run --package shtab-core pytest --confcutdir=core/tests/unit core/tests/unit
```

Для сквозной проверки входа на запущенном стеке используйте `uv run --package shtab-core python core/scripts/smoke_login.py`.
