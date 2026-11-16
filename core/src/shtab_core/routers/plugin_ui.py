"""Манифесты интерфейса и статические файлы для вошедших пользователей."""

from dataclasses import replace
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from shtab_core.config import paths
from shtab_core.dependencies import CurrentUser, Plugins
from shtab_core.services.plugins import PluginFrontend

router = APIRouter(tags=["plugin-ui"])


class PluginUIOut(BaseModel):
    id: str
    name: str
    version: str
    frontend: PluginFrontend


def plugin_root(plugin_id: str) -> Path:
    base = paths.plugins.resolve()
    root = (base / plugin_id).resolve()
    if root.parent != base:
        raise HTTPException(404, "Файлы плагина не найдены")
    return root


def frontend_entry(root: Path, entry: str) -> Path:
    file = (root / entry).resolve()
    if not file.is_relative_to(root) or file.suffix != ".js":
        raise HTTPException(404, "Точка входа интерфейса не найдена")
    return file


@router.get("/api/plugin-ui", response_model=list[PluginUIOut])
async def list_plugin_ui(_: CurrentUser, plugins: Plugins):
    result = []
    for plugin in await plugins.list_all():
        if plugin.frontend is None:
            continue
        frontend = PluginUIOut(
            id=plugin.id, name=plugin.name, version=plugin.version, frontend=plugin.frontend
        ).frontend
        root = plugin_root(plugin.id)
        entry = frontend_entry(root, frontend.entry).relative_to(root).as_posix()
        result.append(
            PluginUIOut(
                id=plugin.id,
                name=plugin.name,
                version=plugin.version,
                frontend=replace(
                    frontend,
                    entry=f"/api/plugin-assets/{quote(plugin.id, safe='')}/{quote(entry)}",
                ),
            )
        )
    return result


@router.get("/api/plugin-assets/{plugin_id}/{asset_path:path}")
async def plugin_asset(plugin_id: str, asset_path: str, _: CurrentUser, plugins: Plugins):
    plugin = await plugins.get(plugin_id)
    if plugin.frontend is None:
        raise HTTPException(404, "У плагина нет интерфейса")
    root = plugin_root(plugin.id)
    entry = frontend_entry(root, plugin.frontend["entry"])
    file = (root / asset_path).resolve()
    if (
        not file.is_relative_to(entry.parent)
        or not file.is_relative_to(root)
        or file.suffix.lower()
        not in {".js", ".css", ".json", ".svg", ".png", ".jpg", ".webp", ".woff", ".woff2"}
        or not file.is_file()
    ):
        raise HTTPException(404, "Файл плагина не найден")
    return FileResponse(
        file, headers={"Cache-Control": "no-cache", "X-Content-Type-Options": "nosniff"}
    )
