from typing import Any, Literal

__all__ = ("MISSING",)


class _MissingSentinel:
    def __repr__(self) -> str:
        return "..."

    def __bool__(self) -> Literal[False]:
        return False

    def __eq__(self, other: object) -> Literal[False]:
        return False


MISSING: Any = _MissingSentinel()
