"""Texture + material library (Panda3D)."""
from __future__ import annotations

import os

from panda3d.core import (Filename, Material, SamplerState, Texture, TextureStage, TransparencyAttrib)

# name -> (texture file or None, shininess, specular, colour tint, transparent)
MATERIALS = {
    "damask": ("damask", 12, 0.12, (1, 1, 1, 1), False),
    "wall_study": ("wall_study", 10, 0.1, (1, 1, 1, 1), False),
    "wall_rose": ("wall_rose", 10, 0.1, (1, 1, 1, 1), False),
    "wall_gallery": ("wall_gallery", 12, 0.12, (1, 1, 1, 1), False),
    "wall_parlour": ("wall_parlour", 10, 0.1, (1, 1, 1, 1), False),
    "stone": ("stone", 6, 0.05, (1, 1, 1, 1), False),
    "marble": ("marble", 70, 0.55, (1, 1, 1, 1), False),
    "wood": ("wood", 40, 0.3, (1, 1, 1, 1), False),
    "wood_dark": ("wood_dark", 50, 0.35, (1, 1, 1, 1), False),
    "carpet": ("carpet", 4, 0.02, (1, 1, 1, 1), False),
    "plaster": ("plaster", 4, 0.03, (1, 1, 1, 1), False),
    "panel": ("panel", 40, 0.3, (1, 1, 1, 1), False),
    "grass": ("grass", 6, 0.05, (1, 1, 1, 1), False),
    "hedge": ("hedge", 8, 0.08, (1, 1, 1, 1), False),
    "gravel": ("gravel", 8, 0.06, (1, 1, 1, 1), False),
    "tile": ("tile", 30, 0.2, (1, 1, 1, 1), False),
    "fabric_red": ("fabric_red", 6, 0.05, (1, 1, 1, 1), False),
    "fabric_linen": ("fabric_linen", 6, 0.05, (1, 1, 1, 1), False),
    "fabric_green": ("fabric_green", 6, 0.05, (1, 1, 1, 1), False),
    "bark": ("bark", 4, 0.03, (1, 1, 1, 1), False),
    "leaves": ("hedge", 10, 0.1, (0.85, 1.0, 0.8, 1), False),
    "brass": (None, 90, 0.9, (0.62, 0.48, 0.22, 1), False),
    "iron": (None, 60, 0.5, (0.08, 0.085, 0.09, 1), False),
    "glass": (None, 120, 1.0, (0.55, 0.7, 0.72, 0.16), True),
    "water": (None, 120, 1.0, (0.03, 0.05, 0.06, 0.85), True),
    "paper": (None, 4, 0.02, (0.82, 0.78, 0.66, 1), False),
    "black": (None, 30, 0.25, (0.012, 0.012, 0.014, 1), False),
    "terracotta": ("tile", 10, 0.05, (1.0, 0.9, 0.85, 1), False),
    "soil": ("gravel", 2, 0.0, (0.35, 0.25, 0.18, 1), False),
    "petal": (None, 20, 0.2, (0.92, 0.78, 0.86, 1), False),
    "canvas_back": ("wood_dark", 10, 0.05, (0.7, 0.62, 0.5, 1), False),
    "roof": ("stone", 8, 0.05, (0.45, 0.45, 0.5, 1), False),
    "bone": (None, 30, 0.3, (0.86, 0.83, 0.74, 1), False),
    "ceramic": (None, 80, 0.6, (0.86, 0.86, 0.82, 1), False),
    "green_metal": (None, 50, 0.45, (0.12, 0.22, 0.16, 1), False),
    "glass_dark": (None, 128, 1.0, (0.05, 0.06, 0.065, 1), False),
    # unlit emissive surfaces (bulbs, flames, embers) — these feed the bloom
    "glow_warm": (None, 0, 0, (1.6, 1.15, 0.6, 1), False),
    "glow_red": (None, 0, 0, (1.5, 0.25, 0.18, 1), False),
    "glow_ember": (None, 0, 0, (1.4, 0.45, 0.12, 1), False),
    "glow_white": (None, 0, 0, (1.2, 1.25, 1.3, 1), False),
    "glow_green": (None, 0, 0, (0.55, 1.0, 0.6, 1), False),
}


class Materials:
    def __init__(self, loader, asset_dir: str, anisotropy: int = 8):
        self.loader = loader
        self.dir = asset_dir
        self.aniso = anisotropy
        self._tex: dict[str, Texture] = {}
        self._mat: dict[str, Material] = {}
        self.normal_stage = TextureStage("normal")
        self.normal_stage.setMode(TextureStage.MNormal)

    def tex(self, name: str) -> Texture:
        if name not in self._tex:
            path = Filename.fromOsSpecific(os.path.join(self.dir, name + ".png"))
            t = self.loader.loadTexture(path)
            t.setMinfilter(SamplerState.FT_linear_mipmap_linear)
            t.setMagfilter(SamplerState.FT_linear)
            t.setAnisotropicDegree(self.aniso)
            self._tex[name] = t
        return self._tex[name]

    def clamp_tex(self, name: str) -> Texture:
        t = self.tex(name)
        t.setWrapU(SamplerState.WM_clamp)
        t.setWrapV(SamplerState.WM_clamp)
        return t

    def material(self, name: str) -> Material:
        if name not in self._mat:
            texname, shin, spec, col, _ = MATERIALS[name]
            m = Material(name)
            base = (1, 1, 1, 1) if texname else col      # textured tints go through colour scale
            m.setDiffuse(base)
            m.setAmbient(base)
            m.setSpecular((spec, spec, spec, 1))
            m.setShininess(shin)
            self._mat[name] = m
        return self._mat[name]

    def apply(self, np_, name: str, normal: bool = True):
        texname, _, _, col, transparent = MATERIALS[name]
        if name.startswith("glow"):
            np_.setLightOff(1)
            np_.setTextureOff(1)
            np_.setMaterialOff(1)
            np_.setColor(col)
            return
        np_.setMaterial(self.material(name), 1)
        if texname:
            np_.setTexture(TextureStage.getDefault(), self.tex(texname), 1)
            if normal:
                np_.setTexture(self.normal_stage, self.tex(texname + "_n"), 1)
            if col != (1, 1, 1, 1):
                np_.setColorScale(col)
        else:
            np_.setTextureOff(1)
            np_.setColor(col)
        if transparent:
            np_.setTransparency(TransparencyAttrib.MAlpha)
            np_.setDepthWrite(False)
            np_.setBin("transparent", 10)
            np_.setTwoSided(True)
