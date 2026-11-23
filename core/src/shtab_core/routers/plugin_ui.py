"""UI manifests and static files for logged-in users."""

from dataclasses import replace
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter
from fastapi.responses import FileResponse
from pydantic import BaseModel, TypeAdapter

from shtab_core.config import paths
from shtab_core.dependencies import CurrentUser, Plugins
from shtab_core.exceptions import NotFoundError
from shtab_core.manifest import PluginFrontend
from shtab_core.models import PluginRecord

router = APIRouter(tags=["plugin-ui"])
FRONTEND = TypeAdapter(PluginFrontend)
ASSET_SUFFIXES = frozenset(
    {".js", ".css", ".json", ".svg", ".png", ".jpg", ".webp", ".woff", ".woff2"}
)


def stored_frontend(plugin: PluginRecord) -> PluginFrontend | None:
    """The plugin's UI as stored in the DB (JSON), parsed back into the dataclass."""
    return FRONTEND.validate_python(plugin.frontend) if plugin.frontend else None


class PluginUIOut(BaseModel):
    id: str
    name: str
    version: str
    frontend: PluginFrontend


def plugin_root(plugin_id: str) -> Path:
    base = paths.plugins.resolve()
    root = (base / plugin_id).resolve()
    if root.parent != base:
        raise NotFoundError("Plugin files not found")
    return root


def frontend_entry(root: Path, entry: str) -> Path:
    file = (root / entry).resolve()
    if not file.is_relative_to(root) or file.suffix != ".js":
        raise NotFoundError("UI entry point not found")
    return file


@router.get("/api/plugin-ui", response_model=list[PluginUIOut])
async def list_plugin_ui(_: CurrentUser, plugins: Plugins):
    result = []
    for plugin in await plugins.list_all():
        frontend = stored_frontend(plugin)
        if not frontend:
            continue
        root = plugin_root(plugin.id)
        entry = frontend_entry(root, frontend.entry).relative_to(root).as_posix()
        asset_url = f"/api/plugin-assets/{quote(plugin.id, safe='')}/{quote(entry)}"
        result.append(
            PluginUIOut(
                id=plugin.id,
                name=plugin.name,
                version=plugin.version,
                frontend=replace(frontend, entry=asset_url),
            )
        )
    return result


@router.get("/api/plugin-assets/{plugin_id}/{asset_path:path}")
async def plugin_asset(
    plugin_id: str, asset_path: str, _: CurrentUser, plugins: Plugins
):
    plugin = await plugins.get(plugin_id)
    frontend = stored_frontend(plugin)
    if not frontend:
        raise NotFoundError("Plugin has no UI")
    root = plugin_root(plugin.id)
    entry = frontend_entry(root, frontend.entry)
    file = (root / asset_path).resolve()
    if (
        not file.is_relative_to(entry.parent)
        or not file.is_relative_to(root)
        or file.suffix.lower() not in ASSET_SUFFIXES
        or not file.is_file()
    ):
        raise NotFoundError("Plugin file not found")
    return FileResponse(
        file, headers={"Cache-Control": "no-cache", "X-Content-Type-Options": "nosniff"}
    )
