import asyncio
import json
import os
import shutil
import site
import sys
import sysconfig
from dataclasses import asdict, dataclass, field
from importlib import import_module, invalidate_caches
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI
from sqlalchemy.exc import IntegrityError

from shtab_core.config import Paths, paths
from shtab_core.models import PluginRecord
from shtab_core.services.errors import ConflictError, InvalidInputError, NotFoundError
from shtab_core.uow import UnitOfWork

if TYPE_CHECKING:
    from shtab_core.mcp_gateway import PluginTools


@dataclass(frozen=True)
class PluginPage:
    """Страница плагина: маршрут интерфейса и имя Web Component."""

    path: str
    element: str


@dataclass(frozen=True)
class PluginMenuItem:
    """Пункт меню, который ядро рисует в предусмотренном месте (slot)."""

    slot: str
    title: str
    path: str
    order: int = 100
    icon: str | None = None


@dataclass(frozen=True)
class PluginFrontend:
    """JS-модуль плагина и его вклад в интерфейс ядра."""

    entry: str
    pages: tuple[PluginPage, ...] = ()
    menu_items: tuple[PluginMenuItem, ...] = ()


@dataclass(frozen=True)
class Plugin:
    """Описание плагина из манифеста, без состояния установки и выполнения."""

    id: str
    name: str
    version: str
    url: str
    backend_entrypoint: str
    frontend: PluginFrontend | None = None
    mcp_entrypoint: str | None = None
    release_ref: str | None = None
    release_commit: str | None = None
    migration_module: str | None = None


