"""The shifting system: rooms change behind the player's back.

A room that the player has left is marked *pending*. It only changes once the
player is out of the room AND is not looking at its doorway (or is far away).
When it changes, the slot can take on a different identity and/or variant, so
"the study" may now be behind the door where the bedroom was.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from .layout import ROOM_SLOTS
from .rooms_data import IDENTITIES, KEY_HOMES, QUIET, VARIANTS

INITIAL = {
    "room_a": ("study", QUIET),
    "room_b": ("bedroom", QUIET),
    "room_c": ("gallery", QUIET),
}


@dataclass
class SlotState:
    identity: str
    variant: str
    inside: bool = False
    visited: bool = False
    pending: bool = False
    shifts: int = 0


@dataclass
class ShiftManager:
    seed: int = 0
    slots: dict[str, SlotState] = field(default_factory=dict)
    total_shifts: int = 0

    def __post_init__(self):
        self.rng = random.Random(self.seed)
        if not self.slots:
            self.slots = {s: SlotState(*INITIAL[s]) for s in ROOM_SLOTS}

    # ------------------------------------------------------------------
    def config(self, slot: str) -> tuple[str, str]:
        st = self.slots[slot]
        return st.identity, st.variant

    def showing(self) -> set[tuple[str, str]]:
        return {(s.identity, s.variant) for s in self.slots.values()}

    def choose_next(self, slot: str, keys_taken: set[str]) -> tuple[str, str]:
        others = {self.slots[s].identity for s in ROOM_SLOTS if s != slot}
        current = self.config(slot)
        wanted = {home for kid, home in KEY_HOMES.items()
                  if kid not in keys_taken and home not in self.showing()}
        options, weights = [], []
        for ident in IDENTITIES:
            if ident in others:
                continue
            for var in VARIANTS:
                cfg = (ident, var)
                if cfg == current:
                    continue
                options.append(cfg)
                # Bias toward configurations that still hold a key, so the
                # house is cruel but never impossible.
                weights.append(4.0 if cfg in wanted else 1.0)
        return self.rng.choices(options, weights)[0]

    # ------------------------------------------------------------------
    def update(self, player_area: str | None, doorway_visible: dict[str, bool],
               door_distance: dict[str, float], keys_taken: set[str]) -> list[str]:
        """Advance the state machine. Returns the slots that shifted this tick."""
        shifted = []
        for slot, st in self.slots.items():
            now_inside = player_area == slot
            if st.inside and not now_inside:
                st.pending = True
            if now_inside:
                st.visited = True
            st.inside = now_inside
            if st.pending and not now_inside:
                unseen = not doorway_visible.get(slot, False)
                far = door_distance.get(slot, 0.0) > 9.0
                if unseen or far:
                    st.identity, st.variant = self.choose_next(slot, keys_taken)
                    st.pending = False
                    st.shifts += 1
                    self.total_shifts += 1
                    shifted.append(slot)
        return shifted
