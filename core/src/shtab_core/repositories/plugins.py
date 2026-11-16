from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shtab_core.models import PluginRecord


class PluginRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, plugin_id: str) -> PluginRecord | None:
        return await self.session.get(PluginRecord, plugin_id)

    async def list_all(self) -> list[PluginRecord]:
        plugins = await self.session.scalars(
            select(PluginRecord).order_by(PluginRecord.name, PluginRecord.id)
        )
        return list(plugins)

    async def add(self, plugin: PluginRecord) -> None:
        self.session.add(plugin)

    async def delete(self, plugin: PluginRecord) -> None:
        await self.session.delete(plugin)
