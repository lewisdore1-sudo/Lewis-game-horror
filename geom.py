"""Procedural mesh building.

`Mesh` collects vertices in plain Python lists (so its winding/normals can be
unit-tested without Panda3D); `Mesh.node()` turns it into a Panda3D GeomNode
with normals, UVs, tangents and binormals for normal mapping.

All faces are counter-clockwise when seen from the side their normal points to
(Panda3D's front-face convention).
"""
from __future__ import annotations

import math

Vec = tuple[float, float, float]


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _norm(a):
    L = math.sqrt(_dot(a, a)) or 1.0
    return (a[0] / L, a[1] / L, a[2] / L)


# face key -> (normal, u axis, v axis) with u × v = normal
FACES = {
    "X": ((1, 0, 0), (0, 1, 0), (0, 0, 1)),
    "x": ((-1, 0, 0), (0, -1, 0), (0, 0, 1)),
    "Y": ((0, 1, 0), (-1, 0, 0), (0, 0, 1)),
    "y": ((0, -1, 0), (1, 0, 0), (0, 0, 1)),
    "Z": ((0, 0, 1), (1, 0, 0), (0, 1, 0)),
    "z": ((0, 0, -1), (1, 0, 0), (0, -1, 0)),
}
ALL_FACES = "XxYyZz"


