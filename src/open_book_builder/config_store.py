"""Planning data kept in data/configs.json: configurations, spare parts and quantities."""
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from .dataset import find_data_dir


class ConfigStore(QObject):
    changed = Signal()
    dirty_changed = Signal(bool)

    def __init__(self, path: Path | None = None, parent: QObject | None = None):
        super().__init__(parent)
        self.path = path or find_data_dir() / "configs.json"
        self.data = json.loads(self.path.read_text(encoding="utf-8"))
        self._dirty = False

    # -- reading ------------------------------------------------------------
    @property
    def dirty(self) -> bool:
        return self._dirty

    def configurations(self) -> list[dict]:
        return self.data["configurations"]

    def config(self, config_id: str | None) -> dict | None:
        return next((c for c in self.configurations() if c["id"] == config_id), None)

    def spare(self, config_id: str | None, mpn: str) -> int:
        cfg = self.config(config_id)
        if cfg and mpn in cfg["spares"]:
            return int(cfg["spares"][mpn])
        return int(self.data["defaultSpares"].get(mpn, 0))

    def quantity(self, config_id: str) -> int:
        return int(self.config(config_id)["quantity"])

    def include_optional(self, config_id: str) -> bool:
        return bool(self.config(config_id)["includeOptional"])

    # -- writing ------------------------------------------------------------
    def _touch(self) -> None:
        self.changed.emit()
        if not self._dirty:
            self._dirty = True
            self.dirty_changed.emit(True)

    def set_spare(self, config_id: str | None, mpn: str, count: int) -> None:
        count = max(0, int(count))
        if self.spare(config_id, mpn) == count:
            return
        cfg = self.config(config_id)
        (cfg["spares"] if cfg else self.data["defaultSpares"])[mpn] = count
        self._touch()

    def set_quantity(self, config_id: str, quantity: int) -> None:
        if self.quantity(config_id) != quantity:
            self.config(config_id)["quantity"] = int(quantity)
            self._touch()

    def set_include_optional(self, config_id: str, value: bool) -> None:
        if self.include_optional(config_id) != value:
            self.config(config_id)["includeOptional"] = bool(value)
            self._touch()

    def save(self) -> None:
        self.path.write_text(json.dumps(self.data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        self._dirty = False
        self.dirty_changed.emit(False)

    def revert(self) -> None:
        self.data = json.loads(self.path.read_text(encoding="utf-8"))
        self._dirty = False
        self.changed.emit()
        self.dirty_changed.emit(False)
