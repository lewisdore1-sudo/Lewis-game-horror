"""Headless smoke test: runs the whole game loop against a stubbed Panda3D.

This can't check rendering, but it executes every state, interaction and
per-frame code path, so typos and logic errors in the game code surface.
Run:  python tests/smoke_stub.py
"""
import math
import os
import sys
import tempfile
import types
from unittest.mock import MagicMock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


class StubModule(types.ModuleType):
    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        m = MagicMock(name=f"{self.__name__}.{name}")
        setattr(self, name, m)
        return m


for mod in ("panda3d", "panda3d.core", "direct", "direct.showbase", "direct.showbase.Audio3DManager",
            "direct.gui", "direct.gui.OnscreenText", "direct.gui.OnscreenImage", "direct.gui.DirectGui",
            "direct.filter", "direct.filter.CommonFilters", "direct.showbase.ShowBase"):
    sys.modules[mod] = StubModule(mod)

DT = 1 / 60
PRESSED = set()


class FakeShowBase:
    def __init__(self):
        self.render = MagicMock(name="render")
        self.render2d = MagicMock(name="render2d")
        self.aspect2d = MagicMock(name="aspect2d")
        for n in ("a2dTopLeft", "a2dTopRight", "a2dBottomCenter", "a2dBottomLeft"):
            setattr(self, n, MagicMock(name=n))
        self.camera = MagicMock(name="camera")
        self.cam = MagicMock(name="cam")
        self.camLens = MagicMock(name="camLens")
        self.loader = MagicMock(name="loader")
        self.win = MagicMock(name="win")
        self.win.getXSize.return_value = 1600
        self.win.getYSize.return_value = 900
        ptr = MagicMock()
        ptr.getX.return_value = 800
        ptr.getY.return_value = 450
        self.win.getPointer.return_value = ptr
        self.pipe = MagicMock()
        self.mouseWatcherNode = MagicMock()
        self.mouseWatcherNode.isButtonDown.side_effect = lambda k: k in PRESSED
        self.sfxManagerList = [MagicMock()]
        self.taskMgr = MagicMock()
        self.events = {}

    def accept(self, ev, fn, *a):
        self.events[ev] = fn

    def disableMouse(self):
        pass

    def setBackgroundColor(self, *a):
        pass

    def userExit(self):
        raise SystemExit

    def windowEvent(self, win):
        pass


sys.modules["direct.showbase.ShowBase"].ShowBase = FakeShowBase
core = sys.modules["panda3d.core"]
clock = MagicMock()
clock.getDt.return_value = DT
core.ClockObject.getGlobalClock.return_value = clock
# keyboard buttons: make them distinct hashable strings
core.KeyboardButton.asciiKey.side_effect = lambda c: f"key:{c}"
for n in ("up", "down", "left", "right", "shift", "lshift"):
    getattr(core.KeyboardButton, n).return_value = f"key:{n}"

from game.assets_gen import generate_all  # noqa: E402
from game.app import MansionApp  # noqa: E402
from game.layout import ROOM_DOOR_X  # noqa: E402
from game.rooms_data import KEY_HOMES, to_world  # noqa: E402

assets = os.path.join(tempfile.gettempdir(), "sm_assets")
generate_all(assets)
app = MansionApp({"shadows": True, "bloom": True}, assets)
task = MagicMock()


def run(seconds):
    for _ in range(int(seconds / DT)):
        app.update(task)


def face(x, y):
    p = app.player
    p.h = math.degrees(math.atan2(-(x - p.x), y - p.y))
    p.p = -20


def walk_to(x, y, max_s=40):
    """Crude autopilot: face the target and hold W."""
    PRESSED.add("key:w")
    t = 0
    while math.hypot(app.player.x - x, app.player.y - y) > 0.5 and t < max_s:
        if app.state != "play":
            break
        face(x, y)
        run(0.1)
        t += 0.1
    PRESSED.discard("key:w")


assert app.state == "title"
run(1)
app.on_enter()
assert app.state == "play"
run(0.5)

# read the note
walk_to(0, 6.4)
face(0, 8)
app.player.p = -35
tgt = app._interaction_target()
assert tgt and tgt.name == "note", tgt and tgt.name
app.on_interact()
assert app.state == "note"
app.on_interact()
assert app.state == "play" and app.progress.read_note

# route to the east wing
for wp in [(5, 7.75), (9.5, 7.75)]:
    walk_to(*wp)
print("in corridor at", round(app.player.x, 2), round(app.player.y, 2), app.last_area)
assert app.last_area == "corridor", app.last_area

# collect keys by visiting rooms until the house offers each one
visits = 0
while app.progress.key_count < 3 and visits < 60 and app.state in ("play",):
    slot = ("room_a", "room_b", "room_c")[visits % 3]
    dx = ROOM_DOOR_X[slot]
    walk_to(dx, 7.75)
    walk_to(dx, 10.3)
    lay = app.layouts[slot]
    if lay.key and lay.key.key_id not in app.progress.keys:
        kx, ky = to_world(slot, lay.key.lx, lay.key.ly)
        # approach the key
        for _ in range(60):
            it = app._interaction_target()
            if it and it.name.startswith("key_"):
                app.on_interact()
                break
            face(kx, ky)
            app.player.p = -math.degrees(math.atan2(1.65 - lay.key.z, math.hypot(kx - app.player.x, ky - app.player.y)))
            PRESSED.add("key:w")
            run(0.1)
            PRESSED.discard("key:w")
    walk_to(dx, 10.3)
    walk_to(dx, 7.75)
    face(dx, 2)                 # look away so the room can shift
    run(0.3)
    visits += 1
    if app.state == "caught":
        run(4.0)
        walk_to(5, 7.75)
        walk_to(9.5, 7.75)
print("keys", sorted(app.progress.keys), "visits", visits, "shifts", app.shifts.total_shifts,
      "caught", app.progress.caught_count, "state", app.state)

# exercise the remaining actions directly
app.state = "play"
app.take_can()
app.progress.keys |= set(KEY_HOMES)
app.water_orchid()
assert app.progress.front_door_open
app.try_west_door()
app.on_escape(); assert app.state == "paused"
app.on_escape(); assert app.state == "play"
app.start_caught(); run(4.0)
print("after caught:", app.state, "chances", app.progress.chances_left)
app.try_front_door()
run(5.0)
assert app.state == "ending", app.state
app.on_enter()
assert app.state == "title"
# game over path
app.on_enter()
for _ in range(3):
    app.state = "play"
    app.start_caught()
    run(4.0)
assert app.state == "gameover", app.state
print("SMOKE TEST PASSED")
