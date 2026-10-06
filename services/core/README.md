# Ядро Shtab

FastAPI-сервис: организация, пользователи и роли, вход через Authentik (OIDC).
Работает за Traefik по адресу `http://shtab.localhost/api/…`.

## API (шаг 2)

| Метод | Путь | Кто | Что |
|---|---|---|---|
| GET | `/api/auth/login?next=/…` | все | Редирект на вход в Authentik |
| GET | `/api/auth/callback` | — | Возврат из Authentik → сессия (cookie `shtab_session`) |
| POST | `/api/auth/logout` | вошедший | Удалить сессию; вернуть ссылку выхода из Authentik |
| GET | `/api/setup` | все | Настроен ли Shtab |
| POST | `/api/setup` | вошедший | Первичная настройка: название организации, вызвавший — администратор |
| GET | `/api/me` | вошедший | Профиль и организация |
| GET | `/api/users` | админ | Все пользователи |
| PATCH | `/api/users/{id}` | админ | Роли: `is_admin`, `is_trusted` (последнего админа снять нельзя) |

Swagger: http://shtab.localhost/api/docs

## Как устроен вход

1. `/api/auth/login` → Authentik (Authorization Code + PKCE).
2. Authentik возвращает на `/api/auth/callback` → ядро создаёт / обновляет пользователя по `sub`.
3. Ядро выдаёт свою сессию: случайный id в cookie (HttpOnly, SameSite=Lax, Secure на HTTPS),
   данные — в Redis (хранится хэш id). Выход удаляет сессию в Redis.

Пароли и учётки — только в Authentik. В ядре — профиль и роли (`is_admin`, `is_trusted`).

## Разработка

Ядро запускается в Docker вместе с фундаментом (из папки `infra/`), код подхватывается
на лету (`--reload`):

```bash
cd infra && docker compose up -d --build
```

Тесты — на настоящем PostgreSQL (база `shtab_test`) и Redis; стек должен быть запущен:

```bash
cd services/core && uv run pytest
```

Сквозная проверка входа через настоящий Authentik (создаёт и удаляет временного пользователя,
мастер настройки не трогает):

```bash
cd services/core && uv run python scripts/smoke_login.py
```

Новая миграция после изменения моделей:

```bash
cd services/core && uv run alembic revision --autogenerate -m "что изменилось"
```

> Python на Windows не резолвит `*.localhost` (браузеры — резолвят). Поэтому ядро
> работает в Docker, а smoke-скрипт сам направляет `*.localhost` на 127.0.0.1.
