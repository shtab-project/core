# Инфраструктура Shtab

Фундамент, на котором живут ядро и плагины: Traefik, PostgreSQL, Redis, Authentik — и само ядро.

| Сервис | Адрес (локально) | Зачем |
|---|---|---|
| Ядро | http://shtab.localhost/api/docs | API Shtab (см. [services/core](../services/core/README.md)) |
| Traefik | http://traefik.shtab.localhost | Прокси: маршруты по доменам, позже — HTTPS |
| Authentik | http://auth.shtab.localhost | Вход, аккаунты, приглашения, OIDC |
| PostgreSQL | `127.0.0.1:5432` | БД `authentik`, `shtab`, `shtab_test` (+ по одной на каждый плагин) |
| Redis | `127.0.0.1:6379` | Очереди taskiq, кэш |

## Первый запуск

```bash
python infra/scripts/gen_env.py
```

```bash
cd infra && docker compose up -d --build
```

Из папки `infra/` без `-f` автоматически подключается `compose.override.yml` — режим
разработки (код ядра монтируется и перезагружается на лету). На сервере — только
`docker compose -f compose.yml up -d`.

`gen_env.py` можно запускать повторно: он только дописывает недостающие ключи.

Authentik готов примерно через минуту. Проверка:
`http://auth.shtab.localhost/-/health/ready/` отвечает `200`.

## Вход в админку Authentik

- Адрес: http://auth.shtab.localhost/if/admin/
- Логин: `akadmin`
- Пароль: `AUTHENTIK_BOOTSTRAP_PASSWORD` из `infra/.env`

## Что настроено автоматически

Файл [authentik/blueprints/shtab.yaml](authentik/blueprints/shtab.yaml) применяется
Authentik при старте и при каждом изменении файла:

- **Регистрация только по приглашению** — поток `shtab-invitation-enrollment`.
  Публичной регистрации нет.
- **OIDC-приложение «Shtab»** — через него ядро будет делать вход.
  Discovery: http://auth.shtab.localhost/application/o/shtab/.well-known/openid-configuration

### Пригласить человека (пока вручную)

Админка → *Directory → Invitations → Create*, поток — `shtab-invitation-enrollment`.
Ссылка вида: `http://auth.shtab.localhost/if/flow/shtab-invitation-enrollment/?itoken=<id>`.

> Одноразовое приглашение (`single use`) сгорает, как только ссылку открыли.

Позже это будет кнопка «Пригласить» в интерфейсе Shtab (ядро создаёт приглашение через API).

## Полезное

Команды — из папки `infra/`.

```bash
docker compose ps
```

```bash
docker compose logs -f core
```

Остановить (данные сохраняются в томах):

```bash
docker compose down
```

`docker compose down -v` удаляет **все данные** (базы, пользователей Authentik).

## Секреты

`infra/.env` создаётся скриптом со случайными паролями и **не попадает в git**.
Шаблон — [.env.example](.env.example).
