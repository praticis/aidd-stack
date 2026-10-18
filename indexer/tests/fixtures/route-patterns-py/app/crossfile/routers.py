from fastapi import APIRouter, Depends


def current_user(): ...


class UserAPIRouter(APIRouter):
    """The project's router: a dependency on every route, the prefix handed on to APIRouter."""

    def __init__(self, tags: list[str] | None = None, prefix: str = "", **kwargs):
        super().__init__(tags=tags, prefix=prefix, dependencies=[Depends(current_user)], **kwargs)


class AdminAPIRouter(UserAPIRouter):
    """A router through a base of the project's: UserAPIRouter's __init__ reads the prefix."""


class AuditAPIRouter(APIRouter):
    """A prefix of its own, whatever the call passes."""

    def __init__(self, **kwargs):
        super().__init__(prefix="/audits", **kwargs)
