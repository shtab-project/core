# Shtab

Своя рабочая экосистема организации на своём сервере. **Ядро** хранит организацию,
аккаунты, проекты и маркет плагинов. Всё остальное — **плагины**, которые ставятся
из маркета: задачи, заметки, позже мессенджер, мониторинг и интеграции.
ИИ-помощник (ChatGPT / Claude) работает с системой через MCP.

Подробно об архитектуре и принятых решениях — в [docs/PLAN.md](docs/PLAN.md).

```
              Браузер / телефон / ChatGPT / Claude
                              │
                Traefik + Authentik (вход, OIDC)
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
| 1 | Локальный фундамент: Traefik, PostgreSQL, Redis, Authentik (настройка blueprint'ом) | ✅ |
| 2 | Ядро: вход через Authentik (OIDC + PKCE), мастер первого запуска, пользователи и роли | ✅ |
| 3 | Веб-интерфейс ядра (Vite + React) | |
| — | Проекты, контракт плагина, плагин «Задачи», MCP-шлюз, заметки, маркет | |

## Структура

```
infra/            Docker Compose, Authentik blueprint, генератор секретов
services/core/    ядро: FastAPI, SQLAlchemy, Alembic
web/              фронт ядра (ещё не начат)
docs/             план
```

Python-сервисы — один uv-workspace с общим `uv.lock` (корневой `pyproject.toml`).
Плагины пока будут жить здесь же, позже каждый уедет в свой репозиторий.

## Запуск локально

Нужны Docker Desktop (WSL2) и [uv](https://docs.astral.sh/uv/).

Сгенерировать `infra/.env` со случайными секретами:

```bash
python infra/scripts/gen_env.py
```

Поднять фундамент и ядро:

```bash
cd infra && docker compose up -d --build
```

Через минуту, когда Authentik готов:

| Адрес | Что |
|---|---|
| http://shtab.localhost/api/docs | API ядра (Swagger) |
| http://shtab.localhost/api/auth/login | Вход в Shtab |
| http://auth.shtab.localhost/if/admin/ | Админка Authentik (`akadmin`, пароль из `infra/.env`) |
| http://traefik.shtab.localhost | Панель Traefik |

Первый вход: войти через `/api/auth/login`, затем в Swagger выполнить `POST /api/setup`
с названием организации — вошедший станет администратором.

Подробнее — [infra/README.md](infra/README.md) и [services/core/README.md](services/core/README.md).

## Тесты

Только на настоящем PostgreSQL и Redis (стек должен быть запущен):

```bash
cd services/core && uv run pytest
```

Сквозная проверка входа через Authentik:

```bash
cd services/core && uv run python scripts/smoke_login.py
```
