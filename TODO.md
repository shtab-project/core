# Ближайшие задачи

- [x] Подключить локальный плагин: манифест → Python API → JS → меню и страница React.
- [x] Согласовать хранение задач и права доступа; реализовать «Задачи»: CRUD, список и Kanban.
- [ ] Проверить сохранение задач после перезапуска и доступ через сессию ядра.
  После обновления VPS число разделов задач в БД сохранилось, а API без входа возвращал `401`. Осталось проверить, что после перезапуска ранее созданная задача открывается в авторизованной сессии.
- [x] Сделать плагин «Заметки»: создание, редактирование и сохранение Markdown.
- [ ] Protect Swagger: `/api/docs` and `/api/openapi.json` must require a signed-in session.
  Disable the built-in routes (`docs_url=None`, `openapi_url=None` in `FastAPI(...)`) and add
  your own routes with the `CurrentUser` dependency: one returns `app.openapi()`, the other
  `get_swagger_ui_html(openapi_url="/api/openapi.json", ...)` from `fastapi.openapi.docs`.
  Redirect unauthenticated users from `/api/docs` to `/api/auth/login?next=/api/docs`
  instead of returning JSON `401`.

## Позже

- [ ] Вместе спроектировать MCP Shtab для работы ИИ с задачами и заметками; затем реализовать.
  MCP-шлюз и инструменты заметок уже реализованы. Осталось добавить инструменты задач.
- [ ] Установка и обновление плагинов из GitHub Releases с проверкой манифеста и версии.
  Каталог устанавливает плагины по закреплённому тегу и коммиту с проверкой манифеста и версии. Обновление «Задач» и «Заметок» выполняет отдельный скрипт. Осталось добавить обновление установленных плагинов на новый релиз через каталог.

Контракт для разработки: [PLUGIN_CONTRACT.md](PLUGIN_CONTRACT.md).
