"""Objective chain and overall game progress (engine independent)."""
from __future__ import annotations

from dataclasses import dataclass, field

from .rooms_data import KEY_HOMES, KEY_NAMES

MAX_CHANCES = 3


@dataclass
class Progress:
    read_note: bool = False
    keys: set[str] = field(default_factory=set)
    has_can: bool = False
    orchid_watered: bool = False
    escaped: bool = False
    caught_count: int = 0
    time_played: float = 0.0

    @property
    def key_count(self) -> int:
        return len(self.keys)

    @property
    def hall_stage(self) -> int:
        return min(3, self.key_count)

    @property
    def garden_stage(self) -> int:
        """0 = safe haven … 3 = withered, fog-choked."""
        return min(3, self.key_count + (1 if self.orchid_watered else 0))

    @property
    def front_door_open(self) -> bool:
        return self.orchid_watered and self.key_count == len(KEY_HOMES)

    @property
    def chances_left(self) -> int:
        return MAX_CHANCES - self.caught_count

    def objective(self) -> str:
        if not self.read_note:
            return "Someone left a note on the table in the Grand Hall."
        if self.key_count < len(KEY_HOMES):
            return f"Find the keys in the East Wing  ({self.key_count}/{len(KEY_HOMES)})"
        if not self.has_can:
            return "Find the watering can by the glasshouse."
        if not self.orchid_watered:
            return "Water the orchid in the glasshouse."
        if not self.escaped:
            return "The front door is open. Leave."
        return ""

    def take_key(self, key_id: str) -> str:
        self.keys.add(key_id)
        return KEY_NAMES[key_id]
