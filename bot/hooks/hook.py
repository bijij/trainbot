from __future__ import annotations

from typing import Any, Callable, Coroutine

__all__ = (
    "hook",
    "Hook",
)


class Hook:
    event: str
    callback: Callable[..., Coroutine[None, None, Any]]


def hook(name: str, /) -> Callable[[Callable[..., Coroutine[None, None, Any]]], type[Hook]]:

    def decorator(func: Callable[..., Coroutine[None, None, Any]]) -> type[Hook]:
        class HookWrapper(Hook):
            event = name
            callback = func

        HookWrapper.__name__ = func.__name__
        HookWrapper.__qualname__ = func.__qualname__
        HookWrapper.__module__ = func.__module__

        return HookWrapper

    return decorator