class Mesh:
    def __init__(self):
        self.pos: list[Vec] = []
        self.nrm: list[Vec] = []
        self.uv: list[tuple[float, float]] = []
        self.tan: list[Vec] = []
        self.bin: list[Vec] = []
        self.idx: list[int] = []

    def __len__(self):
        return len(self.idx) // 3

    def _v(self, p, n, uv, t, b) -> int:
        self.pos.append(p)
        self.nrm.append(n)
        self.uv.append(uv)
        self.tan.append(t)
        self.bin.append(b)
        return len(self.pos) - 1

    def quad(self, ps, n, t, b, uvs):
        i = [self._v(ps[k], n, uvs[k], t, b) for k in range(4)]
        self.idx += [i[0], i[1], i[2], i[0], i[2], i[3]]

    # ------------------------------------------------------------------
    def box(self, x0, y0, z0, x1, y1, z1, tile: float = 1.0, faces: str = ALL_FACES,
            uv_world: bool = True):
        """Axis-aligned box. UVs are in world metres / tile so textures line up
        across neighbouring boxes. uv_world=False maps each face 0..1."""
        lo, hi = (min(x0, x1), min(y0, y1), min(z0, z1)), (max(x0, x1), max(y0, y1), max(z0, z1))
        c = ((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, (lo[2] + hi[2]) / 2)
        half = ((hi[0] - lo[0]) / 2, (hi[1] - lo[1]) / 2, (hi[2] - lo[2]) / 2)
        for f in faces:
            n, u, v = FACES[f]
            hn = abs(_dot(n, half))
            hu = abs(_dot(u, half))
            hv = abs(_dot(v, half))
            fc = (c[0] + n[0] * hn, c[1] + n[1] * hn, c[2] + n[2] * hn)
            ps, uvs = [], []
            for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                p = (fc[0] + u[0] * hu * su + v[0] * hv * sv,
                     fc[1] + u[1] * hu * su + v[1] * hv * sv,
                     fc[2] + u[2] * hu * su + v[2] * hv * sv)
                ps.append(p)
                if uv_world:
                    uvs.append((_dot(p, u) / tile, _dot(p, v) / tile))
                else:
                    uvs.append(((su + 1) / 2, (sv + 1) / 2))
            self.quad(ps, n, u, v, uvs)

    def cylinder(self, cx, cy, z0, r0, r1, h, segs=16, caps=True, tile=1.0):
        """Vertical (tapered) cylinder; r1 = 0 makes a cone."""
        slope = (r0 - r1) / h if h else 0.0
        for i in range(segs):
            a0, a1 = math.tau * i / segs, math.tau * (i + 1) / segs
            ps, uvs = [], []
            for a, r, z in ((a0, r0, z0), (a1, r0, z0), (a1, r1, z0 + h), (a0, r1, z0 + h)):
                ps.append((cx + math.cos(a) * r, cy + math.sin(a) * r, z))
                uvs.append((a * max(r0, r1) / tile, z / tile))
            am = (a0 + a1) / 2
            n = _norm((math.cos(am), math.sin(am), slope))
            t = (-math.sin(am), math.cos(am), 0.0)
            self.quad(ps, n, t, _cross(n, t), uvs)
        if caps:
            for z, r, up in ((z0 + h, r1, True), (z0, r0, False)):
                if r <= 0:
                    continue
                n = (0, 0, 1) if up else (0, 0, -1)
                c = self._v((cx, cy, z), n, (0.5, 0.5), (1, 0, 0), (0, 1 if up else -1, 0))
                ring = []
                for i in range(segs):
                    a = math.tau * i / segs
                    ring.append(self._v((cx + math.cos(a) * r, cy + math.sin(a) * r, z), n,
                                        (0.5 + math.cos(a) * 0.5, 0.5 + math.sin(a) * 0.5),
                                        (1, 0, 0), (0, 1 if up else -1, 0)))
                for i in range(segs):
                    a, b = ring[i], ring[(i + 1) % segs]
                    self.idx += [c, a, b] if up else [c, b, a]

    def sphere(self, cx, cy, cz, r, segs=16, rings=10, scale=(1.0, 1.0, 1.0), inside=False, tile=None):
        sx, sy, sz = scale
        grid = []
        for j in range(rings + 1):
            phi = -math.pi / 2 + math.pi * j / rings
            row = []
            for i in range(segs + 1):
                th = math.tau * i / segs
                d = (math.cos(phi) * math.cos(th), math.cos(phi) * math.sin(th), math.sin(phi))
                p = (cx + d[0] * r * sx, cy + d[1] * r * sy, cz + d[2] * r * sz)
                n = _norm((d[0] / sx, d[1] / sy, d[2] / sz))
                if inside:
                    n = (-n[0], -n[1], -n[2])
                t = (-math.sin(th), math.cos(th), 0.0)
                uv = (i / segs, j / rings) if tile is None else (th * r / tile, phi * r / tile)
                row.append(self._v(p, n, uv, t, _cross(n, t)))
            grid.append(row)
        for j in range(rings):
            for i in range(segs):
                a, b, c, d = grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]
                if inside:
                    self.idx += [a, c, b, a, d, c]
                else:
                    self.idx += [a, b, c, a, c, d]

    def prism_roof(self, x0, y0, x1, y1, z0, rise, tile=2.0):
        """Gable roof with the ridge running along X."""
        ym = (y0 + y1) / 2
        zr = z0 + rise
        for (ya, yb), sign in (((y0, ym), -1), ((y1, ym), 1)):
            ps = [(x0, ya, z0), (x1, ya, z0), (x1, yb, zr), (x0, yb, zr)]
            e1, e2 = _sub(ps[1], ps[0]), _sub(ps[3], ps[0])
            n = _norm(_cross(e1, e2))
            if (sign == -1 and n[1] > 0) or (sign == 1 and n[1] < 0) or n[2] < 0:
                ps = [ps[1], ps[0], ps[3], ps[2]]
                n = _norm(_cross(_sub(ps[1], ps[0]), _sub(ps[3], ps[0])))
            L = math.hypot(ym - ya, rise)
            t = _norm(_sub(ps[1], ps[0]))
            uvs = [(ps[0][0] / tile, 0), (ps[1][0] / tile, 0), (ps[2][0] / tile, L / tile), (ps[3][0] / tile, L / tile)]
            self.quad(ps, n, t, _cross(n, t), uvs)
        for x, n in ((x0, (-1, 0, 0)), (x1, (1, 0, 0))):
            a = self._v((x, y0, z0), n, (y0 / tile, 0), (0, 1, 0), (0, 0, 1))
            b = self._v((x, y1, z0), n, (y1 / tile, 0), (0, 1, 0), (0, 0, 1))
            c = self._v((x, ym, zr), n, (ym / tile, rise / tile), (0, 1, 0), (0, 0, 1))
            self.idx += [a, c, b] if n[0] < 0 else [a, b, c]

    # ------------------------------------------------------------------
    def node(self, name: str = "mesh"):
        """Build a Panda3D NodePath. Imported lazily so tests don't need Panda3D."""
        from panda3d.core import (Geom, GeomNode, GeomTriangles, GeomVertexArrayFormat, GeomVertexData,
                                  GeomVertexFormat, GeomVertexWriter, InternalName, NodePath)
        global _FORMAT
        if _FORMAT is None:
            arr = GeomVertexArrayFormat()
            arr.addColumn(InternalName.getVertex(), 3, Geom.NTFloat32, Geom.CPoint)
            arr.addColumn(InternalName.getNormal(), 3, Geom.NTFloat32, Geom.CNormal)
            arr.addColumn(InternalName.getTexcoord(), 2, Geom.NTFloat32, Geom.CTexcoord)
            arr.addColumn(InternalName.getTangent(), 3, Geom.NTFloat32, Geom.CVector)
            arr.addColumn(InternalName.getBinormal(), 3, Geom.NTFloat32, Geom.CVector)
            fmt = GeomVertexFormat()
            fmt.addArray(arr)
            _FORMAT = GeomVertexFormat.registerFormat(fmt)
        vdata = GeomVertexData(name, _FORMAT, Geom.UHStatic)
        prim = GeomTriangles(Geom.UHStatic)
        prim.setIndexType(Geom.NTUint32)
        if not _fast_fill(vdata, prim, self):
            vdata = GeomVertexData(name, _FORMAT, Geom.UHStatic)
            prim = GeomTriangles(Geom.UHStatic)
            prim.setIndexType(Geom.NTUint32)
            self._slow_fill(vdata, prim)
        geom = Geom(vdata)
        geom.addPrimitive(prim)
        gn = GeomNode(name)
        gn.addGeom(geom)
        return NodePath(gn)

    def _slow_fill(self, vdata, prim):
        from panda3d.core import GeomVertexWriter, InternalName
        vdata.uncleanSetNumRows(len(self.pos))
        wv = GeomVertexWriter(vdata, InternalName.getVertex())
        wn = GeomVertexWriter(vdata, InternalName.getNormal())
        wt = GeomVertexWriter(vdata, InternalName.getTexcoord())
        wtan = GeomVertexWriter(vdata, InternalName.getTangent())
        wbin = GeomVertexWriter(vdata, InternalName.getBinormal())
        for p, n, uv, t, b in zip(self.pos, self.nrm, self.uv, self.tan, self.bin):
            wv.setData3(*p)
            wn.setData3(*n)
            wt.setData2(*uv)
            wtan.setData3(*t)
            wbin.setData3(*b)
        idx = self.idx
        for k in range(0, len(idx), 3):
            prim.addVertices(idx[k], idx[k + 1], idx[k + 2])


