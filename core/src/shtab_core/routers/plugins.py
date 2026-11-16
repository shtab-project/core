"""Учёт плагинов. Все операции доступны только администратору."""

import logging

from fastapi import APIRouter, HTTPException, Response, status

from shtab_core.catalog import CATALOG
from shtab_core.dependencies import AdminPlugins
from shtab_core.schemas import PluginIn, PluginOut

router = APIRouter(prefix="/api/plugins", tags=["plugins"])
logger = logging.getLogger(__name__)


@router.get("", response_model=list[PluginOut], summary="Список плагинов (админ)")
async def list_plugins(plugins: AdminPlugins):
    return await plugins.list_all()


@router.get("/catalog", summary="Каталог плагинов (админ)")
async def list_catalog(plugins: AdminPlugins):
    installed = {plugin.id: plugin for plugin in await plugins.list_all()}
    return [
        {
            "id": plugin_id,
            "name": entry.manifest.name,
            "version": entry.manifest.version,
            "description": entry.description,
            "icon": entry.icon,
            "installed_version": installed[plugin_id].version if plugin_id in installed else None,
        }
        for plugin_id, entry in CATALOG.items()
    ]


@router.post("/catalog/{plugin_id}/install", response_model=PluginOut, status_code=201)
async def install_from_catalog(plugin_id: str, plugins: AdminPlugins):
    entry = CATALOG.get(plugin_id)
    if entry is None:
        raise HTTPException(404, "Плагин не найден в каталоге")
    try:
        return await plugins.register(entry.to_plugin())
    except (OSError, RuntimeError) as exc:
        logger.exception("Не удалось установить плагин из каталога: %s", plugin_id)
        raise HTTPException(502, "Не удалось установить плагин. Попробуйте ещё раз.") from exc


@router.get("/{plugin_id}", response_model=PluginOut, summary="Описание плагина (админ)")
async def get_plugin(plugin_id: str, plugins: AdminPlugins):
    return await plugins.get(plugin_id)


@router.post(
    "",
    response_model=PluginOut,
    status_code=status.HTTP_201_CREATED,
    summary="Зарегистрировать плагин (админ)",
    description="Устанавливает доверенный пакет, подключает backend и сохраняет описание.",
)
async def register_plugin(body: PluginIn, plugins: AdminPlugins):
    return await plugins.register(body.to_plugin())


@router.delete(
    "/{plugin_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить запись плагина (админ)",
    description="Удаляет запись из реестра. Файлы плагина не удаляются.",
)
async def unregister_plugin(plugin_id: str, plugins: AdminPlugins) -> Response:
    await plugins.unregister(plugin_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
