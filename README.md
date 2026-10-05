# Shtab

Рабочий штаб: одно ядро, вокруг которого собраны заметки, задачи, канбан
и любые другие сервисы-плагины. ИИ-помощник (ChatGPT / Claude) подключается
через MCP и работает с задачами так же, как ты.

```
             Телефон / браузер / ChatGPT / Claude
                            │
                 Traefik  (+ Authentik — этап 2)
       ┌──────────────┬─────┴───────┬──────────────────┐
   core (FastAPI)  worker       watcher         SilverBullet ×N
   REST + MCP      (taskiq)     (следит за .md)  shared + личные
       └──────── PostgreSQL · Redis · data/notes/*.md ─┘
```

## Главная идея: Markdown — источник истины

Задачи живут в обычных `.md`-файлах в синтаксисе SilverBullet:

```markdown
- [ ] Сверить смету #гидро [status: doing] [due: 2026-10-10]
```

- **SilverBullet** редактирует файлы как заметки.
- **Ядро** индексирует их в Postgres и показывает канбаном. Перетащил карточку —
  в файле поменялся `[status: …]`.
- **watcher** замечает правки из SilverBullet и ставит переиндексацию.
- **Пространства:** `data/notes/shared/` — общие (видят все), `data/notes/users/<логин>/` — личные.

Колонки канбана: `todo → doing → review → done`.

## Структура

```
core/      ядро: FastAPI, SQLAlchemy, Alembic, taskiq, MCP
web/       веб-интерфейс (ещё не начат)
plugins/   плагины: plugin.yaml + docker-compose.yml
```

## Запуск в Docker

```bash
cp .env.example .env
```

```bash
docker compose up -d --build
```

- API: http://api.shtab.localhost/docs
- Общие заметки: http://notes.shtab.localhost
- Личные (admin): http://admin.notes.shtab.localhost

## Разработка ядра без Docker

Нужны Postgres и Redis (можно поднять только их: `docker compose up -d postgres redis`).

```bash
cd core && uv sync
```

```bash
cd core && uv run alembic upgrade head && uv run uvicorn shtab.main:app --reload
```

```bash
cd core && uv run pytest
```

Тесты не требуют Postgres/Redis — используют SQLite в памяти и временную папку.

## MCP-инструменты

| Инструмент | Что делает |
|---|---|
| `list_tasks(scope?, status?)` | задачи пользователя: личные + общие |
| `add_task(title, scope?, due?, tags?)` | добавить во `Inbox.md` нужного пространства |
| `move_task(task_id, status)` | переместить по канбану |

> ⚠️ Пока без OAuth все MCP-вызовы идут от `SHTAB_DEV_USER`. Не открывать `/mcp`
> в интернет до этапа 2.

## Дорожная карта

1. ✅ **Каркас:** ядро, индекс задач из Markdown, канбан-API, MCP, Docker Compose.
2. **Вход:** Authentik, forward-auth на все маршруты, OAuth для MCP → подключение
   к ChatGPT Plus и Claude Pro как коннектор. Отсюда же — закрытые dev-сайты.
3. **Веб:** портал + канбан + граф, PWA для телефона.
4. **Плагины:** установка из `plugins/*` в пару кликов, плитки в портале.
5. **Интеграции:** мост к Bitrix24, свой мессенджер, мониторинг серверов.
