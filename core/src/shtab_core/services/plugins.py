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

from fastapi import FastAPI
from sqlalchemy.exc import IntegrityError

from shtab_core.config import Paths, paths
from shtab_core.exceptions import ConflictError, InvalidInputError, NotFoundError
from shtab_core.manifest import Plugin
from shtab_core.mcp_gateway import PluginTools
from shtab_core.models import PluginRecord
from shtab_core.schemas import PluginIn
from shtab_core.uow import UnitOfWork


@dataclass
class PluginLoader:
    """Installs trusted packages into the workspace and mounts them in the app."""

    app: FastAPI
    locations: Paths = paths
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _installed: set[str] = field(default_factory=set, init=False)
    _routes: dict[str, list] = field(default_factory=dict, init=False)
    _tools: dict[str, PluginTools] = field(default_factory=dict, init=False)

    def directory(self, plugin_id: str) -> Path:
        if not plugin_id or any(
            character
            not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
            for character in plugin_id
        ):
            raise InvalidInputError("Invalid plugin ID")
        base = self.locations.plugins.resolve()
        destination = (base / plugin_id).resolve()
        if destination.parent != base:
            raise InvalidInputError("Plugin folder is outside the plugin store")
        return destination

    async def install(self, plugin: Plugin) -> None:
        destination = self.directory(plugin.id)
        created = not destination.exists()
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            if created and plugin.url.startswith("local:"):
                source = (
                    self.locations.workspace / plugin.url.removeprefix("local:")
                ).resolve()
                if (
                    not source.is_relative_to(self.locations.workspace.resolve())
                    or not (source / "manifest.json").is_file()
                    or destination.is_relative_to(source)
                ):
                    raise InvalidInputError(
                        "Local plugin source not found or not allowed"
                    )
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
                    ("--branch", plugin.release_ref, "--depth", "1")
                    if plugin.release_ref
                    else ()
                )
                await self._run(
                    "git", "clone", *release, "--", plugin.url, str(destination)
                )
            if plugin.release_commit:
                commit = await self._run(
                    "git", "-C", str(destination), "rev-parse", "HEAD"
                )
                if commit.strip() != plugin.release_commit:
                    raise InvalidInputError(
                        "Plugin folder doesn't match the catalog release"
                    )
                changes = await self._run(
                    "git",
                    "-C",
                    str(destination),
                    "status",
                    "--porcelain",
                    "--untracked-files=all",
                )
                if changes.strip():
                    raise InvalidInputError("Plugin folder has local changes")
            self._validate_manifest(destination, plugin)
            await self._sync_workspace()
            if plugin.migration_module:
                await self._run(
                    sys.executable, "-m", plugin.migration_module, "upgrade", "head"
                )
            # uv writes .pth files for editable packages; reload them here.
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
        # Validate JSON with the HTTP schema at the boundary; use the dataclass inside.
        if not (destination / "pyproject.toml").is_file():
            raise InvalidInputError("Plugin has no pyproject.toml")
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
            raise InvalidInputError("Plugin description doesn't match its manifest")
        if plugin.frontend:
            entry = (destination / plugin.frontend.entry).resolve()
            if (
                not entry.is_relative_to(destination)
                or entry.suffix != ".js"
                or not entry.is_file()
            ):
                raise InvalidInputError("Plugin JS entry point not found")

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
            raise RuntimeError(
                f"{command[0]} failed: {stderr.decode(errors='replace').strip()}"
            )
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
            raise RuntimeError(
                "Run the core with uv run --all-packages from the workspace root"
            )
        return environment

    def activate(
        self, plugin_id: str, entrypoint: str, mcp_entrypoint: str | None = None
    ) -> None:
        if plugin_id in self._routes:
            return
        previous = list(self.app.router.routes)
        try:
            load_backend(self.app, entrypoint)
            if mcp_entrypoint:
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
        """Undo this process's install if the DB record wasn't saved."""
        self.deactivate(plugin.id)
        if plugin.id in self._installed:
            await self._remove_directory(self.directory(plugin.id))
            self._installed.remove(plugin.id)

    async def confirm(self, plugin: Plugin) -> None:
        """After commit the files belong to the saved install."""
        self._installed.discard(plugin.id)

    async def _remove_directory(self, destination: Path) -> None:
        await asyncio.to_thread(self._remove_directory_sync, destination)

    def _remove_directory_sync(self, destination: Path) -> None:
        if destination.resolve().parent != self.locations.plugins.resolve():
            raise RuntimeError("Refusing to delete a folder outside the plugin store")
        if destination.exists():
            shutil.rmtree(destination)

    def restore(self, plugin: PluginRecord) -> None:
        destination = self.directory(plugin.id)
        if not (destination / "manifest.json").is_file():
            raise RuntimeError(f"Installed plugin {plugin.id}: files not found")
        try:
            manifest = PluginIn.model_validate_json(
                (destination / "manifest.json").read_text(encoding="utf-8")
            )
            self.activate(plugin.id, plugin.backend_entrypoint, manifest.mcp_entrypoint)
        except Exception as exc:
            raise RuntimeError(f"Failed to load plugin {plugin.id}") from exc

    async def inspect(self, name: str) -> bool:
        """Inspect a plugin from GitHub."""
        raise NotImplementedError("GitHub inspection is not implemented yet")

    async def remove(self, name: str) -> None:
        """Remove a plugin from Shtab."""
        raise NotImplementedError("Removing plugin files is not implemented yet")


# Calls the plugin's entry point, which mounts its routes.
def load_backend(app: FastAPI, entrypoint: str) -> None:
    load_entrypoint(entrypoint)(app)
    app.openapi_schema = None


def load_entrypoint(entrypoint: str):
    module_name, function = entrypoint.split(":", maxsplit=1)

    module = import_module(module_name)
    register = getattr(module, function)
    if not callable(register):
        raise InvalidInputError("Plugin entry point must be callable")
    return register


@dataclass
class PluginManager:
    """Manages plugin installs and their records through the UoW."""

    uow: UnitOfWork
    plugin_loader: PluginLoader

    async def get(self, plugin_id: str) -> PluginRecord:
        plugin = await self.uow.plugins.get(plugin_id)
        if not plugin:
            raise NotFoundError("Plugin not found")
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
                if plugin.frontend
                else None
            ),
        )

        async with self.plugin_loader.lock:
            installed = False
            try:
                async with self.uow.transaction():
                    if await self.uow.plugins.get(plugin.id):
                        raise ConflictError("Plugin is already registered")
                    await self.plugin_loader.install(plugin)
                    installed = True
                    await self.uow.plugins.add(record)
            except BaseException as exc:
                if installed:
                    await self.plugin_loader.discard(plugin)
                if isinstance(exc, IntegrityError) and await self.uow.plugins.get(
                    plugin.id
                ):
                    raise ConflictError("Plugin is already registered") from None
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
        """Install a plugin from GitHub."""
        raise NotImplementedError("Installing from GitHub is not implemented yet")

    async def inspect(self, name: str) -> bool:
        """Inspect a plugin from GitHub."""
        raise NotImplementedError("GitHub inspection is not implemented yet")

    async def remove(self, name: str) -> None:
        """Remove a plugin from Shtab."""
        raise NotImplementedError("Removing plugin files is not implemented yet")
