"""Install pinned task and note releases using the normal catalog installer."""

import asyncio
import sys

from shtab_core.catalog import CATALOG
from shtab_core.db import engine, get_session_factory
from shtab_core.main import create_app
from shtab_core.services.plugins import PluginLoader, PluginManager
from shtab_core.uow import UnitOfWork


async def main():
    loader = PluginLoader(create_app())
    try:
        for plugin_id in ("todo", "notes"):
            entry = CATALOG[plugin_id]

            async with UnitOfWork(get_session_factory()) as uow:
                manager = PluginManager(uow, loader)
                installed = await uow.plugins.get(plugin_id)
                if installed:
                    if installed.version != entry.manifest.version:
                        raise RuntimeError(
                            f"{plugin_id}: installed {installed.version}, "
                            f"required {entry.manifest.version}. "
                            "An existing plugin is not updated automatically."
                        )
                    if entry.migration_module:
                        process = await asyncio.create_subprocess_exec(
                            sys.executable,
                            "-m",
                            entry.migration_module,
                            "upgrade",
                            "head",
                        )
                        if await process.wait():
                            raise RuntimeError(f"{plugin_id}: migration failed")
                    print(f"{plugin_id}: already installed", flush=True)
                    continue
                await manager.register(entry.to_plugin())
                print(f"{plugin_id}: installed {entry.manifest.version}", flush=True)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
