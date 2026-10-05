"""MCP-шлюз: через него ChatGPT и Claude работают с задачами Shtab.

ВНИМАНИЕ: пока без OAuth все вызовы идут от settings.dev_user.
Не открывать /mcp в интернет до подключения OAuth через Authentik.
"""

import uuid
from datetime import date

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

from shtab import tasks
from shtab.config import settings
from shtab.db import SessionLocal
from shtab.models import Scope, Status
from shtab.schemas import TaskOut

mcp = MCPServer(
    "shtab",
    instructions=(
        "Shtab — рабочая система пользователя: задачи, канбан, заметки. "
        "personal — личные задачи, shared — общие рабочие. "
        "Статусы (колонки канбана): todo, doing, review, done."
    ),
)


async def _user(session):
    return await tasks.get_or_create_user(session, settings.dev_user)


@mcp.tool()
async def list_tasks(scope: Scope | None = None, status: Status | None = None) -> list[TaskOut]:
    """Показать задачи пользователя: личные и общие. Можно отфильтровать по scope и status."""
    async with SessionLocal() as session:
        rows = await tasks.list_tasks(session, await _user(session), scope=scope, status=status)
        return [TaskOut.model_validate(r) for r in rows]


@mcp.tool()
async def add_task(
    title: str,
    scope: Scope = Scope.personal,
    due: date | None = None,
    tags: list[str] | None = None,
) -> TaskOut:
    """Добавить задачу во «Входящие». scope=shared — в общие рабочие задачи."""
    async with SessionLocal() as session:
        task = await tasks.create_task(
            session, await _user(session), title, scope=scope, due=due, tags=tags
        )
        return TaskOut.model_validate(task)


@mcp.tool()
async def move_task(task_id: uuid.UUID, status: Status) -> TaskOut:
    """Переместить задачу в другую колонку канбана (сменить статус)."""
    async with SessionLocal() as session:
        task = await tasks.move_task(session, await _user(session), task_id, status)
        return TaskOut.model_validate(task)


def build_app():
    return mcp.streamable_http_app(
        streamable_http_path="/mcp",
        stateless_http=True,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=settings.mcp_allowed_hosts,
            allowed_origins=[f"http://{h}" for h in settings.mcp_allowed_hosts]
            + [f"https://{h}" for h in settings.mcp_allowed_hosts],
        ),
    )
