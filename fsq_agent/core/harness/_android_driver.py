from typing import Protocol, runtime_checkable


@runtime_checkable
class AndroidDriverInterface(Protocol):
    def context(self) -> dict[str, object]:
        ...

    def tap(self, params: dict[str, object]) -> dict[str, object]:
        ...

    def input_text(self, params: dict[str, object]) -> dict[str, object]:
        ...

    def back(self) -> dict[str, object]:
        ...

    def screenshot(self) -> bytes:
        ...

    def ui_tree(self) -> dict[str, object]:
        ...

