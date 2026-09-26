"""The game: states, input, and the per-frame loop (Panda3D)."""
from __future__ import annotations

import math
import os
import random

from direct.showbase.ShowBase import ShowBase
from panda3d.core import AntialiasAttrib, ClockObject, Filename, KeyboardButton, WindowProperties

from .audio import Audio
from .fx import FX
from .hud import HUD, RED
from .layout import EYE_H, PLAYER_START, ROOM_DOOR_X, ROOM_SLOTS, area_at, sight_rects, solid_rects
from .materials import Materials
from .objectives import Progress
from .physics import angle_to, line_clear
from .player import Player
from .rooms_data import HALL_NOTE, HALL_STAGE_TEXT, KEY_NAMES, colliders, hall_colliders, room_layout, to_world
from .shifting import ShiftManager
from .walker import WalkerVisual
from .walker_ai import WalkerBrain
from .world import World

AREA_TITLES = {
    "hall": "THE GRAND HALL", "corridor": "THE EAST WING", "room_a": "THE EAST WING",
    "room_b": "THE EAST WING", "room_c": "THE EAST WING", "garden": "THE BOTANICAL GARDEN",
    "glasshouse": "THE GLASSHOUSE",
}
SURFACE = {"hall": "stone", "corridor": "wood", "room_a": "wood", "room_b": "wood", "room_c": "wood",
           "garden": "grass", "glasshouse": "stone"}
CAUGHT_LINES = ["IT WAS ALREADY BEHIND YOU.", "YOU LOOKED AWAY.", "IT DOESN'T NEED A FACE TO FIND YOU."]
FONT_CANDIDATES = [
    r"C:\Windows\Fonts\georgia.ttf", r"C:\Windows\Fonts\constan.ttf", r"C:\Windows\Fonts\cambria.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
]
TITLE_FONT_CANDIDATES = [
    r"C:\Windows\Fonts\GARA.TTF", r"C:\Windows\Fonts\constan.ttf", r"C:\Windows\Fonts\georgia.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
]


class Interactable:
    def __init__(self, name, pos, prompt, action, enabled=lambda: True, reach=2.5):
        self.name, self.pos, self.prompt, self.action, self.enabled, self.reach = name, pos, prompt, action, enabled, reach


