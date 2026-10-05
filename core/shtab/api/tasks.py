import uuid

from fastapi import APIRouter, HTTPException, status

from shtab import tasks
from shtab.auth import CurrentUser, DbSession
from shtab.models import Scope, Status
from shtab.schemas import Board, StatusUpdate, TaskCreate, TaskOut
from shtab.worker import reindex_all

router = APIRouter(prefix="/api", tags=["tasks"])


@router.get("/tasks", response_model=list[TaskOut])
async def get_tasks(
    session: DbSession, user: CurrentUser, scope: Scope | None = None, status: Status | None = None
):
    return await tasks.list_tasks(session, user, scope=scope, status=status)


@router.get("/board", response_model=Board)
async def get_board(session: DbSession, user: CurrentUser, scope: Scope | None = None):
    columns: dict[Status, list] = {s: [] for s in Status}
    for task in await tasks.list_tasks(session, user, scope=scope):
        columns[task.status].append(task)
    return Board(columns=columns)


@router.post("/tasks", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
async def create_task(body: TaskCreate, session: DbSession, user: CurrentUser):
    return await tasks.create_task(
        session, user, body.title, scope=body.scope, due=body.due, tags=body.tags
    )


@router.patch("/tasks/{task_id}/status", response_model=TaskOut)
async def move_task(task_id: uuid.UUID, body: StatusUpdate, session: DbSession, user: CurrentUser):
    try:
        return await tasks.move_task(session, user, task_id, body.status)
    except tasks.TaskNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Задача не найдена") from None
    except tasks.TaskConflict as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from None


@router.post("/reindex", status_code=status.HTTP_202_ACCEPTED)
async def reindex(user: CurrentUser):
    await reindex_all.kiq()
    return {"queued": True}