@dataclass
class PluginLoader:
    """Устанавливает доверенные пакеты в workspace и подключает их к приложению."""

    app: FastAPI
    locations: Paths = paths
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _installed: set[str] = field(default_factory=set, init=False)
    _routes: dict[str, list] = field(default_factory=dict, init=False)
    _tools: dict[str, "PluginTools"] = field(default_factory=dict, init=False)

    def directory(self, plugin_id: str) -> Path:
        if not plugin_id or any(
            character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
            for character in plugin_id
        ):
            raise InvalidInputError("Недопустимый ID плагина")
        base = self.locations.plugins.resolve()
        destination = (base / plugin_id).resolve()
        if destination.parent != base:
            raise InvalidInputError("Папка плагина находится вне хранилища")
        return destination

    async def install(self, plugin: Plugin) -> None:
        destination = self.directory(plugin.id)
        created = not destination.exists()
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            if created and plugin.url.startswith("local:"):
                source = (self.locations.workspace / plugin.url.removeprefix("local:")).resolve()
                if (
                    not source.is_relative_to(self.locations.workspace.resolve())
                    or not (source / "manifest.json").is_file()
                    or destination.is_relative_to(source)
                ):
                    raise InvalidInputError("Локальный источник плагина не найден или недопустим")
                await asyncio.to_thread(
                    shutil.copytree,
                    source,
                    destination,
                    ignore=shutil.ignore_patterns(
                        ".git", ".venv", "node_modules", "__pycache__", "*.pyc"
                    ),
                )
            elif created:
                release = (
                    ("--branch", plugin.release_ref, "--depth", "1") if plugin.release_ref else ()
                )
                await self._run("git", "clone", *release, "--", plugin.url, str(destination))
            if plugin.release_commit:
                commit = await self._run("git", "-C", str(destination), "rev-parse", "HEAD")
                if commit.strip() != plugin.release_commit:
                    raise InvalidInputError("Папка плагина не соответствует релизу из каталога")
                changes = await self._run(
                    "git", "-C", str(destination), "status", "--porcelain", "--untracked-files=all"
                )
                if changes.strip():
                    raise InvalidInputError("В папке плагина есть локальные изменения")
            self._validate_manifest(destination, plugin)
            await self._sync_workspace()
            if plugin.migration_module:
                await self._run(sys.executable, "-m", plugin.migration_module, "upgrade", "head")
            # uv добавляет .pth для editable-пакетов; текущий процесс перечитывает их явно.
            site.addsitedir(sysconfig.get_path("purelib"))
            invalidate_caches()
            self.activate(plugin.id, plugin.backend_entrypoint, plugin.mcp_entrypoint)
            if created:
                self._installed.add(plugin.id)
        except BaseException:
            self.deactivate(plugin.id)
            if created:
                await self._remove_directory(destination)
            raise

    def _validate_manifest(self, destination: Path, plugin: Plugin) -> None:
        # На границе JSON используем валидацию HTTP-схемы, внутри — dataclass.
        from shtab_core.schemas import PluginIn

        if not (destination / "pyproject.toml").is_file():
            raise InvalidInputError("У плагина нет pyproject.toml")
        manifest = PluginIn.model_validate_json(
            (destination / "manifest.json").read_text(encoding="utf-8")
        ).to_plugin()
        if (
            manifest.id != plugin.id
            or manifest.version != plugin.version
            or manifest.backend_entrypoint != plugin.backend_entrypoint
            or manifest.mcp_entrypoint != plugin.mcp_entrypoint
            or manifest.frontend != plugin.frontend
        ):
            raise InvalidInputError("Описание плагина не совпадает с его манифестом")
        if plugin.frontend is not None:
            entry = (destination / plugin.frontend.entry).resolve()
            if (
                not entry.is_relative_to(destination)
                or entry.suffix != ".js"
                or not entry.is_file()
            ):
                raise InvalidInputError("JS-точка входа плагина не найдена")

    async def _run(self, *command: str, env: dict[str, str] | None = None) -> str:
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=self.locations.workspace,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await process.communicate()
        except asyncio.CancelledError:
            if process.returncode is None:
                process.terminate()
            await process.communicate()
            raise
        if process.returncode != 0:
            raise RuntimeError(f"Ошибка {command[0]}: {stderr.decode(errors='replace').strip()}")
        return stdout.decode(errors="replace")

    async def _sync_workspace(self) -> None:
        environment = await asyncio.to_thread(self._environment)
        await self._run(
            "uv",
            "sync",
            "--all-packages",
            "--inexact",
            env={**os.environ, "UV_PROJECT_ENVIRONMENT": str(environment)},
        )

    def _environment(self) -> Path:
        environment = (self.locations.workspace / ".venv").resolve()
        if Path(sys.prefix).resolve() != environment:
            raise RuntimeError("Запустите ядро через uv run --all-packages из корня workspace")
        return environment

    def activate(self, plugin_id: str, entrypoint: str, mcp_entrypoint: str | None = None) -> None:
        if plugin_id in self._routes:
            return
        previous = list(self.app.router.routes)
        try:
            load_backend(self.app, entrypoint)
            if mcp_entrypoint is not None:
                from shtab_core.mcp_gateway import PluginTools

                tools = PluginTools(self.app.state.mcp, self.app, plugin_id)
                self._tools[plugin_id] = tools
                load_entrypoint(mcp_entrypoint)(tools)
        except BaseException:
            if tools := self._tools.pop(plugin_id, None):
                tools.close()
            self.app.router.routes[:] = previous
            self.app.openapi_schema = None
            raise
        self._routes[plugin_id] = [
            route for route in self.app.router.routes if route not in previous
        ]

    def deactivate(self, plugin_id: str) -> None:
        if tools := self._tools.pop(plugin_id, None):
            tools.close()
        added = self._routes.pop(plugin_id, [])
        self.app.router.routes[:] = [
            route for route in self.app.router.routes if route not in added
        ]
        self.app.openapi_schema = None

    async def discard(self, plugin: Plugin) -> None:
        """Убрать установку этого процесса, если запись в БД не сохранилась."""
        self.deactivate(plugin.id)
        if plugin.id in self._installed:
            await self._remove_directory(self.directory(plugin.id))
            self._installed.remove(plugin.id)

    async def confirm(self, plugin: Plugin) -> None:
        """После commit файлы принадлежат сохранённой установке."""
        self._installed.discard(plugin.id)

    async def _remove_directory(self, destination: Path) -> None:
        await asyncio.to_thread(self._remove_directory_sync, destination)

    def _remove_directory_sync(self, destination: Path) -> None:
        if destination.resolve().parent != self.locations.plugins.resolve():
            raise RuntimeError("Нельзя удалить папку вне хранилища плагинов")
        if destination.exists():
            shutil.rmtree(destination)

    def restore(self, plugin: PluginRecord) -> None:
        from shtab_core.schemas import PluginIn

        destination = self.directory(plugin.id)
        if not (destination / "manifest.json").is_file():
            raise RuntimeError(f"Установленный плагин {plugin.id}: файлы не найдены")
        try:
            manifest = PluginIn.model_validate_json(
                (destination / "manifest.json").read_text(encoding="utf-8")
            )
            self.activate(plugin.id, plugin.backend_entrypoint, manifest.mcp_entrypoint)
        except Exception as exc:
            raise RuntimeError(f"Не удалось загрузить плагин {plugin.id}") from exc

    async def inspect(self, name: str) -> bool:
        """Проверка плагина из GitHub."""
        raise NotImplementedError("Проверка GitHub пока не реализована")

    async def remove(self, name: str) -> None:
        """Удаление плагина из Shtab."""
        raise NotImplementedError("Удаление файлов плагина пока не реализовано")


