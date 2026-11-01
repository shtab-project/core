class ServiceError(Exception):
    """Ошибка сценария, которую транспорт преобразует в ответ клиенту."""


class InvalidInputError(ServiceError):
    pass


class UnauthorizedError(ServiceError):
    pass


class NotFoundError(ServiceError):
    pass


class ConflictError(ServiceError):
    pass
