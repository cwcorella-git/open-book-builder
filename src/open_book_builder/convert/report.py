"""What the converter found: every rejected or flagged item, with its line."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Item:
    line: int  # 1-based line in the source file; 0 means the file as a whole
    level: str  # "error" stops the work from being written; "note" is only reported
    message: str

    def __str__(self) -> str:
        where = f"line {self.line}" if self.line else "file"
        return f"{self.level.capitalize()}, {where}: {self.message}"


@dataclass
class Report:
    items: list[Item] = field(default_factory=list)

    def error(self, line: int, message: str) -> None:
        self.items.append(Item(line, "error", message))

    def note(self, line: int, message: str) -> None:
        self.items.append(Item(line, "note", message))

    @property
    def errors(self) -> list[Item]:
        return [i for i in self.items if i.level == "error"]

    @property
    def ok(self) -> bool:
        return not self.errors