class MansionApp(ShowBase):
    def __init__(self, settings: dict, asset_dir: str):
        ShowBase.__init__(self)
        self.settings = settings
        self.asset_dir = asset_dir
        self.clock = ClockObject.getGlobalClock()
        self.disableMouse()
        self.setBackgroundColor(0, 0, 0, 1)
        self.render.setShaderAuto()
        self.render.setAntialias(AntialiasAttrib.MAuto)
        self.camLens.setFov(settings.get("fov", 78))
        self.camLens.setNearFar(0.05, 500)
        self.aspect2d.setBin("fixed", 40)

        self.mats = Materials(self.loader, asset_dir, settings.get("anisotropy", 8))
        font = self._font(FONT_CANDIDATES)
        title_font = self._font(TITLE_FONT_CANDIDATES)
        self.world = World(self, self.mats, settings)
        self.walker_vis = WalkerVisual(self.world.root, self.mats)
        self.walker_vis.np.setLight(self.world.amb_in)
        self.player = Player(self, self.world.root, settings)
        self.fx = FX(self, self.mats, settings)
        self.hud = HUD(self, font, title_font)
        self.audio = Audio(self, asset_dir, self.walker_vis.np, settings.get("volume", 0.8))

        self.keys_map = {
            "fwd": [KeyboardButton.asciiKey("w"), KeyboardButton.up()],
            "back": [KeyboardButton.asciiKey("s"), KeyboardButton.down()],
            "left": [KeyboardButton.asciiKey("a"), KeyboardButton.left()],
            "right": [KeyboardButton.asciiKey("d"), KeyboardButton.right()],
            "sprint": [KeyboardButton.shift(), KeyboardButton.lshift()],
        }
        self.accept("escape", self.on_escape)
        self.accept("enter", self.on_enter)
        self.accept("e", self.on_interact)
        self.accept("mouse1", self.on_interact)
        self.accept("f", self.on_flashlight)
        self.accept("q", self.on_quit_key)
        self.accept("f11", self.toggle_fullscreen)
        self.accept("window-event", self.on_window_event)

        self.state = "title"
        self.state_t = 0.0
        self.mouse_skip = 2
        self.new_game()
        self.hud.show_title(True)
        self.hud.fade_to(0.35, 0.6)
        self.set_mouse_captured(False)
        self.taskMgr.add(self.update, "update")

    # ==================================================================
    def _font(self, candidates):
        for path in candidates:
            if os.path.exists(path):
                try:
                    f = self.loader.loadFont(Filename.fromOsSpecific(path))
                    f.setPixelsPerUnit(90)
                    return f
                except Exception:
                    continue
        return None

    def set_mouse_captured(self, on: bool):
        props = WindowProperties()
        props.setCursorHidden(on)
        if hasattr(WindowProperties, "M_confined"):
            props.setMouseMode(WindowProperties.M_confined if on else WindowProperties.M_absolute)
        self.win.requestProperties(props)
        self.mouse_captured = on
        self.mouse_skip = 2

    def toggle_fullscreen(self):
        props = WindowProperties()
        fs = not self.win.getProperties().getFullscreen()
        props.setFullscreen(fs)
        if fs:
            props.setSize(self.pipe.getDisplayWidth(), self.pipe.getDisplayHeight())
        self.win.requestProperties(props)
        self.mouse_skip = 3

    def on_window_event(self, win):
        if win != self.win:
            return
        self.windowEvent(win)          # keep ShowBase's own handling (resize, close)
        if not win.getProperties().getForeground() and self.state == "play":
            self.pause(True)

    # ==================================================================
    # Game setup
    # ==================================================================
    def new_game(self):
        seed = random.randrange(1 << 30)
        self.progress = Progress()
        self.shifts = ShiftManager(seed=seed)
        self.brain = WalkerBrain(seed=seed + 1)
        self.layouts = {}
        for slot in ROOM_SLOTS:
            self._rebuild_room(slot)
        self.world.build_hall_stage(0)
        self.world.build_orchid(False, 0)
        self.world.build_can(True)
        self.world.set_garden_stage(0)
        self.world.open_front_door(0.0)
        self.walker_vis.show(False)
        self.player.reset(*PLAYER_START)
        self.player.flash_on = True
        self.visited_areas = set()
        self.told = set()
        self.dread = 0.0
        self.grace = 0.0
        self.last_area = None
        self._recompute_colliders()
        self._build_interactables()
        self.hud.show_note(None)
        self.hud.show_card(None)

    def _rebuild_room(self, slot):
        ident, var = self.shifts.config(slot)
        seed = self.shifts.slots[slot].shifts + ROOM_SLOTS.index(slot) * 7
        lay = room_layout(ident, var, seed)
        self.layouts[slot] = lay
        self.world.build_room(slot, lay, self.progress.keys, seed)

    def _recompute_colliders(self):
        extra = hall_colliders(self.progress.hall_stage)
        for slot in ROOM_SLOTS:
            extra += colliders(slot, self.layouts[slot])
        self.solid = solid_rects(extra)
        self.sight = sight_rects()

    # ------------------------------------------------------------------
    def _build_interactables(self):
        P = self.progress
        self.interactables = [
            Interactable("note", (0.0, 8.0, 0.8), lambda: "[E]  Read the note", self.read_note),
            Interactable("front", (0.0, 0.2, 1.4),
                         lambda: "[E]  Leave" if P.front_door_open else "[E]  Try the front door",
                         self.try_front_door, reach=2.6),
            Interactable("west", (-7.6, 7.75, 1.4), lambda: "[E]  Try the West Wing door", self.try_west_door,
                         reach=2.6),
            Interactable("can", (2.4, 31.1, 0.25), lambda: "[E]  Take the watering can", self.take_can,
                         enabled=lambda: not P.has_can),
            Interactable("orchid", (0.0, 40.0, 1.4), lambda: "[E]  Water the orchid" if P.has_can
                         else "[E]  Look at the orchid", self.water_orchid,
                         enabled=lambda: not P.orchid_watered),
        ]

    def _key_interactables(self):
        out = []
        for slot in ROOM_SLOTS:
            lay = self.layouts[slot]
            if lay.key and lay.key.key_id not in self.progress.keys and self.world.slot_key_np[slot] is not None:
                x, y = to_world(slot, lay.key.lx, lay.key.ly)
                kid = lay.key.key_id
                out.append(Interactable(f"key_{slot}", (x, y, lay.key.z), lambda k=kid: f"[E]  Take the {KEY_NAMES[k]}",
                                        lambda s=slot, k=kid: self.take_key(s, k), reach=2.6))
        return out

    # ==================================================================
    # Actions
    # ==================================================================
    def read_note(self):
        self.audio.play("paper", 0.8)
        self.hud.show_note(HALL_NOTE)
        self.state = "note"

    def close_note(self):
        self.hud.show_note(None)
        self.audio.play("paper", 0.6, 0.9)
        self.state = "play"
        if not self.progress.read_note:
            self.progress.read_note = True
            self.hud.message.show("The East Wing is through the door on your right.", 4.0)

    def take_key(self, slot, key_id):
        name = self.progress.take_key(key_id)
        self.world.take_key(slot)
        self.audio.play("key", 0.9)
        n = self.progress.key_count
        self.world.build_hall_stage(self.progress.hall_stage)
        self.world.set_garden_stage(self.progress.garden_stage)
        self._recompute_colliders()
        if n == 1:
            self.hud.message.show(f"You took the {name}.\nSomething in the house has noticed.", 4.5)
            self.brain.active = True
            self.brain.spawn_away(self.player.x, self.player.y, self.player.h, self.sight, False, min_d=16)
            self.walker_vis.show(True)
            self.audio.play("shift", 0.6)
        elif n == 2:
            self.hud.message.show(f"You took the {name}.\nFar away, a door you didn't open closes.", 4.5)
            self.audio.play("shift", 0.7)
        else:
            self.hud.message.show(f"You took the {name}.\nThe house is quiet now. Too quiet.", 4.5)
            self.audio.play("shift", 0.8, 0.8)

    def try_front_door(self):
        if self.progress.front_door_open:
            self.start_escape()
        else:
            self.audio.play("locked", 0.9)
            self.hud.message.show("Locked. It has never been unlocked from this side.", 3.0)

    def try_west_door(self):
        self.audio.play("locked", 0.9, 0.85)
        self.hud.message.show("The West Wing is chained shut.\nNot yet.", 3.0)

    def take_can(self):
        self.progress.has_can = True
        self.world.build_can(False)
        self.audio.play("click", 0.6, 0.6)
        self.hud.message.show("A watering can. Still half full.", 3.0)

    def water_orchid(self):
        P = self.progress
        if P.key_count < 3:
            self.hud.message.show("A single orchid, somehow still alive.\nThe note said: the keys first.", 3.5)
            return
        if not P.has_can:
            self.hud.message.show("The soil is bone dry. There was a watering can by the door.", 3.5)
            return
        P.orchid_watered = True
        self.audio.play("water", 0.9)
        self.world.build_orchid(True, P.garden_stage)
        self.world.set_garden_stage(P.garden_stage)
        self.hud.message.show("The orchid drinks.\nSomewhere in the house, a lock turns.", 5.0)

    # ==================================================================
    # States
    # ==================================================================
    def on_enter(self):
        if self.state == "title":
            self.state = "play"
            self.state_t = 0.0
            self.player.flash_on = True
            self.player.flicker = 1.0
            self.hud.show_title(False)
            self.hud.show_play(True)
            self.hud.fade_to(0.0, 0.8)
            self.set_mouse_captured(True)
            self.hud.message.show("Someone left the lights on.", 3.0)
        elif self.state in ("gameover", "ending"):
            self.new_game()
            self.state = "title"
            self.hud.show_card(None)
            self.hud.set_fade_color(0, 0, 0)
            self.hud.show_title(True)
            self.hud.show_play(False)
            self.hud.fade_to(0.35, 0.6)
            self.set_mouse_captured(False)

    def on_escape(self):
        if self.state == "play":
            self.pause(True)
        elif self.state == "paused":
            self.pause(False)
        elif self.state == "note":
            self.close_note()
        elif self.state == "title":
            self.userExit()

    def on_quit_key(self):
        if self.state == "paused":
            self.userExit()

    def pause(self, on: bool):
        if on and self.state == "play":
            self.state = "paused"
            self.hud.show_card("PAUSED", "ESC  resume      ·      Q  quit to desktop")
            self.set_mouse_captured(False)
            self.audio.silence()
        elif not on and self.state == "paused":
            self.state = "play"
            self.hud.show_card(None)
            self.set_mouse_captured(True)

    def on_flashlight(self):
        if self.state == "play":
            self.player.toggle_flash()
            self.audio.play("click", 0.7)

    def on_interact(self):
        if self.state == "note":
            self.close_note()
            return
        if self.state != "play":
            return
        target = self._interaction_target()
        if target:
            target.action()

    def start_caught(self):
        self.state = "caught"
        self.state_t = 0.0
        self.progress.caught_count += 1
        self.audio.play("caught", 1.0)
        self.audio.silence()
        self.fx.red_flash(0.9)
        self.player.shake = 1.2
        self.hud.show_play(False)

    def start_escape(self):
        self.state = "escape"
        self.state_t = 0.0
        self.audio.play("door_open", 1.0)
        self.hud.show_play(False)

    # ==================================================================
    # Frame update
    # ==================================================================
    def _down(self, action) -> bool:
        is_down = self.mouseWatcherNode.isButtonDown
        return any(is_down(k) for k in self.keys_map[action])

    def _mouse_delta(self):
        if not self.mouse_captured:
            return 0.0, 0.0
        cx, cy = self.win.getXSize() // 2, self.win.getYSize() // 2
        md = self.win.getPointer(0)
        dx, dy = md.getX() - cx, md.getY() - cy
        self.win.movePointer(0, cx, cy)
        if self.mouse_skip > 0:
            self.mouse_skip -= 1
            return 0.0, 0.0
        return dx, dy

    def _interaction_target(self):
        px, py = self.player.x, self.player.y
        ex, ey, ez = px, py, EYE_H
        hr, pr = math.radians(self.player.h), math.radians(self.player.p)
        fx, fy, fz = -math.sin(hr) * math.cos(pr), math.cos(hr) * math.cos(pr), math.sin(pr)
        best, best_a = None, 26.0
        for it in self.interactables + self._key_interactables():
            if not it.enabled():
                continue
            vx, vy, vz = it.pos[0] - ex, it.pos[1] - ey, it.pos[2] - ez
            d = math.sqrt(vx * vx + vy * vy + vz * vz)
            if d > it.reach or d < 1e-3:
                continue
            if not line_clear(px, py, it.pos[0], it.pos[1], self.sight):
                continue
            cos_a = max(-1.0, min(1.0, (vx * fx + vy * fy + vz * fz) / d))
            a = math.degrees(math.acos(cos_a))
            if a < best_a:
                best, best_a = it, a
        return best

    def update(self, task):
        dt = min(self.clock.getDt(), 1 / 20)
        self.state_t += dt
        getattr(self, f"_update_{self.state}", self._update_idle)(dt)
        self.world.update(dt)
        self.hud.update(dt)
        self.audio.update(dt)
        return task.cont

    def _update_idle(self, dt):
        pass

    def _update_title(self, dt):
        t = self.state_t * 0.06
        self.camera.setPos(math.sin(t) * 3.5, 3.5 + math.cos(t * 0.7) * 1.2, 2.2)
        self.camera.lookAt(0, 9, 1.8 + math.sin(t * 1.3) * 0.3)
        self.player.flash_on = False
        self.player.flicker = 0.0
        self.player.spot.setColor((0, 0, 0, 1))
        self.audio.set_loop("hum_loop", 0.12)
        self.audio.set_loop("drone_loop", 0.35)
        self.audio.set_loop("tick_loop", 0.18)
        self.fx.update(dt, 0.2, False, 0)

    def _update_note(self, dt):
        self.player.apply_camera(self.camera, dt)
        self.fx.update(dt, self.dread * 0.5, False, self.progress.garden_stage)

    def _update_paused(self, dt):
        pass

    def _update_play(self, dt):
        P = self.progress
        P.time_played += dt
        pl = self.player

        dx, dy = self._mouse_delta()
        pl.look(dx, dy, self.settings.get("mouse_sensitivity", 0.12), self.settings.get("invert_y", False))
        fwd = (1 if self._down("fwd") else 0) - (1 if self._down("back") else 0)
        strafe = (1 if self._down("right") else 0) - (1 if self._down("left") else 0)
        speed = pl.move(dt, fwd, strafe, self._down("sprint"), self.solid)
        area = area_at(pl.x, pl.y) or self.last_area
        if pl.step_due(dt, speed):
            self.audio.step(SURFACE.get(area, "wood"), 0.35 + 0.15 * (speed > 3))

        # ------------------------------------------------ area changes
        if area != self.last_area:
            self._entered(area)
            self.last_area = area

        # ------------------------------------------------ the shifting house
        vis, dist = {}, {}
        for slot in ROOM_SLOTS:
            doorx = ROOM_DOOR_X[slot]
            dist[slot] = math.hypot(pl.x - doorx, pl.y - 9.0)
            vis[slot] = angle_to(pl.x, pl.y, pl.h, doorx, 9.0) < 52 and line_clear(pl.x, pl.y, doorx, 9.0, self.sight)
        shifted = self.shifts.update(area, vis, dist, P.keys)
        if shifted:
            for slot in shifted:
                self._rebuild_room(slot)
            self._recompute_colliders()
            if random.random() < 0.35 and min(dist[s] for s in shifted) < 14:
                self.audio.play("creak", 0.35, random.uniform(0.8, 1.1))

        # ------------------------------------------------ the Walker
        b = self.brain
        events = []
        if b.active:
            if self.grace > 0:
                self.grace -= dt
            else:
                events = b.update(dt, pl.x, pl.y, pl.h, pl.flash_on, P.key_count, self.solid, self.sight)
        wdist = math.hypot(b.x - pl.x, b.y - pl.y)
        for ev in events:
            if ev == "spotted":
                self.audio.play("sting", 0.85)
                self.fx.red_flash(0.25)
                pl.shake = max(pl.shake, 0.5)
            elif ev == "teleported" and wdist < 14:
                self.audio.walker_creak()
            elif ev == "caught":
                self.start_caught()
                return
        self.walker_vis.update(dt, b)
        self.audio.walker_sounds(b.moving, b.active, wdist)

        # ------------------------------------------------ dread
        target = 0.0
        if b.active:
            target = max(0.0, min(1.0, 1.0 - (wdist - 2.0) / 12.0))
            if b.seen:
                target = min(1.0, target + 0.25)
        self.dread += (target - self.dread) * min(1.0, dt * 1.5)
        # the flashlight falters when it is close
        if self.dread > 0.55 and random.random() < dt * 3 * self.dread:
            pl.flicker = random.choice((0.0, 0.15, 0.4))
        pl.flicker += (1.0 - pl.flicker) * min(1.0, dt * 6)

        # ------------------------------------------------ ambience
        outdoors = area in ("garden", "glasshouse")
        self.audio.set_loop("hum_loop", 0.0 if outdoors else (0.28 if area == "corridor" else 0.14))
        self.audio.set_loop("wind_loop", 0.55 if outdoors else 0.06)
        self.audio.set_loop("drone_loop", 0.25 + 0.6 * self.dread)
        self.audio.set_loop("heartbeat_loop", max(0.0, (self.dread - 0.35) * 1.4))
        tick = max(0.0, 1.0 - math.hypot(pl.x + 7.4, pl.y - 5.4) / 9.0) * 0.5
        self.audio.set_loop("tick_loop", tick)

        # ------------------------------------------------ HUD
        target_it = self._interaction_target()
        self.hud.prompt.setText(target_it.prompt() if target_it else "")
        self.hud.objective.setText(P.objective())
        keys_txt = "KEYS   " + "   ".join(KEY_NAMES[k].replace(" Key", "") if k in P.keys else "?"
                                          for k in ("brass", "bone", "clock"))
        self.hud.keys.setText(keys_txt + ("" if P.chances_left >= 3 else f"\nCHANCES   {'I ' * P.chances_left}"))
        self.hud.stamina.setText("" if pl.stamina > 0.98 else "|" * max(1, int(pl.stamina * 24)))

        pl.apply_camera(self.camera, dt)
        self.fx.update(dt, self.dread, outdoors, P.garden_stage)

    def _entered(self, area):
        P = self.progress
        title = AREA_TITLES.get(area)
        if title and title not in self.visited_areas:
            self.visited_areas.add(title)
            self.hud.area.show(title, 2.5)
        if area in ROOM_SLOTS:
            st = self.shifts.slots[area]
            if st.shifts > 0 and "shifted" not in self.told:
                self.told.add("shifted")
                self.hud.message.show("This isn't the room you left.", 3.0)
            elif st.variant == "night" and "night" not in self.told:
                self.told.add("night")
                self.hud.message.show("Something has been here.", 3.0)
        if area == "garden":
            if P.garden_stage == 0 and "garden0" not in self.told:
                self.told.add("garden0")
                self.hud.message.show("Cold air. Open sky.\nIt feels safer out here.", 3.5)
            elif P.garden_stage >= 2 and "garden2" not in self.told:
                self.told.add("garden2")
                self.hud.message.show("The garden is dying.\nIt isn't safe out here any more.", 3.5)
        if area == "hall" and P.hall_stage > 0 and f"hall{P.hall_stage}" not in self.told:
            self.told.add(f"hall{P.hall_stage}")
            self.hud.message.show(HALL_STAGE_TEXT[P.hall_stage], 3.5)

    def _update_caught(self, dt):
        t = self.state_t
        pl, b = self.player, self.brain
        # the camera is dragged round to face it, and it is right there
        want = math.degrees(math.atan2(-(b.x - pl.x), b.y - pl.y))
        dh = (want - pl.h + 180) % 360 - 180
        pl.h += dh * min(1.0, dt * 10)
        pl.p += (8 - pl.p) * min(1.0, dt * 8)
        d = math.hypot(b.x - pl.x, b.y - pl.y)
        if d > 0.55:
            b.x += (pl.x - b.x) / d * dt * 3
            b.y += (pl.y - b.y) / d * dt * 3
        b.seen = True
        self.walker_vis.update(dt, b)
        pl.apply_camera(self.camera, dt)
        self.fx.update(dt, 1.0, False, self.progress.garden_stage)
        if t > 0.55 and self.hud.fade_target < 1:
            self.hud.set_fade_color(0, 0, 0)
            self.hud.fade_to(1.0, 8.0)
            if self.progress.chances_left > 0:
                self.hud.show_card(random.choice(CAUGHT_LINES), f"{self.progress.chances_left} chance"
                                   f"{'s' if self.progress.chances_left != 1 else ''} left", RED)
            else:
                self.state = "gameover"
                self.hud.show_card("THE HOUSE KEEPS YOU.",
                                   "You were caught three times.\n\nPress ENTER to try again.", RED)
                self.set_mouse_captured(False)
                return
        if t > 3.6:
            self.hud.show_card(None)
            pl.reset(*PLAYER_START)
            pl.h = 0.0
            b.spawn_away(pl.x, pl.y, pl.h, self.sight, b.garden_allowed(self.progress.key_count), min_d=18)
            b.seen = False
            self.grace = 4.0
            self.dread = 0.0
            self.hud.fade_to(0.0, 0.7)
            self.hud.show_play(True)
            self.state = "play"
            self.state_t = 0.0
            self.hud.message.show("The Grand Hall. Again.", 2.5)

    def _update_gameover(self, dt):
        pass

    def _update_escape(self, dt):
        t = self.state_t
        pl = self.player
        self.world.open_front_door(min(1.0, t / 2.2))
        pl.h += ((180 - pl.h + 180) % 360 - 180) * min(1.0, dt * 2)
        pl.p += (0 - pl.p) * min(1.0, dt * 2)
        if t > 1.2:
            pl.y -= dt * 0.8
        pl.apply_camera(self.camera, dt)
        self.fx.update(dt, 0.0, False, self.progress.garden_stage)
        if t > 1.5 and self.hud.fade_target < 1:
            self.hud.set_fade_color(0.82, 0.84, 0.86)
            self.hud.fade_to(1.0, 0.45)
            self.audio.silence()
        if t > 4.2 and self.state == "escape":
            self.hud.set_fade_color(0, 0, 0)
            self.state = "ending"
            P = self.progress
            m, s = divmod(int(P.time_played), 60)
            self.hud.show_card("YOU LEFT.\nTHE HOUSE STAYS.",
                               f"Time inside: {m}m {s:02d}s     ·     Rooms that moved: {self.shifts.total_shifts}"
                               f"     ·     Times caught: {P.caught_count}\n\nPress ENTER to return to the title.")
            self.set_mouse_captured(False)

    def _update_ending(self, dt):
        pass
