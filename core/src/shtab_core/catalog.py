from dataclasses import dataclass, replace
from pathlib import Path

from pydantic import TypeAdapter

from shtab_core.manifest import Plugin
from shtab_core.schemas import PluginIn


@dataclass(frozen=True)
class CatalogEntry:
    manifest: PluginIn
    description: str
    icon: str
    commit: str
    migration_module: str | None

    def to_plugin(self) -> Plugin:
        return replace(
            self.manifest.to_plugin(),
            release_ref=f"v{self.manifest.version}",
            release_commit=self.commit,
            migration_module=self.migration_module,
        )


CATALOG = {
    entry.manifest.id: entry
    for entry in TypeAdapter(list[CatalogEntry]).validate_json(
        Path(__file__).with_name("plugin_catalog.json").read_bytes()
    )
}