_FORMAT = None
_FAST_OK = True


def _fast_fill(vdata, prim, mesh) -> bool:
    """Copy all vertices/indices in one go through the buffer protocol.
    Falls back to the (slower) writer path if this Panda3D build refuses."""
    global _FAST_OK
    if not _FAST_OK:
        return False
    try:
        import numpy as np
        n = len(mesh.pos)
        arr = np.empty((n, 14), dtype=np.float32)
        arr[:, 0:3] = mesh.pos
        arr[:, 3:6] = mesh.nrm
        arr[:, 6:8] = mesh.uv
        arr[:, 8:11] = mesh.tan
        arr[:, 11:14] = mesh.bin
        vdata.uncleanSetNumRows(n)
        vmv = memoryview(vdata.modifyArray(0)).cast("B")
        data = arr.tobytes()
        if vmv.nbytes != len(data):
            raise ValueError("unexpected vertex stride")
        vmv[:] = data
        idx = np.asarray(mesh.idx, dtype=np.uint32).tobytes()
        parr = prim.modifyVertices()
        parr.uncleanSetNumRows(len(mesh.idx))
        pmv = memoryview(parr).cast("B")
        if pmv.nbytes != len(idx):
            raise ValueError("unexpected index size")
        pmv[:] = idx
        return True
    except Exception as exc:          # older/odd builds: use the writer path from now on
        print("Fast mesh upload unavailable, using slow path:", exc)
        _FAST_OK = False
        return False


class MeshSet:
    """One Mesh per material name, turned into one child node per material."""

    def __init__(self):
        self.meshes: dict[str, Mesh] = {}

    def __getitem__(self, mat: str) -> Mesh:
        if mat not in self.meshes:
            self.meshes[mat] = Mesh()
        return self.meshes[mat]

    def build(self, parent, materials, name="set"):
        root = parent.attachNewNode(name)
        for mat, mesh in self.meshes.items():
            if len(mesh) == 0:
                continue
            np_ = mesh.node(f"{name}:{mat}")
            np_.reparentTo(root)
            materials.apply(np_, mat)
        return root
