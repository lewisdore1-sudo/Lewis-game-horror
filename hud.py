"""On-screen text and menus (Panda3D DirectGUI)."""
from __future__ import annotations

from direct.gui.DirectGui import DirectFrame
from direct.gui.OnscreenText import OnscreenText
from panda3d.core import TextNode, TransparencyAttrib

INK = (0.86, 0.83, 0.76, 1)
DIM = (0.55, 0.57, 0.55, 1)
RED = (0.82, 0.28, 0.3, 1)


class Fader:
    """Text that fades in, holds, then fades out."""

    def __init__(self, text: OnscreenText):
        self.text = text
        self.t = 0.0
        self.hold = 0.0
        self.text.setTransparency(TransparencyAttrib.MAlpha)
        self.text.setAlphaScale(0.0)

    def show(self, s: str, hold: float = 3.5):
        self.text.setText(s)
        self.t = 0.0
        self.hold = hold

    def update(self, dt):
        if self.hold <= 0:
            self.text.setAlphaScale(0.0)
            return
        self.t += dt
        fade_in, fade_out = 0.4, 1.0
        if self.t < fade_in:
            a = self.t / fade_in
        elif self.t < fade_in + self.hold:
            a = 1.0
        elif self.t < fade_in + self.hold + fade_out:
            a = 1.0 - (self.t - fade_in - self.hold) / fade_out
        else:
            a = 0.0
            self.hold = 0.0
        self.text.setAlphaScale(a)


class HUD:
    def __init__(self, app, font, title_font):
        self.app = app
        kw = dict(font=font, mayChange=True, shadow=(0, 0, 0, 0.85))
        self.objective = OnscreenText(text="", parent=app.a2dTopLeft, pos=(0.09, -0.11), scale=0.04,
                                      fg=INK, align=TextNode.ALeft, **kw)
        self.keys = OnscreenText(text="", parent=app.a2dTopRight, pos=(-0.09, -0.11), scale=0.036,
                                 fg=DIM, align=TextNode.ARight, **kw)
        self.prompt = OnscreenText(text="", parent=app.a2dBottomCenter, pos=(0, 0.2), scale=0.045,
                                   fg=INK, align=TextNode.ACenter, **kw)
        self.dot = OnscreenText(text="+", parent=app.aspect2d, pos=(0, -0.012), scale=0.035,
                                fg=(1, 1, 1, 0.35), align=TextNode.ACenter, font=font)
        self.stamina = OnscreenText(text="", parent=app.a2dBottomCenter, pos=(0, 0.1), scale=0.03,
                                    fg=DIM, align=TextNode.ACenter, **kw)
        self.message = Fader(OnscreenText(text="", parent=app.aspect2d, pos=(0, 0.3), scale=0.055,
                                          fg=INK, align=TextNode.ACenter, wordwrap=26, **kw))
        self.area = Fader(OnscreenText(text="", parent=app.a2dBottomLeft, pos=(0.09, 0.12), scale=0.05,
                                       fg=DIM, align=TextNode.ALeft, **{**kw, "font": title_font}))

        # the note -------------------------------------------------------
        self.note = DirectFrame(parent=app.aspect2d, frameColor=(0.8, 0.76, 0.64, 0.97),
                                frameSize=(-0.66, 0.66, -0.86, 0.86))
        self.note_text = OnscreenText(text="", parent=self.note, pos=(-0.56, 0.72), scale=0.041,
                                      fg=(0.14, 0.1, 0.08, 1), align=TextNode.ALeft, wordwrap=27,
                                      font=font, mayChange=True)
        OnscreenText(text="[E]  put it down", parent=self.note, pos=(0, -0.8), scale=0.032,
                     fg=(0.3, 0.24, 0.2, 1), align=TextNode.ACenter, font=font)
        self.note.hide()

        # full-screen fade (drawn above the 3D view, below text) ---------
        self.fade = DirectFrame(parent=app.render2d, frameColor=(0, 0, 0, 1), frameSize=(-1, 1, -1, 1),
                                sortOrder=20)
        self.fade.setTransparency(TransparencyAttrib.MAlpha)
        self.fade.setBin("fixed", 20)
        self.fade_a = 1.0
        self.fade_target = 1.0
        self.fade_speed = 1.0

        # title ----------------------------------------------------------
        self.title = app.aspect2d.attachNewNode("title")
        OnscreenText(text="THE SHIFTING MANSION", parent=self.title, pos=(0, 0.3), scale=0.13,
                     fg=(0.88, 0.86, 0.8, 1), align=TextNode.ACenter, font=title_font, shadow=(0, 0, 0, 1))
        OnscreenText(text="The house changes when you aren't looking.", parent=self.title, pos=(0, 0.17),
                     scale=0.045, fg=DIM, align=TextNode.ACenter, font=font)
        self.title_prompt = OnscreenText(text="Press ENTER to begin", parent=self.title, pos=(0, -0.25),
                                         scale=0.05, fg=INK, align=TextNode.ACenter, font=font, mayChange=True)
        OnscreenText(text="WASD move   ·   mouse look   ·   SHIFT run   ·   E interact   ·   "
                          "F flashlight   ·   ESC pause",
                     parent=self.title, pos=(0, -0.42), scale=0.032, fg=DIM, align=TextNode.ACenter, font=font)
        OnscreenText(text="18+   ·   Psychological horror   ·   Jump scares   ·   Flashing lights   ·   "
                          "Disturbing themes",
                     parent=self.title, pos=(0, -0.8), scale=0.03, fg=RED, align=TextNode.ACenter, font=font)

        # big centre card (caught / game over / ending / pause) ------------
        self.card = app.aspect2d.attachNewNode("card")
        self.card_title = OnscreenText(text="", parent=self.card, pos=(0, 0.12), scale=0.09, fg=INK,
                                       align=TextNode.ACenter, font=title_font, mayChange=True, wordwrap=18)
        self.card_sub = OnscreenText(text="", parent=self.card, pos=(0, -0.12), scale=0.042, fg=DIM,
                                     align=TextNode.ACenter, font=font, mayChange=True, wordwrap=34)
        self.card.hide()

        self.show_play(False)

    # ------------------------------------------------------------------
    def show_play(self, on: bool):
        for w in (self.objective, self.keys, self.prompt, self.dot, self.stamina):
            w.show() if on else w.hide()

    def show_title(self, on: bool):
        self.title.show() if on else self.title.hide()

    def show_card(self, title: str | None, sub: str = "", color=INK):
        if title is None:
            self.card.hide()
            return
        self.card_title.setText(title)
        self.card_title.setFg(color)
        self.card_sub.setText(sub)
        self.card.show()

    def show_note(self, text: str | None):
        if text is None:
            self.note.hide()
        else:
            self.note_text.setText(text)
            self.note.show()

    def fade_to(self, alpha: float, speed: float = 1.0):
        self.fade_target = alpha
        self.fade_speed = speed

    def set_fade_color(self, r, g, b):
        self.fade["frameColor"] = (r, g, b, 1)

    def update(self, dt):
        self.message.update(dt)
        self.area.update(dt)
        d = self.fade_target - self.fade_a
        step = dt * self.fade_speed
        self.fade_a = self.fade_target if abs(d) <= step else self.fade_a + step * (1 if d > 0 else -1)
        self.fade.setAlphaScale(self.fade_a)
        if self.fade_a <= 0.001:
            self.fade.hide()
        else:
            self.fade.show()
