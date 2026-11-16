from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(eq=False)
class BaseError(Exception, ABC):
    @property
    @abstractmethod
    def message(self) -> str: ...

    def __str__(self) -> str:
        return self.message


@dataclass(eq=False)
class PluginNotFoundError(BaseError):
    @property
    def message(self) -> str:
        return "Plugin not found in repository"


class DatabaseError(Exception): ...


@dataclass(eq=False)
class DatabaseWriteError(BaseError):
    @property
    def message(self) -> str:
        return "Modifications are not allowed in read-only session"
