import json
import sys
from types import ModuleType
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import APIRouter, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import IntegrityError

from shtab_core.config import Paths
from shtab_core.db import get_session_factory
from shtab_core.dependencies import get_plugin_loader
from shtab_core.main import create_app
from shtab_core.models import PluginRecord
from shtab_core.schemas import PluginIn
from shtab_core.services.plugins import PluginLoader, PluginManager, load_backend
from shtab_core.uow import UnitOfWork


def test_backend_entrypoint_calls_plugin_register(monkeypatch):
    app = FastAPI()
    module = ModuleType("example_plugin")
    module.register = Mock()
    monkeypatch.setitem(sys.modules, "example_plugin", module)
    load_backend(app, "example_plugin:register")
    module.register.assert_called_once_with(app)


def test_loader_receives_current_application():
    from starlette.requests import Request

    app = FastAPI()
    request = Request({"type": "http", "app": app})
    assert get_plugin_loader(request).app is app
    assert get_plugin_loader(request) is get_plugin_loader(request)


@pytest.fixture
def local_plugin(tmp_path, monkeypatch):
    source = tmp_path / "example"
    source.mkdir()
    (source / "pyproject.toml").write_text('[project]\nname = "example-plugin"\nversion = "1"')
    payload = {
        "id": "example",
        "name": "Example",
        "version": "1",
        "url": "local:example",
        "backend_entrypoint": "example_plugin:register",
        "frontend": None,
    }
    (source / "manifest.json").write_text(json.dumps(payload))
    module = ModuleType("example_plugin")

    def register(app):
        router = APIRouter()

        @router.get("/api/example")
        async def example():
            return {"ok": True}

        app.include_router(router)

    module.register = register
    monkeypatch.setitem(sys.modules, "example_plugin", module)
    return PluginIn.model_validate(payload).to_plugin()


async def test_local_install_commit_failure_removes_files_and_routes(
    uow, tmp_path, monkeypatch, local_plugin
):
    app = FastAPI()
    loader = PluginLoader(app, Paths(workspace=tmp_path))
    monkeypatch.setattr(loader, "_sync_workspace", AsyncMock())

    async def fail_commit():
        await uow.flush()
        raise IntegrityError("insert", {}, Exception("failed commit"))

    monkeypatch.setattr(uow.plugins.session, "commit", fail_commit)
    with pytest.raises(IntegrityError):
        await PluginManager(uow, loader).register(local_plugin)
    assert not loader.directory("example").exists()
    assert await uow.plugins.list_all() == []
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get("/api/example")).status_code == 404


async def test_sync_failure_removes_partial_install(tmp_path, monkeypatch, local_plugin):
    loader = PluginLoader(FastAPI(), Paths(workspace=tmp_path))
    monkeypatch.setattr(loader, "_sync_workspace", AsyncMock(side_effect=RuntimeError("uv failed")))
    with pytest.raises(RuntimeError, match="uv failed"):
        await loader.install(local_plugin)
    assert not loader.directory("example").exists()


async def test_preinstalled_files_survive_failed_registration(
    uow, tmp_path, monkeypatch, local_plugin
):
    previous = PluginLoader(FastAPI(), Paths(workspace=tmp_path))
    monkeypatch.setattr(previous, "_sync_workspace", AsyncMock())
    await previous.install(local_plugin)
    await previous.confirm(local_plugin)
    loader = PluginLoader(FastAPI(), Paths(workspace=tmp_path))
    monkeypatch.setattr(loader, "_sync_workspace", AsyncMock())
    monkeypatch.setattr(
        uow.plugins.session, "commit", AsyncMock(side_effect=RuntimeError("commit failed"))
    )
    with pytest.raises(RuntimeError, match="commit failed"):
        await PluginManager(uow, loader).register(local_plugin)
    assert (loader.directory("example") / "manifest.json").is_file()
    assert await uow.plugins.list_all() == []


async def test_startup_restores_registry_without_installing(
    session_factory, tmp_path, monkeypatch, local_plugin
):
    async with UnitOfWork(session_factory) as uow:
        app = create_app()
        loader = PluginLoader(app, Paths(workspace=tmp_path))
        sync = AsyncMock()
        monkeypatch.setattr(loader, "_sync_workspace", sync)
        await PluginManager(uow, loader).register(local_plugin)
        sync.assert_awaited_once()

    for _ in range(2):
        restarted = create_app()
        loader = PluginLoader(restarted, Paths(workspace=tmp_path))
        install = AsyncMock(side_effect=AssertionError("startup must not reinstall"))
        monkeypatch.setattr(loader, "install", install)
        restarted.state.plugin_loader = loader
        restarted.dependency_overrides[get_session_factory] = lambda: session_factory
        async with restarted.router.lifespan_context(restarted):
            async with AsyncClient(
                transport=ASGITransport(app=restarted), base_url="http://test"
            ) as client:
                assert (await client.get("/api/example")).json() == {"ok": True}
                assert "/api/example" in restarted.openapi()["paths"]
        install.assert_not_awaited()


async def test_missing_installed_files_fail_startup(session_factory, tmp_path):
    async with UnitOfWork(session_factory) as uow:
        async with uow.transaction():
            await uow.plugins.add(
                PluginRecord(
                    id="missing",
                    name="Missing",
                    version="1",
                    url="local:missing",
                    backend_entrypoint="missing_plugin:register",
                )
            )
    app = create_app()
    app.state.plugin_loader = PluginLoader(app, Paths(workspace=tmp_path))
    app.dependency_overrides[get_session_factory] = lambda: session_factory
    with pytest.raises(RuntimeError, match="missing"):
        async with app.router.lifespan_context(app):
            pytest.fail("Startup should fail when an installed plugin is missing")


async def test_subprocess_runs_from_workspace_and_reports_its_error(tmp_path, monkeypatch):
    process = AsyncMock()
    process.returncode = 1
    process.communicate.return_value = (b"", b"sync failed")
    spawn = AsyncMock(return_value=process)
    monkeypatch.setattr("asyncio.create_subprocess_exec", spawn)
    loader = PluginLoader(FastAPI(), Paths(workspace=tmp_path))
    with pytest.raises(RuntimeError, match="sync failed"):
        await loader._run("uv", "sync", "--all-packages")
    assert spawn.call_args.kwargs["cwd"] == tmp_path
