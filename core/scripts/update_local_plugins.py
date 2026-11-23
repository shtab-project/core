"""Synchronize already installed plugins after a local source update."""

import asyncio
import json
import subprocess
import sys
from pathlib import Path

from sqlalchemy import select

from shtab_core.catalog import CATALOG
from shtab_core.db import engine, get_session_factory
from shtab_core.models import PluginRecord
from shtab_core.schemas import PluginIn


async def main() -> None:
    check_only = sys.argv[1:] == ["--check"]
    try:
        async with get_session_factory().begin() as session:
            records = {}
            for plugin_id in ("notes", "todo"):
                record = await session.scalar(
                    select(PluginRecord).where(PluginRecord.id == plugin_id)
                )
                if not record:
                    raise RuntimeError(
                        f"Install {plugin_id} from the Plugins section first."
                    )
                records[plugin_id] = record
            if check_only:
                print("OK: notes and todo are installed")
                return
            manifests = {}
            for plugin_id in records:
                path = Path("/app/core/plugins") / plugin_id / "manifest.json"
                manifest = PluginIn.model_validate(json.loads(path.read_text()))
                if manifest.id != plugin_id:
                    raise ValueError(f"Invalid plugin ID: {path}")
                manifests[plugin_id] = manifest
            for plugin_id, record in records.items():
                module = CATALOG[plugin_id].migration_module
                if module:
                    subprocess.run(
                        [sys.executable, "-m", module, "upgrade", "head"], check=True
                    )
                manifest = manifests[plugin_id]
                record.name = manifest.name
                record.version = manifest.version
                record.backend_entrypoint = manifest.backend_entrypoint
                record.frontend = manifest.model_dump(mode="json")["frontend"]
                print(f"{plugin_id}: updated to {manifest.version}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
