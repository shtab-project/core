"""Plugin registry. Admins only."""

import logging

from fastapi import APIRouter, Response, status

from shtab_core.catalog import CATALOG
from shtab_core.dependencies import AdminPlugins
from shtab_core.exceptions import BadGatewayError, NotFoundError
from shtab_core.schemas import CatalogPluginOut, PluginIn, PluginOut

router = APIRouter(prefix="/api/plugins", tags=["plugins"])
logger = logging.getLogger(__name__)


@router.get("", response_model=list[PluginOut], summary="List plugins (admin)")
async def list_plugins(plugins: AdminPlugins):
    return await plugins.list_all()


@router.get(
    "/catalog",
    response_model=list[CatalogPluginOut],
    summary="Plugin catalog (admin)",
)
async def list_catalog(plugins: AdminPlugins):
    installed = {plugin.id: plugin.version for plugin in await plugins.list_all()}
    return [
        CatalogPluginOut(
            id=plugin_id,
            name=entry.manifest.name,
            version=entry.manifest.version,
            description=entry.description,
            icon=entry.icon,
            installed_version=installed.get(plugin_id),
        )
        for plugin_id, entry in CATALOG.items()
    ]


@router.post("/catalog/{plugin_id}/install", response_model=PluginOut, status_code=201)
async def install_from_catalog(plugin_id: str, plugins: AdminPlugins):
    entry = CATALOG.get(plugin_id)
    if not entry:
        raise NotFoundError("Plugin not found in the catalog")
    try:
        return await plugins.register(entry.to_plugin())
    except (OSError, RuntimeError) as exc:
        logger.exception("Failed to install plugin from the catalog: %s", plugin_id)
        raise BadGatewayError("Failed to install the plugin. Try again.") from exc


@router.get("/{plugin_id}", response_model=PluginOut, summary="Plugin details (admin)")
async def get_plugin(plugin_id: str, plugins: AdminPlugins):
    return await plugins.get(plugin_id)


@router.post(
    "",
    response_model=PluginOut,
    status_code=status.HTTP_201_CREATED,
    summary="Register a plugin (admin)",
    description="Installs a trusted package, mounts its backend and saves the record.",
)
async def register_plugin(body: PluginIn, plugins: AdminPlugins):
    return await plugins.register(body.to_plugin())


@router.delete(
    "/{plugin_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a plugin record (admin)",
    description="Removes the registry record. Plugin files stay on disk.",
)
async def unregister_plugin(plugin_id: str, plugins: AdminPlugins) -> Response:
    await plugins.unregister(plugin_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