# Плагин который устанавливает маршруты и остальные функции.
def load_backend(app: FastAPI, entrypoint: str) -> None:
    load_entrypoint(entrypoint)(app)
    app.openapi_schema = None


def load_entrypoint(entrypoint: str):
    module_name, function = entrypoint.split(":", maxsplit=1)

    module = import_module(module_name)
    register = getattr(module, function)
    if not callable(register):
        raise InvalidInputError("Точка входа плагина должна быть функцией")
    return register


class PluginManager:
    """Управляет установкой плагинов и их записями через UoW."""

    def __init__(self, uow: UnitOfWork, plugin_loader: PluginLoader) -> None:
        self.uow = uow
        self.plugin_loader = plugin_loader

    async def get(self, plugin_id: str) -> PluginRecord:
        plugin = await self.uow.plugins.get(plugin_id)
        if plugin is None:
            raise NotFoundError("Плагин не найден")
        return plugin

    async def list_all(self) -> list[PluginRecord]:
        return await self.uow.plugins.list_all()

    async def register(self, plugin: Plugin) -> PluginRecord:
        record = PluginRecord(
            id=plugin.id,
            name=plugin.name,
            version=plugin.version,
            url=plugin.url,
            backend_entrypoint=plugin.backend_entrypoint,
            frontend=(
                json.loads(json.dumps(asdict(plugin.frontend)))
                if plugin.frontend is not None
                else None
            ),
        )
        async with self.plugin_loader.lock:
            installed = False
            try:
                async with self.uow.transaction():
                    if await self.uow.plugins.get(plugin.id) is not None:
                        raise ConflictError("Плагин уже зарегистрирован")
                    await self.plugin_loader.install(plugin)
                    installed = True
                    await self.uow.plugins.add(record)
            except BaseException as exc:
                if installed:
                    await self.plugin_loader.discard(plugin)
                if isinstance(exc, IntegrityError) and await self.uow.plugins.get(plugin.id):
                    raise ConflictError("Плагин уже зарегистрирован") from None
                raise
            await self.plugin_loader.confirm(plugin)
        return record

    async def unregister(self, plugin_id: str) -> None:
        async with self.plugin_loader.lock:
            async with self.uow.transaction():
                record = await self.get(plugin_id)
                await self.uow.plugins.delete(record)
            self.plugin_loader.deactivate(plugin_id)

    async def install(self, plugin: Plugin) -> None:
        """Установка плагина из GitHub."""
        raise NotImplementedError("Установка из GitHub пока не реализована")

    async def inspect(self, name: str) -> bool:
        """Проверка плагина из GitHub."""
        raise NotImplementedError("Проверка GitHub пока не реализована")

    async def remove(self, name: str) -> None:
        """Удаление плагина из Shtab."""
        raise NotImplementedError("Удаление файлов плагина пока не реализовано")
