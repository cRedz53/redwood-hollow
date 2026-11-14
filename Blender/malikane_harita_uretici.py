# Malikane haritasi - Blender blockout uretici (Blender 4.2+ / 5.x)
#
# Calistirma (depo kok klasorunden):
#   blender -b -P Blender/malikane_harita_uretici.py -- Blender/Cikti
# veya Blender > Scripting sekmesinde acip "Run Script".
# Cikti: Malikane_Harita.blend, Onizlemeler/*.png, UE_Aktarim/ (FBX + scene.json)
#
# Olcek: 1 Blender birimi = 1 metre.
# Harita ~200 m x 110 m, cevresi tas kaideli siyah demir cit, 2 demir kapi
# (bati: giris kapisi, guney: kacis kapisi), dogu tarafta 2 katli buyuk malikane
# (merdivenli sutunlu giris, balkon, camli pencereler, avizeler), bahcede 7 kulube,
# cam / mese agaclari ve calilar. Gece atmosferi.

import bpy
import bmesh
import json
import math
import os
import random
import sys
from mathutils import Matrix, Vector

random.seed(7)

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT_DIR = argv[0] if argv else (os.path.dirname(bpy.data.filepath) or os.path.expanduser("~"))
os.makedirs(OUT_DIR, exist_ok=True)

# ---------------------------------------------------------------- layout
MAP_HW, MAP_HH, MAP_R = 100.0, 55.0, 20.0     # cit sinirinin yari genislik / yari yukseklik / kose yaricapi
FENCE_H, KERB_H = 2.6, 0.45

GATES = {
    "Giris_Kapisi": {"pos": Vector((-MAP_HW, 24.0)), "width": 9.0, "open": 0.35},
    "Kacis_Kapisi": {"pos": Vector((35.0, -MAP_HH)), "width": 10.0, "open": 0.0},
}

MANSION_MIN = Vector((18.0, -38.0))
MANSION_MAX = Vector((62.0, 42.0))
BASE_Z = 1.5        # malikane kaidesi (merdivenle cikilir)
FLOOR_H = 5.0
MANSION_DOOR_Y = 2.0
STAIR_FOOT_X = MANSION_MIN.x - 12.0

# (x, y, genislik, derinlik, donus derecesi) - kapi yerel -Y tarafinda
HUTS = [
    (-74.0, 39.0, 8.0, 6.5, -90),
    (-33.0, 36.0, 7.0, 6.0, 180),
    (-2.0, 42.0, 7.0, 6.0, 180),
    (-40.0, -2.0, 9.0, 7.5, 0),
    (-65.0, -40.0, 7.0, 6.0, 90),
    (-15.0, -32.0, 6.5, 5.5, 45),
    (-86.0, -8.0, 7.5, 6.0, -90),
]

PATHS = [  # cakil yollar (polyline)
    [Vector((-MAP_HW, 24.0)), Vector((-60.0, 18.0)), Vector((-20.0, 5.0)), Vector((STAIR_FOOT_X, MANSION_DOOR_Y))],
    [Vector((STAIR_FOOT_X - 1, MANSION_DOOR_Y)), Vector((0.0, -46.0)), Vector((35.0, -48.0)), Vector((35.0, -MAP_HH))],
]
PATH_W = 3.5
UV_TILE = 2.0       # metre / doku tekrari (Megascans yuzeyleri ~2 m x 2 m)


# ---------------------------------------------------------------- scene reset
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
scene.unit_settings.scale_length = 1.0


def collection(name):
    col = bpy.data.collections.new(name)
    scene.collection.children.link(col)
    return col


def material(name, color, rough=0.85, metal=0.0, emit=None, emit_strength=0.0, glass=False):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    if emit:
        bsdf.inputs["Emission Color"].default_value = (*emit, 1.0)
        bsdf.inputs["Emission Strength"].default_value = emit_strength
    if glass:
        bsdf.inputs["Alpha"].default_value = 0.25
        m["glass"] = True
    m.diffuse_color = (*color, 1.0)
    return m


M = {
    "grass": material("M_Grass", (0.03, 0.06, 0.022)),
    "gravel": material("M_Gravel", (0.17, 0.15, 0.12)),
    "stone": material("M_Stone", (0.24, 0.23, 0.21)),
    "iron": material("M_Iron", (0.015, 0.015, 0.015), rough=0.45, metal=1.0),
    "plaster": material("M_MansionWall", (0.36, 0.33, 0.29)),
    "trim": material("M_Trim", (0.55, 0.53, 0.49), rough=0.6),
    "column": material("M_Column", (0.55, 0.52, 0.47), rough=0.6),
    "floor": material("M_WoodFloor", (0.11, 0.06, 0.035), rough=0.5),
    "roof": material("M_Roof", (0.05, 0.05, 0.06), rough=0.7),
    "wood": material("M_HutWood", (0.14, 0.09, 0.055)),
    "door": material("M_DoorWood", (0.08, 0.04, 0.02), rough=0.55),
    "frame": material("M_WindowFrame", (0.6, 0.58, 0.55), rough=0.5),
    "glass": material("M_Glass", (0.02, 0.03, 0.035), rough=0.05, glass=True),
    "brass": material("M_Brass", (0.6, 0.42, 0.18), rough=0.35, metal=1.0),
    "trunk": material("M_TreeTrunk", (0.07, 0.045, 0.03)),
    "pine": material("M_PineLeaves", (0.012, 0.05, 0.02)),
    "oak": material("M_OakLeaves", (0.025, 0.055, 0.015)),
    "bush": material("M_Bush", (0.02, 0.045, 0.015)),
    "lamp": material("M_LampGlow", (1.0, 0.7, 0.4), emit=(1.0, 0.6, 0.25), emit_strength=15.0),
    "fire": material("M_Fire", (1.0, 0.4, 0.1), emit=(1.0, 0.35, 0.08), emit_strength=25.0),
    "marble_w": material("M_MarbleWhite", (0.78, 0.76, 0.72), rough=0.15),
    "marble_b": material("M_MarbleBlack", (0.025, 0.025, 0.025), rough=0.15),
    "carpet": material("M_Carpet", (0.22, 0.015, 0.02), rough=0.95),
    "rug_border": material("M_RugBorder", (0.3, 0.18, 0.05), rough=0.9),
    "velvet": material("M_Velvet", (0.16, 0.01, 0.02), rough=0.8),
    "dark_wood": material("M_DarkWood", (0.05, 0.025, 0.012), rough=0.35),
    "upholstery": material("M_Upholstery", (0.1, 0.02, 0.025), rough=0.85),
    "lacquer": material("M_Lacquer", (0.008, 0.008, 0.008), rough=0.08),
    "linen": material("M_Linen", (0.7, 0.67, 0.6), rough=0.9),
    "canvas": material("M_Canvas", (0.06, 0.045, 0.03), rough=0.7),
    "book_r": material("M_BookRed", (0.2, 0.03, 0.02), rough=0.6),
    "book_g": material("M_BookGreen", (0.03, 0.1, 0.05), rough=0.6),
    "book_b": material("M_BookBrown", (0.12, 0.06, 0.025), rough=0.6),
}


class Builder:
    """Collects primitives into one bmesh, then writes a single object."""

    def __init__(self):
        self.bm = bmesh.new()
        self.bm.loops.layers.uv.verify()

    def _tag(self, before, mi):
        for f in self.bm.faces:
            if f not in before:
                f.material_index = mi

    def box(self, center, size, rot_z=0.0, mi=0):
        before = set(self.bm.faces)
        mat = Matrix.Translation(Vector(center)) @ Matrix.Rotation(rot_z, 4, 'Z') @ Matrix.Diagonal((*size, 1.0))
        bmesh.ops.create_cube(self.bm, size=1.0, matrix=mat, calc_uvs=True)
        self._tag(before, mi)

    def cone(self, center, r1, r2, depth, segments=8, mi=0):
        before = set(self.bm.faces)
        bmesh.ops.create_cone(self.bm, cap_ends=True, segments=segments, radius1=r1, radius2=r2,
                              depth=depth, matrix=Matrix.Translation(Vector(center)), calc_uvs=True)
        self._tag(before, mi)

    def cyl(self, center, r, depth, segments=16, mi=0):
        self.cone(center, r, r, depth, segments, mi)

    def beam(self, p0, p1, w, h, mi=0):
        """Box from p0 to p1 (any direction), w x h cross-section — sloped rails, posts."""
        p0, p1 = Vector(p0), Vector(p1)
        d = p1 - p0
        rot = d.to_track_quat('X', 'Z').to_matrix().to_4x4()
        before = set(self.bm.faces)
        mat = Matrix.Translation((p0 + p1) / 2) @ rot @ Matrix.Diagonal((d.length, w, h, 1.0))
        bmesh.ops.create_cube(self.bm, size=1.0, matrix=mat, calc_uvs=True)
        self._tag(before, mi)

    def blob(self, center, radius, squash=1.0, mi=0, subdiv=1):
        before = set(self.bm.faces)
        mat = Matrix.Translation(Vector(center)) @ Matrix.Diagonal((1.0, 1.0, squash, 1.0))
        bmesh.ops.create_icosphere(self.bm, subdivisions=subdiv, radius=radius, matrix=mat, calc_uvs=True)
        self._tag(before, mi)

    def prism_roof(self, center, sx, sy, z0, height, rot_z=0.0, mi=0):
        """Gable roof, ridge along local Y."""
        before = set(self.bm.faces)
        hx, hy = sx / 2, sy / 2
        local = [(-hx, -hy, 0), (hx, -hy, 0), (hx, hy, 0), (-hx, hy, 0), (0, -hy, height), (0, hy, height)]
        mat = Matrix.Translation(Vector((center[0], center[1], z0))) @ Matrix.Rotation(rot_z, 4, 'Z')
        v = [self.bm.verts.new(mat @ Vector(p)) for p in local]
        for idx in [(0, 1, 4), (2, 3, 5), (0, 4, 5, 3), (1, 2, 5, 4), (0, 3, 2, 1)]:
            self.bm.faces.new([v[i] for i in idx])
        self._tag(before, mi)

    def wall(self, a, b, height, thick, openings=(), base_z=0.0, mi=0):
        """Straight wall from a to b (2D). openings: (offset_along, width, z_bottom, z_top)."""
        a, b = Vector(a), Vector(b)
        d = b - a
        length = d.length
        if length < 1e-4:
            return
        d.normalize()
        rot = math.atan2(d.y, d.x)

        def piece(s0, s1, z0, z1):
            if s1 - s0 < 1e-3 or z1 - z0 < 1e-3:
                return
            p = a + d * ((s0 + s1) / 2)
            self.box((p.x, p.y, base_z + (z0 + z1) / 2), (s1 - s0, thick, z1 - z0), rot, mi)

        cursor = 0.0
        for off, w, zb, zt in sorted(openings):
            s0, s1 = max(0.0, off - w / 2), min(length, off + w / 2)
            piece(cursor, s0, 0, height)
            piece(s0, s1, 0, zb)
            piece(s0, s1, zt, height)
            cursor = s1
        piece(cursor, length, 0, height)

    def box_uvs(self):
        """Box-project UVs in metres (1 UV unit = UV_TILE m) so real textures tile at true scale."""
        uv = self.bm.loops.layers.uv.verify()
        self.bm.normal_update()
        for f in self.bm.faces:
            n = f.normal
            axis = max(range(3), key=lambda i: abs(n[i]))
            ui, vi = ((1, 2), (0, 2), (0, 1))[axis]
            for loop in f.loops:
                co = loop.vert.co
                loop[uv].uv = (co[ui] / UV_TILE, co[vi] / UV_TILE)

    def finish(self, name, mats, col, location=(0, 0, 0), rot_z=0.0):
        me = bpy.data.meshes.new(name)
        bmesh.ops.remove_doubles(self.bm, verts=self.bm.verts, dist=1e-5)
        self.box_uvs()
        self.bm.to_mesh(me)
        self.bm.free()
        for m in mats:
            me.materials.append(m)
        ob = bpy.data.objects.new(name, me)
        ob.location = location
        ob.rotation_euler.z = rot_z
        col.objects.link(ob)
        return ob


def add_window(fb, gb, a, b, s, w, zb, zt, base_z, thick, mullions=True):
    """Frame (fb) + glass pane (gb) for an opening cut by Builder.wall at offset s."""
    a, b = Vector(a), Vector(b)
    d = (b - a).normalized()
    rot = math.atan2(d.y, d.x)
    p = a + d * s
    h, ft, depth = zt - zb, 0.1, thick + 0.08
    zc = base_z + (zb + zt) / 2
    for off in (-w / 2 + ft / 2, w / 2 - ft / 2):  # jambs
        q = p + d * off
        fb.box((q.x, q.y, zc), (ft, depth, h), rot)
    fb.box((p.x, p.y, base_z + zt - ft / 2), (w, depth, ft), rot)          # head
    fb.box((p.x, p.y, base_z + zb + ft / 2), (w, depth, ft), rot)          # bottom rail
    n = Vector((-d.y, d.x))
    for side in (-1, 1):                                                     # sill + lintel, both faces
        q = p + n * side * (thick / 2 + 0.06)
        fb.box((q.x, q.y, base_z + zb - 0.06), (w + 0.3, 0.16, 0.12), rot)
        fb.box((q.x, q.y, base_z + zt + 0.15), (w + 0.4, 0.14, 0.3), rot)
    if mullions:
        fb.box((p.x, p.y, zc), (0.06, thick * 0.5, h), rot)
        fb.box((p.x, p.y, base_z + zb + h * 0.62), (w, thick * 0.5, 0.06), rot)
    gb.box((p.x, p.y, zc), (w - 2 * ft, 0.03, h - 2 * ft), rot)


C_LIGHTS = collection("Isiklar")
C_PROTO = collection("Prototipler")


# ---------------------------------------------------------------- doors (leaf meshes: hinge at origin, leaf along +X)
def door(name, mesh_ob, hinge, ext, inward, col, partner=None, angle=90.0, locked=False):
    """Openable door leaf. ext: direction the closed leaf points from its hinge; inward: side it swings to."""
    ext, inward = Vector(ext).normalized(), Vector(inward)
    ob = bpy.data.objects.new(name, mesh_ob.data)
    ob.location = hinge
    ob.rotation_euler.z = math.atan2(ext.y, ext.x)
    ob["door_open"] = math.copysign(angle, ext.x * inward.y - ext.y * inward.x)
    ob["door_locked"] = locked
    if partner:
        ob["door_partner"] = partner
    col.objects.link(ob)
    return ob


def raised_panel(b, x0, x1, z0, z1, t, mi=0, frame_mi=0):
    """Raised panel with a moulded frame on both faces of a leaf of thickness t."""
    w, h = x1 - x0, z1 - z0
    cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
    for s in (-1, 1):
        y = s * (t / 2 + 0.01)
        b.box((cx, y, z1 - 0.02), (w, 0.02, 0.04), mi=frame_mi)
        b.box((cx, y, z0 + 0.02), (w, 0.02, 0.04), mi=frame_mi)
        b.box((x0 + 0.02, y, cz), (0.04, 0.02, h), mi=frame_mi)
        b.box((x1 - 0.02, y, cz), (0.04, 0.02, h), mi=frame_mi)
        b.box((cx, s * (t / 2 + 0.008), cz), (w - 0.16, 0.016, h - 0.16), mi=mi)


def leaf_hardware(b, w, h, t, mi):
    for z in (0.3, h / 2, h - 0.3):                               # hinges
        b.box((0.015, 0, z), (0.03, t + 0.02, 0.12), mi=mi)
    for s in (-1, 1):                                             # lever handles with back plates
        y = s * (t / 2 + 0.01)
        b.box((w - 0.1, y, 1.05), (0.05, 0.02, 0.24), mi=mi)
        b.box((w - 0.16, s * (t / 2 + 0.05), 1.1), (0.14, 0.025, 0.025), mi=mi)


def panel_leaf(name, w, h, t, rows, glass_top=False):
    """Classic panelled leaf; mats: wood, brass, glass."""
    b = Builder()
    b.box((w / 2, 0, h / 2), (w, t, h))
    z, gap = 0.18, 0.14
    usable = h - 0.18 - 0.18 - gap * (len(rows) - 1)
    for k, frac in enumerate(rows):
        ph = usable * frac
        if glass_top and k == len(rows) - 1:
            b.box((w / 2, 0, z + ph / 2), (w - 0.3, t + 0.004, ph - 0.1), mi=2)
            for s in (-1, 1):                                     # glazing bars
                b.box((w / 2, s * (t / 2 + 0.01), z + ph / 2), (0.04, 0.02, ph - 0.1), mi=0)
        else:
            raised_panel(b, 0.15, w - 0.15, z, z + ph, t)
        z += ph + gap
    leaf_hardware(b, w, h, t, 1)
    return b.finish(name, [M["door"], M["brass"], M["glass"]], C_PROTO)


def french_leaf(name, w, h, t):
    """Glazed balcony door leaf: stiles, rails and a 2 x 4 grid of panes."""
    b = Builder()
    st = 0.1
    for x in (st / 2, w - st / 2):
        b.box((x, 0, h / 2), (st, t, h))
    for z in (0.15, 0.7, h - 0.06):
        b.box((w / 2, 0, z), (w, t, 0.12 if z != 0.15 else 0.3))
    raised_panel(b, st, w - st, 0.02, 0.64, t)
    b.box((w / 2, 0, (0.76 + h - 0.12) / 2), (w - 2 * st, 0.012, h - 0.88), mi=2)
    b.box((w / 2, 0, (0.76 + h - 0.12) / 2), (0.03, t * 0.6, h - 0.88))
    for k in range(1, 4):
        b.box((w / 2, 0, 0.76 + k * (h - 0.88) / 4), (w - 2 * st, t * 0.6, 0.03))
    leaf_hardware(b, w, h, t, 1)
    return b.finish(name, [M["frame"], M["brass"], M["glass"]], C_PROTO)


def plank_leaf(name, w, h, t):
    """Rustic hut door: vertical planks, ledges and a Z brace, iron ring pull."""
    b = Builder()
    n = 6
    for k in range(n):
        pw = w / n
        b.box((pw * (k + 0.5), 0, h / 2), (pw - 0.008, t, h - 0.01 * (k % 2)))
    for z in (0.3, h - 0.3):
        b.box((w / 2, t / 2 + 0.02, z), (w - 0.06, 0.04, 0.14))
    b.beam((0.12, t / 2 + 0.02, 0.35), (w - 0.12, t / 2 + 0.02, h - 0.35), 0.12, 0.04)
    for z in (0.3, h - 0.3):                                      # strap hinges
        b.box((0.25, -(t / 2 + 0.01), z), (0.5, 0.02, 0.05), mi=1)
    b.box((w - 0.15, -(t / 2 + 0.02), 1.0), (0.03, 0.03, 0.16), mi=1)
    return b.finish(name, [M["wood"], M["iron"]], C_PROTO)


def door_casing(b, a, c, s, w, h, base_z, thick, depth=0.05, width=0.14, mi=0):
    """Moulded architrave around an opening, on both faces of the wall."""
    a, c = Vector(a), Vector(c)
    d = (c - a).normalized()
    n = Vector((-d.y, d.x))
    rot = math.atan2(d.y, d.x)
    p = a + d * s
    for side in (-1, 1):
        q = p + n * side * (thick / 2 + depth / 2)
        for off in (-(w / 2 + width / 2), w / 2 + width / 2):
            r = q + d * off
            b.box((r.x, r.y, base_z + (h + width) / 2), (width, depth, h + width), rot, mi)
        b.box((q.x, q.y, base_z + h + width / 2), (w + 2 * width, depth, width), rot, mi)
        b.box((q.x, q.y, base_z + h + width + 0.06), (w + 2 * width + 0.2, depth + 0.04, 0.12), rot, mi)


def point_light(name, loc, energy, color=(1.0, 0.6, 0.3), radius=0.15):
    ld = bpy.data.lights.new(name, 'POINT')
    ld.energy = energy
    ld.color = color
    ld.shadow_soft_size = radius
    ob = bpy.data.objects.new(name, ld)
    ob.location = loc
    C_LIGHTS.objects.link(ob)
    return ob


def slab_with_holes(b, rect, holes, z, t=0.2, mi=0):
    """Slab (top at z) covering rect = (x0, x1, y0, y1) minus rectangular holes."""
    x0, x1, y0, y1 = rect
    xs = sorted({x0, x1, *[v for h in holes for v in h[:2] if x0 < v < x1]})
    ys = sorted({y0, y1, *[v for h in holes for v in h[2:] if y0 < v < y1]})
    for xa, xb in zip(xs, xs[1:]):
        for ya, yb in zip(ys, ys[1:]):
            cx, cy = (xa + xb) / 2, (ya + yb) / 2
            if any(h[0] < cx < h[1] and h[2] < cy < h[3] for h in holes):
                continue
            b.box((cx, cy, z - t / 2), (xb - xa, yb - ya, t), mi=mi)


# ---------------------------------------------------------------- secret tunnel layout (world metres)
# A hatch in the floor of hut 7 opens onto steep stairs; the tunnel runs west under the fence
# and comes up through a second hatch outside the grounds.
TUNNEL_HUT = 7
TUN_Y, TUN_W = -10.0, 1.3            # tunnel centre line (y) and stair / hatch width
TUN_FLOOR, TUN_CEIL = -3.0, -0.7
STEP_R, STEP_T = 0.3, 0.28           # stair rise / tread
HATCH_L = 2.6                        # hatch length along the stairs (head-room on the way down)
ENTRY_X0 = -85.3                     # top step of the entry stairs (inside the hut)
HUT_FLOOR_Z = 0.3
EXIT_X0 = -112.0                     # foot of the exit stairs (outside the fence at x = -100)
ENTRY_HOLE = (ENTRY_X0 - HATCH_L, ENTRY_X0, TUN_Y - TUN_W / 2, TUN_Y + TUN_W / 2)
EXIT_HOLE = (EXIT_X0 - 2.8, EXIT_X0 - 0.2, TUN_Y - TUN_W / 2, TUN_Y + TUN_W / 2)

# ---------------------------------------------------------------- ground + paths
C_GROUND = collection("Zemin")
g = Builder()
slab_with_holes(g, (-200, 200, -150, 150), [ENTRY_HOLE, EXIT_HOLE], 0.0, 0.5)
g.finish("Zemin_Cim", [M["grass"]], C_GROUND)

p = Builder()
for line in PATHS:
    for a, b in zip(line, line[1:]):
        d = b - a
        mid = (a + b) / 2
        p.box((mid.x, mid.y, 0.02), (d.length + PATH_W, PATH_W, 0.04), math.atan2(d.y, d.x))
p.finish("Yol_Cakil", [M["gravel"]], C_GROUND)


# ---------------------------------------------------------------- boundary fence + gates
def rounded_rect(hw, hh, r, seg=12):
    pts = []
    corners = [((hw - r, hh - r), 0), ((-hw + r, hh - r), 90), ((-hw + r, -hh + r), 180), ((hw - r, -hh + r), 270)]
    for (cx, cy), start in corners:
        for i in range(seg + 1):
            ang = math.radians(start + 90 * i / seg)
            pts.append(Vector((cx + r * math.cos(ang), cy + r * math.sin(ang))))
    return pts


def fence(b, a, c, gaps, pillar_every=14.0):
    """Stone kerb + black iron picket fence with spear tips; stone pillars every N m."""
    a, c = Vector(a), Vector(c)
    d = c - a
    length = d.length
    if length < 1e-4:
        return
    d.normalize()
    rot = math.atan2(d.y, d.x)

    def blocked(s):
        return any(abs(s - g0) < gw / 2 for g0, gw in gaps)

    # kerb and rails as runs between gaps
    cuts = sorted((max(0.0, g0 - gw / 2), min(length, g0 + gw / 2)) for g0, gw in gaps)
    runs, cursor = [], 0.0
    for s0, s1 in cuts:
        runs.append((cursor, s0))
        cursor = s1
    runs.append((cursor, length))
    for s0, s1 in runs:
        if s1 - s0 < 1e-3:
            continue
        m = a + d * ((s0 + s1) / 2)
        b.box((m.x, m.y, KERB_H / 2), (s1 - s0, 0.5, KERB_H), rot, mi=1)
        for z in (KERB_H + 0.2, FENCE_H - 0.35):
            b.box((m.x, m.y, z), (s1 - s0, 0.05, 0.05), rot, mi=0)
    n = int(length / 0.14)
    for i in range(n + 1):
        s = i * length / max(n, 1)
        if blocked(s):
            continue
        q = a + d * s
        b.box((q.x, q.y, (KERB_H + FENCE_H) / 2), (0.025, 0.025, FENCE_H - KERB_H), rot, mi=0)
        b.cone((q.x, q.y, FENCE_H + 0.08), 0.035, 0.0, 0.16, 4, mi=0)
    k = int(length // pillar_every)
    for i in range(1, k + 1):
        s = i * length / (k + 1)
        if blocked(s) or any(abs(s - g0) < gw / 2 + 2 for g0, gw in gaps):
            continue
        q = a + d * s
        b.box((q.x, q.y, (FENCE_H + 0.3) / 2), (0.7, 0.7, FENCE_H + 0.3), rot, mi=1)
        b.box((q.x, q.y, FENCE_H + 0.38), (0.9, 0.9, 0.16), rot, mi=1)


C_WALLS = collection("Sinir_Cit")
fb_ = Builder()
outline = rounded_rect(MAP_HW, MAP_HH, MAP_R)
for a, b in zip(outline, outline[1:] + outline[:1]):
    d = b - a
    if d.length < 1e-4:
        continue
    gaps = []
    for gate in GATES.values():
        rel = gate["pos"] - a
        t = rel.dot(d.normalized())
        if 0 < t < d.length and abs(d.normalized().cross(rel)) < 0.1:
            gaps.append((t, gate["width"] + 2.6))  # +gate pillars
    fence(fb_, a, b, gaps)
fb_.finish("Sinir_Cit", [M["iron"], M["stone"]], C_WALLS)

C_GATES = collection("Kapilar")
for gname, gate in GATES.items():
    pos, width = gate["pos"], gate["width"]
    on_west = abs(pos.x + MAP_HW) < 0.1
    along = Vector((0, 1)) if on_west else Vector((1, 0))      # direction along the fence
    rot = math.atan2(along.y, along.x)

    pb = Builder()
    for side in (-1, 1):
        c = pos + along * side * (width / 2 + 0.65)
        pb.box((c.x, c.y, 2.0), (1.3, 1.3, 4.0), rot)
        pb.box((c.x, c.y, 4.1), (1.6, 1.6, 0.25), rot)
        pb.box((c.x, c.y, 4.5), (0.35, 0.35, 0.55), rot, mi=1)
        point_light(f"{gname}_Fener_{'L' if side < 0 else 'R'}", (c.x, c.y, 4.5), 250)
    pb.finish(f"{gname}_Sutunlar", [M["stone"], M["lamp"]], C_GATES)

    # two openable leaves (hinge at the pillars), arched so the top rises towards the centre
    leaf_w = width / 2
    lb = Builder()
    for z in (0.15, 1.6, 3.0):
        lb.box((leaf_w / 2, 0, z), (leaf_w, 0.08, 0.08))
    n_bars = int(leaf_w / 0.14)
    for i in range(n_bars + 1):
        x = i * leaf_w / n_bars
        top = 3.2 + 0.6 * (i / n_bars) ** 1.5
        lb.box((x, 0, top / 2), (0.03, 0.03, top))
        lb.cone((x, 0, top + 0.09), 0.04, 0.0, 0.18, 4)
    for i in range(1, n_bars, 2):                                 # scrollwork between the rails
        lb.blob((i * leaf_w / n_bars, 0, 2.3), 0.07, 1.6)
    lb.box((leaf_w - 0.06, 0, 1.6), (0.12, 0.12, 0.35))           # lock box
    leaf_proto = lb.finish(f"{gname}_Kanat", [M["iron"]], C_PROTO)
    inward = Vector((1, 0)) if on_west else Vector((0, 1))
    names = [f"{gname}_Kanat_L", f"{gname}_Kanat_R"]
    for side, nm, other in ((-1, names[0], names[1]), (1, names[1], names[0])):
        hinge = pos + along * side * leaf_w
        door(nm, leaf_proto, (hinge.x, hinge.y, 0), -side * along, inward, C_GATES, other, 80.0)


# ---------------------------------------------------------------- mansion
C_MANSION = collection("Malikane")
mx0, my0 = MANSION_MIN
mx1, my1 = MANSION_MAX
dy = MANSION_DOOR_Y
T = 0.5
Z1 = BASE_Z                  # zemin kat dosemesi
Z2 = BASE_Z + FLOOR_H        # ust kat dosemesi / balkon
TOTAL_H = BASE_Z + FLOOR_H * 2
DOOR_W, DOOR_H = 5.0, 4.5    # buyuk ana kapi
PORT_D, PORT_W = 8.0, 22.0   # sutunlu giris (portik) derinlik / genislik
STEP_N = 9
px0 = mx0 - PORT_D           # teras / balkon on kenari
STEP_RUN = (px0 - STAIR_FOOT_X) / (STEP_N - 1)
WIN_W, WIN_ZB, WIN_ZT = 1.8, 1.0, 3.8


def windows(length, skip=None):
    """Window openings every ~4.5 m. skip=(center, half_width) area kept clear."""
    ops = []
    n = int(length // 4.5)
    for i in range(n):
        s = (i + 0.5) * length / n
        if skip and abs(s - skip[0]) < skip[1]:
            continue
        ops.append((s, WIN_W, WIN_ZB, WIN_ZT))
    return ops


def balustrade(b, a, c, z, h=1.1, spacing=0.3, mi=0):
    a, c = Vector(a), Vector(c)
    d = c - a
    rot = math.atan2(d.y, d.x)
    mid = (a + c) / 2
    b.box((mid.x, mid.y, z + h - 0.08), (d.length, 0.3, 0.16), rot, mi)
    b.box((mid.x, mid.y, z + 0.08), (d.length, 0.3, 0.16), rot, mi)
    n = int(d.length / spacing)
    for i in range(1, n):
        q = a + d * (i / n)
        b.cyl((q.x, q.y, z + h / 2), 0.07, h - 0.3, 8, mi)


def curtain(cb, a, b, s, w, zt, base_z):
    """Two velvet drapes and a pelmet on the interior side of a window."""
    a, b = Vector(a), Vector(b)
    d = (b - a).normalized()
    rot = math.atan2(d.y, d.x)
    inward = -Vector((-d.y, d.x))  # walls run clockwise, so the left normal points outside
    p = a + d * s + inward * (T / 2 + 0.12)
    h = zt + 0.6
    for side in (-1, 1):
        q = p + d * side * (w / 2 + 0.2)
        cb.box((q.x, q.y, base_z + h / 2), (0.55, 0.14, h), rot)
        cb.box((q.x, q.y, base_z + 1.2), (0.6, 0.18, 0.08), rot, mi=1)  # brass tie-back
    cb.box((p.x, p.y, base_z + zt + 0.45), (w + 1.4, 0.2, 0.5), rot)


mw, wf, wg, cu = Builder(), Builder(), Builder(), Builder()
walls = [
    ((mx0, my0), (mx0, my1)),  # west (front, door)
    ((mx0, my1), (mx1, my1)),  # north
    ((mx1, my1), (mx1, my0)),  # east
    ((mx1, my0), (mx0, my0)),  # south
]
for idx, (a, b) in enumerate(walls):
    length = (Vector(b) - Vector(a)).length
    door_s = dy - my0 if idx == 0 else None
    for floor, z in enumerate((Z1, Z2)):
        ops = windows(length, (door_s, 4.0) if door_s is not None else None)
        mw.wall(a, b, FLOOR_H, T, ops + ([(door_s, DOOR_W, 0.0, DOOR_H)] if door_s is not None and floor == 0 else [])
                + ([(door_s, 2.8, 0.0, 3.6)] if door_s is not None and floor == 1 else []), z)
        for s, w, zb, zt in ops:
            add_window(wf, wg, a, b, s, w, zb, zt, z, T)
            curtain(cu, a, b, s, w, zt, z)

# parapet, cornices and corner quoins
for a, b in walls:
    mw.wall(a, b, 1.0, T, (), TOTAL_H)
    a, b = Vector(a), Vector(b)
    m, d = (a + b) / 2, b - a
    rot = math.atan2(d.y, d.x)
    for z, hgt, out in ((Z1 + 0.15, 0.3, 0.75), (Z2 - 0.1, 0.35, 0.8), (TOTAL_H - 0.1, 0.5, 0.95), (TOTAL_H + 1.0, 0.15, 0.75)):
        wf.box((m.x, m.y, z), (d.length + out, T + out - 0.5 + 0.2, hgt), rot)
for cx in (mx0, mx1):
    for cy in (my0, my1):
        wf.box((cx, cy, (Z1 + TOTAL_H) / 2), (1.0, 1.0, TOTAL_H - Z1))

# interior: double-height entrance hall with an imperial staircase facing the door,
# salon (north), dining room (south), library (east); bedrooms upstairs.
HALL_Y0, HALL_Y1 = dy - 12.0, dy + 12.0
HALL_X1 = mx0 + 28.0          # back wall of the hall
SX0 = mx0 + 16.0              # foot of the central flight
SX_L = mx0 + 22.0             # landing starts here
SX_B = mx0 + 26.0             # upper back gallery starts here
ZM = Z1 + FLOOR_H / 2         # landing height
for y in (HALL_Y0, HALL_Y1):
    mw.wall((mx0 + T / 2, y), (HALL_X1, y), FLOOR_H, 0.3, [(10.0, 2.6, 0, 3.6)], Z1)
    mw.wall((mx0 + T / 2, y), (HALL_X1, y), FLOOR_H, 0.3, [(8.0, 2.2, 0, 3.0)], Z2)
back_len = my1 - my0 - T
for z, doors in ((Z1, (dy - 20, dy + 20)), (Z2, (dy - 20, dy, dy + 20))):
    mw.wall((HALL_X1, my0 + T / 2), (HALL_X1, my1 - T / 2), FLOOR_H, 0.3,
            [(yy - (my0 + T / 2), 2.6, 0, 3.4) for yy in doors], z)
mw.finish("Malikane_Duvarlar", [M["plaster"]], C_MANSION)
wf.finish("Malikane_Pencere_Cerceve", [M["frame"]], C_MANSION)
wg.finish("Malikane_Cam", [M["glass"]], C_MANSION)
cu.finish("Malikane_Perdeler", [M["velvet"], M["brass"]], C_MANSION)

# floors & roof
fl = Builder()
ix0, iy0, ix1, iy1 = mx0 + T / 2, my0 + T / 2, mx1 - T / 2, my1 - T / 2
fl.box(((ix0 + ix1) / 2, (iy0 + iy1) / 2, Z1 - 0.1), (ix1 - ix0, iy1 - iy0, 0.2))
# upper floor with the hall void: gallery strips along the west wall and both sides,
# open over the central floor and over the staircase




VOID_C = (ix0 + 4.0, SX0, dy - 5.0, dy + 5.0)      # over the hall floor
VOID_S = (SX0, SX_B, dy - 9.0, dy + 9.0)           # over the staircase
slab_with_holes(fl, (ix0, ix1, iy0, iy1), [VOID_C, VOID_S], Z2)
fl.finish("Malikane_Zeminler", [M["floor"]], C_MANSION)

# black and white marble chequerboard in the hall
mf = Builder()
for i in range(int(HALL_X1 - ix0)):
    for j in range(int(HALL_Y1 - HALL_Y0) - 1):
        mf.box((ix0 + i + 0.5, HALL_Y0 + 0.65 + j, Z1 + 0.01), (1.0, 1.0, 0.02), mi=(i + j) % 2)
mf.finish("Malikane_Mermer_Zemin", [M["marble_w"], M["marble_b"]], C_MANSION)

# imperial staircase: central flight to a landing, two return flights to the gallery
sb = Builder()  # mats: marble, carpet, dark wood, brass
STEPS, RUN = 14, (SX_L - SX0) / 14
for i in range(STEPS):
    top = Z1 + (ZM - Z1) * (i + 1) / STEPS
    x = SX0 + RUN * (i + 0.5)
    sb.box((x, dy, (Z1 + top) / 2), (RUN, 6.0, top - Z1))
    sb.box((x, dy, top + 0.015), (RUN, 3.6, 0.03), mi=1)
    for s in (-1, 1):  # return flights climb back towards the door
        top2 = ZM + (Z2 - ZM) * (i + 1) / STEPS
        x2 = SX_L - RUN * (i + 0.5)
        sb.box((x2, dy + s * 7, top2 - 0.2), (RUN, 4.0, 0.4))                # open underside
        if i % 4 == 3:
            sb.cyl((x2, dy + s * 8.6, (Z1 + top2) / 2), 0.18, top2 - Z1 - 0.3, 16)  # columns under the flight
            sb.cyl((x2, dy + s * 5.4, (Z1 + top2) / 2), 0.18, top2 - Z1 - 0.3, 16)
        sb.box((x2, dy + s * 7, top2 + 0.015), (RUN, 2.4, 0.03), mi=1)
for s in (-1, 1):  # sloped soffits under the return flights
    sb.beam((SX_L, dy + s * 7, ZM - 0.45), (SX0, dy + s * 7, Z2 - 0.45), 3.8, 0.3)
sb.box(((SX_L + HALL_X1) / 2, dy, (Z1 + ZM) / 2), (HALL_X1 - SX_L, 18.0, ZM - Z1))
sb.box(((SX_L + HALL_X1) / 2, dy, ZM + 0.015), (HALL_X1 - SX_L - 1.0, 3.6, 0.03), mi=1)
for s in (-1, 1):
    sb.box(((SX_L + HALL_X1) / 2 - 0.5, dy + s * 4.6, ZM + 0.015), (2.4, 5.6, 0.03), mi=1)


def rail(b, p0, p1, h=1.0, spacing=0.35):
    """Handrail from p0 to p1 (stair nosing points) with turned balusters."""
    p0, p1 = Vector(p0), Vector(p1)
    b.beam(p0 + Vector((0, 0, h)), p1 + Vector((0, 0, h)), 0.12, 0.1, mi=2)
    n = max(1, int((p1 - p0).length / spacing))
    for i in range(n + 1):
        q = p0.lerp(p1, i / n)
        b.cyl((q.x, q.y, q.z + h / 2), 0.04, h, 8, mi=0)


for s in (-1, 1):
    rail(sb, (SX0, dy + s * 3.05, Z1), (SX_L, dy + s * 3.05, ZM))                 # central flight
    for yy in (5.05, 8.95):                                                        # return flights
        rail(sb, (SX_L, dy + s * yy, ZM), (SX0, dy + s * yy, Z2))
    rail(sb, (SX_L, dy + s * 3.05, ZM), (SX_L, dy + s * 4.95, ZM))                # landing front
    rail(sb, (SX_L, dy + s * 9.0, ZM), (HALL_X1 - 0.2, dy + s * 9.0, ZM))         # landing sides
    sb.box((SX0 - 0.1, dy + s * 3.05, Z1 + 0.7), (0.45, 0.45, 1.4), mi=2)          # newel posts
    sb.blob((SX0 - 0.1, dy + s * 3.05, Z1 + 1.55), 0.18, 1.0, mi=3)
# gallery balustrades around the void
balustrade(sb, (VOID_C[0], dy - 5), (SX0, dy - 5), Z2)
balustrade(sb, (VOID_C[0], dy + 5), (SX0, dy + 5), Z2)
balustrade(sb, (VOID_C[0], dy - 5), (VOID_C[0], dy + 5), Z2)
balustrade(sb, (SX0, dy - 9), (SX_B, dy - 9), Z2)
balustrade(sb, (SX0, dy + 9), (SX_B, dy + 9), Z2)
balustrade(sb, (SX_B, dy - 9), (SX_B, dy + 9), Z2)
sb.finish("Malikane_Saray_Merdiveni", [M["marble_w"], M["carpet"], M["dark_wood"], M["brass"]], C_MANSION)

# hall decor: dark wood wainscoting, pilasters, cornice
hd = Builder()
for y, sgn in ((HALL_Y0, 1), (HALL_Y1, -1)):
    yi = y + sgn * 0.18
    hd.wall((mx0 + T / 2, yi), (HALL_X1, yi), 1.3, 0.06, [(10.0, 3.0, 0, 3.8)], Z1, mi=0)
    for x in (mx0 + 4, mx0 + 15, mx0 + 20, mx0 + 25):
        hd.box((x, yi, (Z1 + TOTAL_H) / 2), (0.7, 0.25, TOTAL_H - Z1), mi=1)
    hd.box(((mx0 + HALL_X1) / 2, yi, TOTAL_H - 0.3), (HALL_X1 - mx0, 0.4, 0.5), mi=1)
    hd.box(((mx0 + HALL_X1) / 2, yi, Z2 - 0.35), (HALL_X1 - mx0, 0.3, 0.3), mi=1)
hd.finish("Malikane_Hol_Dekor", [M["dark_wood"], M["trim"]], C_MANSION)

rf = Builder()
rf.box(((mx0 + mx1) / 2, (my0 + my1) / 2, TOTAL_H + 0.1), (mx1 - mx0, my1 - my0, 0.2))
# hipped-look gable roof sitting on the parapet with a 1.5 m overhang all round
ROOF_Z, ROOF_H = TOTAL_H + 1.15, 9.5
rf.prism_roof(((mx0 + mx1) / 2, (my0 + my1) / 2), mx1 - mx0 + 3.0, my1 - my0 + 3.0, ROOF_Z, ROOF_H)
rf.box(((mx0 + mx1) / 2, (my0 + my1) / 2, ROOF_Z - 0.1), (mx1 - mx0 + 3.0, my1 - my0 + 3.0, 0.2))  # soffit
for cy in (my0 + 10, dy, my1 - 10):
    rf.box((mx0 + 30, cy, TOTAL_H + 6.0), (1.8, 1.8, 12.0))
    rf.box((mx0 + 30, cy, TOTAL_H + 12.15), (2.2, 2.2, 0.3))
    for k in (-0.4, 0.4):
        rf.cyl((mx0 + 30 + k, cy, TOTAL_H + 12.6), 0.18, 0.6, 10)  # chimney pots
rf.finish("Malikane_Cati", [M["roof"]], C_MANSION)

# plinth, front terrace and grand staircase
st = Builder()
st.box(((mx0 + mx1) / 2, (my0 + my1) / 2, (Z1 - 0.2) / 2), (mx1 - mx0 + 0.8, my1 - my0 + 0.8, Z1 - 0.2))
st.box(((px0 + mx0) / 2, dy, Z1 / 2), (PORT_D, PORT_W, Z1))
rise = Z1 / STEP_N
for j in range(1, STEP_N):  # step tops: rise * j
    length = (STEP_N - j) * STEP_RUN
    st.box((px0 - length / 2, dy, rise * j / 2), (length, 16.0, rise * j))
for s in (-1, 1):
    # stair cheek walls, pedestals with lanterns, wall lanterns beside the door
    st.box(((STAIR_FOOT_X + px0) / 2, dy + s * 8.3, Z1 / 2 + 0.3), (px0 - STAIR_FOOT_X, 0.6, Z1 + 0.6))
    st.box((STAIR_FOOT_X + 0.5, dy + s * 8.3, 0.75), (1.1, 1.1, 1.5))
    st.box((STAIR_FOOT_X + 0.5, dy + s * 8.3, 1.8), (0.4, 0.4, 0.55), mi=1)
    st.box((mx0 - 0.4, dy + s * 3.6, Z1 + 3.3), (0.3, 0.3, 0.45), mi=1)
st.finish("Malikane_Kaide_Merdiven", [M["stone"], M["lamp"]], C_MANSION)

# giant columns, balcony over the entrance, pediment
cb = Builder()
col_x = px0 + 1.0
col_top = TOTAL_H - 0.6
for cy in (-10.0, -6.5, -3.2, 3.2, 6.5, 10.0):
    cb.box((col_x, dy + cy, Z1 + 0.25), (1.9, 1.9, 0.5))
    cb.cyl((col_x, dy + cy, (Z1 + col_top) / 2), 0.7, col_top - Z1 - 1.0, 24)
    cb.box((col_x, dy + cy, col_top - 0.25), (1.9, 1.9, 0.5))
cb.box(((px0 + mx0) / 2 - 0.2, dy, col_top + 0.45), (PORT_D + 0.4, PORT_W + 0.4, 0.9))
cb.prism_roof(((px0 + mx0) / 2 - 0.2, dy), PORT_W + 0.8, PORT_D + 0.4, col_top + 0.9, 3.8, rot_z=math.pi / 2)
cb.box(((px0 + mx0) / 2, dy, Z2 - 0.2), (PORT_D, PORT_W, 0.4))
hw = PORT_W / 2 - 0.25
balustrade(cb, (px0 + 0.25, dy - hw), (px0 + 0.25, dy + hw), Z2)
balustrade(cb, (px0 + 0.25, dy - hw), (mx0 - 0.3, dy - hw), Z2)
balustrade(cb, (px0 + 0.25, dy + hw), (mx0 - 0.3, dy + hw), Z2)
cb.finish("Malikane_Sutunlar_Balkon", [M["column"]], C_MANSION)

# ---- openable doors: main entrance, balcony, interior double doors (all leaves hinge-origin)
C_DOORS = collection("Kapilar_Malikane")
LEAF_MAIN = panel_leaf("Kapi_Ana", DOOR_W / 2, DOOR_H, 0.16, [0.28, 0.32, 0.4], glass_top=True)
LEAF_WIDE = panel_leaf("Kapi_Ic_Genis", 1.3, 3.4, 0.08, [0.35, 0.65])
LEAF_NARROW = panel_leaf("Kapi_Ic_Dar", 1.1, 3.0, 0.08, [0.35, 0.65])
LEAF_BALCONY = french_leaf("Kapi_Balkon", 1.4, 3.6, 0.08)
# brass knockers on the outside of the main door
kb = Builder()
for s in (-1, 1):
    kb.cyl((mx0 - 0.11, dy + s * 0.45, Z1 + 2.6), 0.09, 0.03, 16)
kb.finish("Malikane_Kapi_Tokmak", [M["brass"]], C_MANSION)


def double_door(prefix, leaf, center, along, inward, width, z, angle=90.0):
    """Two leaves hinged at either side of an opening, swinging to `inward`."""
    c, d = Vector(center), Vector(along).normalized()
    n1, n2 = f"{prefix}_L", f"{prefix}_R"
    h1, h2 = c - d * (width / 2), c + d * (width / 2)
    door(n1, leaf, (h1.x, h1.y, z), d, inward, C_DOORS, n2, angle)
    door(n2, leaf, (h2.x, h2.y, z), -d, inward, C_DOORS, n1, angle)


double_door("Kapi_Ana", LEAF_MAIN, (mx0, dy), (0, 1), (1, 0), DOOR_W, Z1)
double_door("Kapi_Balkon", LEAF_BALCONY, (mx0, dy), (0, 1), (1, 0), 2.8, Z2)
casing = Builder()
door_casing(casing, (mx0, my0), (mx0, my1), dy - my0, DOOR_W, DOOR_H, Z1, T, 0.14, 0.45, mi=1)
door_casing(casing, (mx0, my0), (mx0, my1), dy - my0, 2.8, 3.6, Z2, T, 0.08, 0.2, mi=1)
for y, sgn in ((HALL_Y1, 1), (HALL_Y0, -1)):                     # hall side doors, into the rooms
    xg, xu = mx0 + T / 2 + 10.0, mx0 + T / 2 + 8.0
    double_door(f"Kapi_Hol_{'K' if sgn > 0 else 'G'}_Zemin", LEAF_WIDE, (xg, y), (1, 0), (0, sgn), 2.6, Z1)
    double_door(f"Kapi_Hol_{'K' if sgn > 0 else 'G'}_Ust", LEAF_NARROW, (xu, y), (1, 0), (0, sgn), 2.2, Z2)
    door_casing(casing, (mx0, y), (HALL_X1, y), xg - mx0, 2.6, 3.6, Z1, 0.3)
    door_casing(casing, (mx0, y), (HALL_X1, y), xu - mx0, 2.2, 3.0, Z2, 0.3)
for z, ys in ((Z1, (dy - 20, dy + 20)), (Z2, (dy - 20, dy, dy + 20))):  # into the library / east rooms
    for yy in ys:
        double_door(f"Kapi_Dogu_{'Zemin' if z == Z1 else 'Ust'}_{int(yy - dy):+d}", LEAF_WIDE,
                    (HALL_X1, yy), (0, 1), (1, 0), 2.6, z)
        door_casing(casing, (HALL_X1, my0), (HALL_X1, my1), yy - my0, 2.6, 3.4, z, 0.3)
casing.finish("Malikane_Kapi_Kasalari", [M["dark_wood"], M["column"]], C_MANSION)

for s, tag in ((1, "L"), (-1, "R")):
    point_light(f"Malikane_Kapi_Feneri_{tag}", (mx0 - 0.8, dy + s * 3.6, Z1 + 3.3), 150)
    point_light(f"Merdiven_Feneri_{tag}", (STAIR_FOOT_X + 0.5, dy + s * 8.3, 2.2), 120)

# chandeliers: one shared mesh, origin at the ceiling mount
ab = Builder()
ab.cyl((0, 0, -0.5), 0.03, 1.0, 6)
ab.cyl((0, 0, -1.15), 0.18, 0.35, 12)
ab.cone((0, 0, -1.45), 0.18, 0.0, 0.3, 12)
for i in range(16):  # ring
    ang = math.tau * i / 16
    ab.box((0.75 * math.cos(ang), 0.75 * math.sin(ang), -1.15), (0.32, 0.04, 0.04), ang + math.pi / 2)
for i in range(8):  # arms + candles
    ang = math.tau * i / 8
    c, s = math.cos(ang), math.sin(ang)
    ab.box((0.38 * c, 0.38 * s, -1.15), (0.75, 0.03, 0.03), ang)
    ab.cyl((0.75 * c, 0.75 * s, -1.02), 0.025, 0.22, 6)
    ab.blob((0.75 * c, 0.75 * s, -0.86), 0.05, 1.6, mi=1)
chandelier = ab.finish("Avize", [M["brass"], M["lamp"]], C_PROTO)
chandelier.location = (-150, -90, 0)

C_CHAND = collection("Avizeler")
CX_N, CX_S = (HALL_Y1 + my1) / 2, (HALL_Y0 + my0) / 2          # room centre lines (y)
CX_MID = (mx0 + HALL_X1) / 2                                     # front rooms centre (x)
CX_BACK = (HALL_X1 + mx1) / 2                                    # library centre (x)
rooms = {
    "Zemin": (Z2 - 0.2, [(CX_MID - 6, CX_N), (CX_MID + 6, CX_N), (CX_MID - 4, CX_S), (CX_MID + 4, CX_S),
                         (CX_BACK, my1 - 14), (CX_BACK, dy), (CX_BACK, my0 + 14)]),
    "Ust": (TOTAL_H, [(CX_MID - 6, CX_N), (CX_MID + 6, CX_N), (CX_MID - 6, CX_S), (CX_MID + 6, CX_S),
                      (CX_BACK, my1 - 14), (CX_BACK, my0 + 14)]),
}
for lvl, (ceil, spots) in rooms.items():
    for i, (x, y) in enumerate(spots):
        ob = bpy.data.objects.new(f"Avize_{lvl}_{i + 1}", chandelier.data)
        ob.location = (x, y, ceil)
        ob.visible_shadow = False  # the light sits inside the chandelier
        C_CHAND.objects.link(ob)
        point_light(f"Avize_{lvl}_{i + 1}_Isik", (x, y, ceil - 0.9), 400, (1.0, 0.62, 0.32), 0.6)
# great chandelier in the double-height hall
ob = bpy.data.objects.new("Avize_Hol", chandelier.data)
ob.location = ((ix0 + 4 + SX0) / 2, dy, TOTAL_H)
ob.scale = (2.4, 2.4, 2.4)
ob.visible_shadow = False
C_CHAND.objects.link(ob)
point_light("Avize_Hol_Isik", ((ix0 + 4 + SX0) / 2, dy, TOTAL_H - 2.4), 1500, (1.0, 0.62, 0.32), 1.0)


# ---------------------------------------------------------------- palace furniture (shared meshes, local front = +X)
C_FURN = collection("Mobilya")
FM = [M["dark_wood"], M["upholstery"], M["brass"], M["marble_w"], M["linen"], M["velvet"],
      M["lacquer"], M["canvas"], M["fire"], M["book_r"], M["book_g"], M["book_b"], M["carpet"], M["rug_border"]]
WOOD, UPH, BRASS, MARBLE, LINEN, VELVET, LACQ, CANVAS, FIRE, BR, BG, BB, CARPET, BORDER = range(14)


def proto(name, build):
    b = Builder()
    build(b)
    ob = b.finish(f"Mob_{name}", FM, C_PROTO)
    ob.location = (-150, -120 - len(C_PROTO.objects) * 6, 0)
    return ob


def legs(b, sx, sy, h, r=0.035):
    for lx in (-sx / 2, sx / 2):
        for ly in (-sy / 2, sy / 2):
            b.cyl((lx, ly, h / 2), r, h, 8, WOOD)


def armchair(b, w=0.85):
    legs(b, 0.65, w - 0.15, 0.2)
    b.box((0, 0, 0.32), (0.8, w, 0.25), mi=UPH)
    b.box((-0.36, 0, 0.85), (0.14, w, 0.9), mi=UPH)
    b.box((-0.43, 0, 1.33), (0.08, w + 0.05, 0.08), mi=WOOD)
    for s in (-1, 1):
        b.box((0.02, s * (w / 2 - 0.05), 0.6), (0.78, 0.12, 0.3), mi=UPH)


def sofa(b):
    armchair(b, 2.3)


def coffee_table(b):
    legs(b, 1.1, 0.6, 0.42)
    b.box((0, 0, 0.45), (1.3, 0.75, 0.06), mi=MARBLE)


TABLE_CLEAR = 1.18  # underside of tables the player can crouch under (crouched capsule is 110 cm)
DINING_W = 1.9
CHAIR_SCALE = 1.25  # dining chairs grown with the oversized table


def dining_table(b, length=14.0):
    # legs along the long edges so the space underneath stays open for hiding
    hw = DINING_W / 2
    for x in [i * 3.5 - length / 2 + 0.25 for i in range(int(length / 3.5) + 1)]:
        for y in (-(hw - 0.12), hw - 0.12):
            b.cyl((x, y, TABLE_CLEAR / 2), 0.08, TABLE_CLEAR, 12, WOOD)
    for y in (-(hw - 0.08), hw - 0.08):                                              # apron, edges only
        b.box((0, y, TABLE_CLEAR - 0.03), (length - 0.2, 0.04, 0.06), mi=WOOD)
    for x in (-length / 2 + 0.12, length / 2 - 0.12):
        b.box((x, 0, TABLE_CLEAR - 0.03), (0.04, DINING_W - 0.16, 0.06), mi=WOOD)
    b.box((0, 0, TABLE_CLEAR + 0.04), (length, DINING_W, 0.08), mi=WOOD)
    b.box((0, 0, TABLE_CLEAR + 0.085), (length - 0.6, 0.55, 0.01), mi=CARPET)       # table runner


def chair(b):
    legs(b, 0.42, 0.42, 0.45, 0.025)
    b.box((0, 0, 0.48), (0.5, 0.5, 0.07), mi=UPH)
    b.box((-0.23, 0, 0.95), (0.05, 0.46, 0.85), mi=WOOD)
    b.box((-0.2, 0, 0.98), (0.03, 0.34, 0.6), mi=UPH)


def fireplace(b):
    b.box((0.35, 0, 0.05), (0.7, 2.8, 0.1), mi=MARBLE)
    for s in (-1, 1):
        b.box((0.1, s * 1.05, 0.7), (0.4, 0.35, 1.3), mi=MARBLE)
    b.box((0.12, 0, 1.42), (0.55, 3.0, 0.16), mi=MARBLE)
    b.box((0.1, 0, 1.2), (0.38, 1.8, 0.3), mi=MARBLE)
    b.box((-0.15, 0, 0.55), (0.1, 1.8, 1.0), mi=LACQ)                      # sooty back
    for k in range(5):
        b.blob((0.05, -0.5 + k * 0.25, 0.25), 0.16, 1.6, mi=FIRE)
    b.box((-0.1, 0, 3.0), (0.5, 2.4, 3.0), mi=WOOD)                        # overmantel panel
    b.box((-0.0, 0, 2.6), (0.08, 1.6, 1.4), mi=BRASS)                       # mirror frame
    b.box((0.03, 0, 2.6), (0.04, 1.4, 1.2), mi=LACQ)


def bookcase(b):
    rnd = random.Random(5)
    w, h, dpt = 1.8, 2.6, 0.45
    b.box((-dpt / 2 + 0.02, 0, h / 2), (0.04, w, h), mi=WOOD)
    for s in (-1, 1):
        b.box((0, s * w / 2, h / 2), (dpt, 0.05, h), mi=WOOD)
    for k in range(6):
        z = 0.1 + k * 0.48
        b.box((0, 0, z), (dpt, w, 0.04), mi=WOOD)
        if k == 5:
            break
        y = -w / 2 + 0.05
        while y < w / 2 - 0.08:
            t = rnd.uniform(0.03, 0.07)
            bh = rnd.uniform(0.28, 0.4)
            b.box((0.02, y + t / 2, z + 0.02 + bh / 2), (0.3, t, bh), mi=rnd.choice((BR, BG, BB)))
            y += t + 0.004
    b.box((0, 0, h + 0.08), (dpt + 0.1, w + 0.1, 0.16), mi=WOOD)


def bed(b):
    b.box((0, 0, 0.3), (2.3, 2.0, 0.45), mi=WOOD)
    b.box((0.05, 0, 0.62), (2.15, 1.9, 0.25), mi=LINEN)
    b.box((0.35, 0, 0.76), (1.5, 1.95, 0.06), mi=VELVET)                   # bedspread
    for s in (-1, 1):
        b.box((-0.85, s * 0.45, 0.82), (0.4, 0.75, 0.18), mi=LINEN)        # pillows
    b.box((-1.13, 0, 1.2), (0.1, 2.0, 1.6), mi=WOOD)                       # headboard
    for lx in (-1.12, 1.12):
        for ly in (-0.98, 0.98):
            b.cyl((lx, ly, 1.25), 0.06, 2.5, 10, WOOD)
            b.box((lx, ly, 1.3), (0.12, 0.35, 2.3), mi=VELVET)             # drapes
    b.box((0, 0, 2.52), (2.4, 2.1, 0.12), mi=WOOD)                         # canopy


def wardrobe(b):
    b.box((0, 0, 1.15), (0.65, 1.6, 2.3), mi=WOOD)
    b.box((0.33, 0, 1.15), (0.02, 0.02, 2.1), mi=LACQ)
    for s in (-1, 1):
        b.box((0.34, s * 0.12, 1.2), (0.03, 0.03, 0.18), mi=BRASS)
    b.box((0, 0, 2.38), (0.75, 1.75, 0.16), mi=WOOD)


def sideboard(b):
    b.box((0, 0, 0.45), (0.55, 1.9, 0.8), mi=WOOD)
    b.box((0, 0, 0.88), (0.6, 2.0, 0.05), mi=MARBLE)
    for s in (-1, 0, 1):
        b.box((0.28, s * 0.6, 0.6), (0.02, 0.04, 0.04), mi=BRASS)


def clock(b):
    b.box((0, 0, 0.4), (0.4, 0.6, 0.8), mi=WOOD)
    b.box((0, 0, 1.25), (0.32, 0.45, 0.9), mi=WOOD)
    b.box((0, 0, 1.95), (0.42, 0.62, 0.55), mi=WOOD)
    b.box((0.21, 0, 1.95), (0.02, 0.38, 0.38), mi=BRASS)
    b.box((0.17, 0, 1.25), (0.01, 0.06, 0.6), mi=BRASS)                    # pendulum
    b.prism_roof((0, 0), 0.62, 0.45, 2.22, 0.2, rot_z=math.pi / 2, mi=WOOD)


def piano(b):
    for p in ((0.5, 0.5), (0.5, -0.5), (-0.7, 0)):
        b.cyl((p[0], p[1], 0.35), 0.06, 0.7, 10, LACQ)
    b.box((-0.1, 0, 0.85), (1.8, 1.45, 0.32), mi=LACQ)
    b.box((0.85, 0, 0.78), (0.2, 1.3, 0.06), mi=LINEN)                     # keys
    b.beam((-0.95, 0.7, 1.02), (0.7, 0.7, 1.75), 0.03, 1.4, mi=LACQ)       # open lid


def painting(b, w=1.4, h=1.0):
    b.box((0.0, 0, 0), (0.03, w, h), mi=CANVAS)
    for s in (-1, 1):
        b.box((0.03, s * (w / 2 + 0.05), 0), (0.08, 0.1, h + 0.2), mi=BRASS)
        b.box((0.03, 0, s * (h / 2 + 0.05)), (0.08, w + 0.2, 0.1), mi=BRASS)


def rug(b, sx=6.0, sy=4.0):
    b.box((0, 0, 0.012), (sx, sy, 0.012), mi=BORDER)
    b.box((0, 0, 0.02), (sx - 0.4, sy - 0.4, 0.012), mi=CARPET)


def candelabra(b):
    b.cyl((0, 0, 0.02), 0.09, 0.04, 12, BRASS)
    b.cyl((0, 0, 0.25), 0.02, 0.45, 8, BRASS)
    for k in range(5):
        ang = math.tau * k / 5
        x, y = (0.13 * math.cos(ang), 0.13 * math.sin(ang)) if k else (0, 0)
        if k:
            b.box((x / 2, y / 2, 0.42), (0.14, 0.015, 0.015), ang, BRASS)
        b.cyl((x, y, 0.53), 0.012, 0.18, 6, LINEN)
        b.blob((x, y, 0.65), 0.018, 1.8, mi=FIRE)


def pedestal_vase(b):
    b.box((0, 0, 0.55), (0.45, 0.45, 1.1), mi=MARBLE)
    b.box((0, 0, 1.12), (0.55, 0.55, 0.06), mi=MARBLE)
    b.blob((0, 0, 1.45), 0.25, 1.4, mi=LACQ, subdiv=2)
    b.cyl((0, 0, 1.8), 0.08, 0.2, 12, LACQ)


def desk(b):
    # two drawer pedestals with a knee hole wide and high enough to crouch into
    for s in (-1, 1):
        b.box((0, s * 0.72, TABLE_CLEAR / 2), (0.75, 0.42, TABLE_CLEAR), mi=WOOD)
    b.box((0, 0, TABLE_CLEAR + 0.025), (0.9, 1.9, 0.05), mi=WOOD)
    b.box((0, 0, TABLE_CLEAR + 0.055), (0.6, 1.0, 0.01), mi=UPH)          # leather top


def pedestal(b):
    b.box((0, 0, 0.06), (0.6, 0.6, 0.12), mi=MARBLE)
    b.cyl((0, 0, 0.6), 0.2, 1.0, 16, MARBLE)
    b.box((0, 0, 1.12), (0.5, 0.5, 0.06), mi=MARBLE)


def bust(b):  # placeholder; Poly Haven marble bust replaces it
    b.blob((0, 0, 0.3), 0.18, 1.5, mi=MARBLE)


def mirror(b):  # placeholder; Poly Haven ornate mirror replaces it (front +X, centred)
    b.box((0, 0, 0), (0.03, 0.9, 1.3), mi=BRASS)


def small_vase(b):  # placeholder; Poly Haven ceramic vase replaces it
    b.blob((0, 0, 0.2), 0.13, 1.6, mi=LACQ)


P = {n: proto(n, f) for n, f in (
    ("Kaide", pedestal), ("Bust", bust), ("Ayna", mirror), ("Vazo_Kucuk", small_vase),
    ("Koltuk", armchair), ("Kanepe", sofa), ("Sehpa", coffee_table), ("Yemek_Masasi", dining_table),
    ("Sandalye", chair), ("Somine", fireplace), ("Kitaplik", bookcase), ("Yatak", bed), ("Gardirop", wardrobe),
    ("Konsol", sideboard), ("Saat", clock), ("Piyano", piano), ("Tablo", painting), ("Hali", rug),
    ("Samdan", candelabra), ("Vazo", pedestal_vase), ("Calisma_Masasi", desk))}
count = {}


def place(name, x, y, z, deg=0.0, s=1.0):
    count[name] = count.get(name, 0) + 1
    ob = bpy.data.objects.new(f"Mob_{name}_{count[name]:02d}", P[name].data)
    ob.location = (x, y, z)
    ob.rotation_euler.z = math.radians(deg)
    ob.scale = (s, s, s) if isinstance(s, (int, float)) else s
    C_FURN.objects.link(ob)
    return ob


N_IN, S_IN = HALL_Y1 + 0.15, HALL_Y0 - 0.15        # room faces of the hall side walls
W_IN, E_IN, NW, SW = mx0 + T / 2, mx1 - T / 2, my1 - T / 2, my0 + T / 2
BACK_W, BACK_E = HALL_X1 - 0.15, HALL_X1 + 0.15      # faces of the hall back wall

# entrance hall
place("Hali", (ix0 + SX0) / 2, dy, Z1, 0, (2.6, 0.9, 1))
for s in (-1, 1):
    place("Vazo", mx0 + 2.0, dy + s * 4.0, Z1)
    place("Vazo", SX0 - 1.2, dy + s * 4.2, Z1)
    for x in (mx0 + 5, mx0 + 15, mx0 + 21):
        place("Tablo", x, dy + s * 11.75, Z1 + 2.6, -90 * s, 1.6)
        place("Tablo", x, dy + s * 11.75, Z2 + 2.3, -90 * s, 1.3)
    place("Saat", HALL_X1 - 0.5, dy + s * 10.5, Z1, 180)

# salon (north, ground floor)
place("Somine", CX_MID, NW - 0.25, Z1, -90)
place("Hali", CX_MID, CX_N + 2, Z1, 0, (1.5, 1.6, 1))
place("Kanepe", CX_MID, CX_N - 1.5, Z1, 90)
place("Sehpa", CX_MID, CX_N + 1.5, Z1, 90)
place("Koltuk", CX_MID - 3, CX_N + 2, Z1, 0)
place("Koltuk", CX_MID + 3, CX_N + 2, Z1, 180)
place("Piyano", mx0 + 5, HALL_Y1 + 6, Z1, 30)
place("Saat", BACK_W - 0.3, NW - 2, Z1, 180)
for y in (HALL_Y1 + 3, HALL_Y1 + 13, HALL_Y1 + 15, HALL_Y1 + 17, HALL_Y1 + 19):
    place("Kitaplik", BACK_W - 0.25, y, Z1, 180)
for x in (mx0 + 4, CX_MID + 7):
    place("Tablo", x, N_IN + 0.05, Z1 + 2.5, 90, 1.5)
place("Koltuk", mx0 + 4, NW - 4, Z1, -45)
place("Koltuk", mx0 + 6.5, NW - 4, Z1, -135)
place("Sehpa", mx0 + 5.2, NW - 5.2, Z1, 0, 0.6)

# dining room (south, ground floor)
place("Hali", CX_MID, CX_S, Z1, 0, (2.8, 1.3, 1))
place("Yemek_Masasi", CX_MID, CX_S, Z1)
for i in range(9):  # 1.5 m apart: the gaps between chairs are wide enough to crawl under the table
    x = CX_MID - 6 + i * 1.5
    place("Sandalye", x, CX_S + DINING_W / 2 + 0.4, Z1, -90, CHAIR_SCALE)
    place("Sandalye", x, CX_S - DINING_W / 2 - 0.4, Z1, 90, CHAIR_SCALE)
place("Sandalye", CX_MID - 8.0, CX_S, Z1, 0, CHAIR_SCALE)
place("Sandalye", CX_MID + 8.0, CX_S, Z1, 180, CHAIR_SCALE)
for x in (-4.5, -1.5, 1.5, 4.5):
    place("Samdan", CX_MID + x, CX_S, Z1 + TABLE_CLEAR + 0.09)
place("Somine", CX_MID, SW + 0.25, Z1, 90)
for y in (my0 + 6, HALL_Y0 - 4):
    place("Konsol", BACK_W - 0.3, y, Z1, 180)
    place("Samdan", BACK_W - 0.3, y, Z1 + 0.9)
for x in (mx0 + 4, CX_MID + 7):
    place("Tablo", x, S_IN - 0.05, Z1 + 2.5, -90, 1.6)

# library (east, ground floor)
y = my0 + 2.0
while y < my1 - 2.0:
    if all(abs(y - d) > 2.2 for d in (dy - 20, dy + 20)):
        place("Kitaplik", BACK_E + 0.25, y, Z1, 0)
    y += 1.85
for yy in (my1 - 14, my0 + 14):
    place("Hali", CX_BACK, yy, Z1, 90, (1.3, 1.1, 1))
    place("Koltuk", CX_BACK - 1.6, yy - 1.4, Z1, 45)
    place("Koltuk", CX_BACK + 1.6, yy - 1.4, Z1, 135)
    place("Sehpa", CX_BACK, yy, Z1, 0, 0.7)
place("Calisma_Masasi", CX_BACK + 3, dy, Z1, 180)
place("Sandalye", CX_BACK + 3.8, dy, Z1, 180, CHAIR_SCALE)
place("Samdan", CX_BACK + 3, dy + 0.6, Z1 + TABLE_CLEAR + 0.06)
place("Hali", CX_BACK + 2, dy, Z1, 90, (1.0, 1.0, 1))
place("Saat", E_IN - 0.3, dy + 4, Z1, 180)

# upper floor: master bedroom (north), guest bedroom + study (south), portrait gallery (east)
for side, yc, wall_y, face in ((1, CX_N, NW, -90), (-1, CX_S, SW, 90)):
    place("Yatak", CX_MID + 4, wall_y - side * 1.3, Z2, face)
    place("Hali", CX_MID + 4, wall_y - side * 3.5, Z2, 0, (0.9, 1.1, 1))
    for dx in (-1.6, 1.6):
        place("Konsol", CX_MID + 4 + dx * 1.2, wall_y - side * 0.4, Z2, face, (0.8, 0.3, 0.7))
    # in the south bedroom these two wardrobes stand half in front of the door to the east wing,
    # leaving only a sliver to squeeze through (see SQUEEZE_GAPS) — kept on purpose
    place("Gardirop", BACK_W - 0.4, yc + 4, Z2, 180)
    place("Gardirop", BACK_W - 0.4, yc + 6, Z2, 180)
    # fireplace on the hall wall, clear of the gallery door at mx0 + 8
    place("Somine", mx0 + 18, (N_IN if side > 0 else S_IN) + side * 0.25, Z2, 90 * side)
    place("Koltuk", mx0 + 16.5, (N_IN if side > 0 else S_IN) + side * 3, Z2, 45 * side)
    place("Koltuk", mx0 + 19.5, (N_IN if side > 0 else S_IN) + side * 3, Z2, 135 * side)
    place("Hali", mx0 + 18, (N_IN if side > 0 else S_IN) + side * 3, Z2, 0, (0.7, 0.8, 1))
    place("Konsol", BACK_W - 0.3, yc - 5, Z2, 180)                                   # vanity
    place("Ayna", BACK_W - 0.05, yc - 5, Z2 + 1.9, 180, 1.0)
    place("Vazo_Kucuk", BACK_W - 0.3, yc - 5.6, Z2 + 0.92)
    place("Kaide", mx0 + 1.2, wall_y - side * 1.2, Z2)
    place("Bust", mx0 + 1.2, wall_y - side * 1.2, Z2 + 1.15, -side * 45)
    place("Calisma_Masasi", mx0 + 3, yc - side * 6, Z2, 0)
    place("Samdan", mx0 + 3, yc - side * 6, Z2 + TABLE_CLEAR + 0.06)
    place("Tablo", CX_MID - 6, wall_y - side * 0.05, Z2 + 2.4, face, 1.5)
y = my0 + 3.0
while y < my1 - 3.0:
    if all(abs(y - d) > 2.0 for d in (dy - 20, dy, dy + 20)):
        place("Tablo", BACK_E + 0.05, y, Z2 + 2.3, 0, 1.4)
    y += 4.0
for yy in (my1 - 14, my0 + 14):
    place("Kanepe", CX_BACK - 2, yy, Z2, 0)
    place("Sehpa", CX_BACK, yy, Z2, 0)

# more period decor so no room feels empty
for s in (-1, 1):
    wy = dy + s * 11.4                                               # hall walls, both floors
    place("Konsol", mx0 + 5, wy, Z1, -90 * s)
    place("Vazo_Kucuk", mx0 + 5.4, wy, Z1 + 0.92)
    place("Samdan", mx0 + 4.5, wy, Z1 + 0.92)
    place("Kanepe", mx0 + 14.5, dy + s * 10.7, Z1, -90 * s)
    place("Kaide", SX0 - 3, dy + s * 7, Z1)
    place("Bust", SX0 - 3, dy + s * 7, Z1 + 1.15, 0)
    place("Konsol", mx0 + 12, wy, Z2, -90 * s)
    place("Vazo_Kucuk", mx0 + 12, wy, Z2 + 0.92)
    place("Kaide", mx0 + 3.5, dy + s * 10.9, Z2)
    place("Bust", mx0 + 3.5, dy + s * 10.9, Z2 + 1.15, -90 * s)
    place("Hali", mx0 + 10, dy + s * 8.5, Z2, 0, (2.0, 0.55, 1))     # gallery runners
# salon
place("Konsol", mx0 + 4, N_IN + 0.3, Z1, 90)
place("Vazo_Kucuk", mx0 + 4.4, N_IN + 0.3, Z1 + 0.92)
place("Samdan", mx0 + 3.6, N_IN + 0.3, Z1 + 0.92)
place("Hali", mx0 + 5, HALL_Y1 + 6, Z1, 30, (0.6, 0.7, 1))
for x, y in ((W_IN + 1.2, NW - 1.2), (BACK_W - 1.4, N_IN + 1.3)):
    place("Kaide", x, y, Z1)
    place("Bust", x, y, Z1 + 1.15, 225)
# dining room
for y in (my0 + 6, HALL_Y0 - 4):
    place("Ayna", BACK_W - 0.05, y, Z1 + 2.1, 180, 1.0)
    place("Vazo_Kucuk", BACK_W - 0.3, y + 0.6, Z1 + 0.92)
for x, y in ((W_IN + 1.2, SW + 1.2), (W_IN + 1.2, S_IN - 1.2)):
    place("Kaide", x, y, Z1)
    place("Bust", x, y, Z1 + 1.15, 45)
# library
for y in (my1 - 4, my0 + 4):
    place("Kaide", E_IN - 1.2, y, Z1)
    place("Bust", E_IN - 1.2, y, Z1 + 1.15, 180)
place("Koltuk", CX_BACK - 1.6, 20, Z1, 0)
place("Koltuk", CX_BACK + 1.6, 20, Z1, 180)
place("Sehpa", CX_BACK, 20, Z1, 90, 0.6)
place("Samdan", CX_BACK, 20, Z1 + 0.5)
# upper portrait gallery
place("Hali", CX_BACK, dy, Z2, 90, (2.4, 0.7, 1))
for y in (my0 + 9, my1 - 9, dy - 9, dy + 9):
    place("Kaide", BACK_E + 1.0, y, Z2)
    place("Bust", BACK_E + 1.0, y, Z2 + 1.15, 0)

# fireplaces glow
for i, (x, y, z) in enumerate([(CX_MID, NW - 0.6, Z1), (CX_MID, SW + 0.6, Z1),
                               (mx0 + 18, N_IN + 0.6, Z2), (mx0 + 18, S_IN - 0.6, Z2)], 1):
    point_light(f"Somine_{i}_Ates", (x, y, z + 0.5), 250, (1.0, 0.45, 0.15), 0.4)


# ---------------------------------------------------------------- huts
C_HUTS = collection("Kulubeler")
LEAF_HUT = plank_leaf("Kapi_Kulube", 1.1, 2.15, 0.06)
H_WOOD, H_STONE, H_ROOF, H_DOOR, H_LAMP, H_IRON = range(6)


def workbench(b, cx, cy, length, depth, rot, base=HUT_FLOOR_Z):
    """Bare wooden workbench (empty top): thick top, apron, four legs, lower shelf, back rail."""
    rz = Matrix.Rotation(rot, 3, 'Z')
    at = lambda lx, ly, z: tuple(rz @ Vector((lx, ly, 0)) + Vector((cx, cy, z)))
    b.box(at(0, 0, base + 0.88), (length, depth, 0.07), rot, H_DOOR)
    b.box(at(0, -depth / 2 + 0.02, base + 0.79), (length - 0.1, 0.03, 0.12), rot, H_WOOD)
    for lx in (-length / 2 + 0.07, length / 2 - 0.07):
        for ly in (-depth / 2 + 0.07, depth / 2 - 0.07):
            b.box(at(lx, ly, base + 0.42), (0.08, 0.08, 0.84), rot, H_WOOD)
    b.box(at(0, 0, base + 0.22), (length - 0.12, depth - 0.12, 0.035), rot, H_WOOD)
    b.box(at(0, depth / 2 - 0.03, base + 1.0), (length, 0.04, 0.18), rot, H_WOOD)


def wall_lamp(b, px, py, inward, base=HUT_FLOOR_Z, z=1.9):
    """Wall-mounted gas lamp: back plate, bracket arm, brass cup, glowing glass chimney."""
    rot = math.atan2(inward[1], inward[0])
    d = Vector(inward).normalized()
    p = Vector((px, py))
    b.box((p.x, p.y, base + z), (0.02, 0.12, 0.22), rot, H_IRON)
    q = p + d * 0.14
    b.box((q.x, q.y, base + z - 0.05), (0.26, 0.025, 0.025), rot, H_IRON)
    q = p + d * 0.27
    b.cyl((q.x, q.y, base + z - 0.02), 0.06, 0.07, 10, H_IRON)
    b.cyl((q.x, q.y, base + z + 0.13), 0.045, 0.24, 10, H_LAMP)
    b.cone((q.x, q.y, base + z + 0.3), 0.06, 0.02, 0.08, 10, H_IRON)
    return q


def hatch_leaf(name, length, width, t=0.06):
    """Floor hatch: planks along +X, hinge along the X axis, leaf spans +Y, top flush with the floor."""
    b = Builder()
    n = 5
    for k in range(n):
        pw = width / n
        b.box((length / 2, pw * (k + 0.5), -t / 2), (length, pw - 0.008, t))
    for xx in (0.25, length - 0.25):                               # cross battens underneath
        b.box((xx, width / 2, -t - 0.02), (0.12, width - 0.1, 0.04))
    for xx in (0.4, length - 0.4):                                 # strap hinges
        b.box((xx, 0.2, 0.004), (0.06, 0.4, 0.008), mi=1)
    b.cyl((length / 2, width - 0.18, 0.01), 0.07, 0.015, 12, 1)   # iron ring pull
    return b.finish(name, [M["wood"], M["iron"]], C_PROTO)


def trapdoor(name, leaf, hinge, col, angle=100.0):
    ob = bpy.data.objects.new(name, leaf.data)
    ob.location = hinge
    ob["door_open"] = angle
    ob["door_axis"] = "roll"
    ob["door_locked"] = False
    col.objects.link(ob)
    return ob


LEAF_HATCH = hatch_leaf("Kapi_Kapak", HATCH_L, TUN_W)
for i, (x, y, sx, sy, deg) in enumerate(HUTS, 1):
    hb, hf, hg = Builder(), Builder(), Builder()
    hx, hy, h = sx / 2, sy / 2, 3.0
    t = 0.25
    rz = Matrix.Rotation(math.radians(deg), 3, 'Z')
    to_world = lambda lx, ly, lz: rz @ Vector((lx, ly, lz)) + Vector((x, y, 0))
    holes = []
    if i == TUNNEL_HUT:  # hatch hole in the hut floor, expressed in hut-local coordinates
        inv = rz.transposed()
        c0 = inv @ Vector((ENTRY_HOLE[0] - x, ENTRY_HOLE[2] - y, 0))
        c1 = inv @ Vector((ENTRY_HOLE[1] - x, ENTRY_HOLE[3] - y, 0))
        holes = [(min(c0.x, c1.x), max(c0.x, c1.x), min(c0.y, c1.y), max(c0.y, c1.y))]
    slab_with_holes(hb, (-hx - 0.2, hx + 0.2, -hy - 0.2, hy + 0.2), holes, HUT_FLOOR_Z, 0.3, H_STONE)  # stone base
    # interior: two empty workbenches and two wall gas lamps
    workbench(hb, -0.6, hy - t / 2 - 0.4, 3.2, 0.7, 0.0)
    workbench(hb, -hx + t / 2 + 0.4, -0.6, 2.2, 0.7, math.radians(90))
    lamps = [wall_lamp(hb, hx - t / 2, 1.8, (-1, 0)), wall_lamp(hb, -hx + t / 2, -1.8, (1, 0))]
    walls_h = [((-hx, -hy), (hx, -hy), [(hx, 1.1, 0.0, 2.2)]),               # door side
               ((hx, -hy), (hx, hy), [(hy, 1.0, 1.0, 2.0)]),                 # window
               ((hx, hy), (-hx, hy), []),
               ((-hx, hy), (-hx, -hy), [(hy, 1.0, 1.0, 2.0)])]
    for a, b, ops in walls_h:
        hb.wall(a, b, h, t, ops, 0.3)
        for s, w, zb, zt in ops:
            if zb > 0:
                add_window(hf, hg, a, b, s, w, zb, zt, 0.3, t, mullions=False)
    for k in range(int(h / 0.3)):                                             # plank lines, not across the doorway
        z = 0.3 + k * 0.3
        if z > HUT_FLOOR_Z + 2.2 + 0.15:
            hb.box((0, -hy - t / 2 - 0.01, z), (sx, 0.02, 0.03))
        else:
            for x0, x1 in ((-hx, -0.55 - 0.13), (0.55 + 0.13, hx)):
                hb.box(((x0 + x1) / 2, -hy - t / 2 - 0.01, z), (x1 - x0, 0.02, 0.03))
    # roof with a generous overhang over all four walls, fascia boards along the eaves
    hb.prism_roof((0, 0), sx + 2.4, sy + 2.0, h + 0.3, 2.6, rot_z=math.pi / 2, mi=2)
    for s in (-1, 1):
        hb.box((0, s * (sy / 2 + 1.0), h + 0.25), (sx + 2.4, 0.06, 0.18), mi=3)
    if i % 3 == 0:
        hb.cyl((hx * 0.5, hy * 0.4, h + 2.4), 0.15, 2.8, 8, mi=1)            # stove pipe
    door_casing(hb, (-hx, -hy), (hx, -hy), hx, 1.1, 2.2, 0.3, t, 0.05, 0.12, mi=3)
    hut = hb.finish(f"Kulube_{i}", [M["wood"], M["stone"], M["roof"], M["door"], M["lamp"], M["iron"]], C_HUTS,
                    location=(x, y, 0), rot_z=math.radians(deg))
    fr = hf.finish(f"Kulube_{i}_Pencere", [M["frame"]], C_HUTS, location=(x, y, 0), rot_z=math.radians(deg))
    gl = hg.finish(f"Kulube_{i}_Cam", [M["glass"]], C_HUTS, location=(x, y, 0), rot_z=math.radians(deg))
    for k, q in enumerate(lamps, 1):
        point_light(f"Kulube_{i}_Lamba_{k}", to_world(q.x, q.y, HUT_FLOOR_Z + 2.05), 70, (1.0, 0.62, 0.3), 0.08)
    hinge = to_world(-0.55, -hy, HUT_FLOOR_Z)
    door(f"Kapi_Kulube_{i}", LEAF_HUT, hinge, (rz @ Vector((1, 0, 0))).xy, (rz @ Vector((0, 1, 0))).xy, C_HUTS)
    if i == TUNNEL_HUT:
        trapdoor("Kapi_Kapak_Kulube", LEAF_HATCH, (ENTRY_HOLE[0], ENTRY_HOLE[2], HUT_FLOOR_Z), C_HUTS)


# ---------------------------------------------------------------- secret tunnel
C_TUNNEL = collection("Gizli_Tunel")
tb = Builder()  # mats: planks, dirt floor, stone, lamp, iron
T_WOOD, T_DIRT, T_STONE, T_LAMP, T_IRON = range(5)
half = TUN_W / 2
entry_run = round((HUT_FLOOR_Z - TUN_FLOOR) / STEP_R) * STEP_T     # 11 steps down
exit_run = round(-TUN_FLOOR / STEP_R) * STEP_T                      # 10 steps up
x_entry_end = ENTRY_X0 - entry_run
for k in range(round((HUT_FLOOR_Z - TUN_FLOOR) / STEP_R) - 1):     # entry stairs, heading west
    top = HUT_FLOOR_Z - STEP_R * (k + 1)
    tb.box((ENTRY_X0 - STEP_T * (k + 0.5), TUN_Y, (TUN_FLOOR + top) / 2), (STEP_T, TUN_W, top - TUN_FLOOR), mi=T_WOOD)
for k in range(round(-TUN_FLOOR / STEP_R) - 1):                    # exit stairs, heading west and up
    top = TUN_FLOOR + STEP_R * (k + 1)
    tb.box((EXIT_X0 - STEP_T * (k + 0.5), TUN_Y, (TUN_FLOOR + top) / 2), (STEP_T, TUN_W, top - TUN_FLOOR), mi=T_WOOD)
for x0, x1 in ((ENTRY_X0 + 0.1, x_entry_end), (EXIT_X0, EXIT_X0 - exit_run - 0.1)):   # stair shafts
    for s in (-1, 1):
        tb.box(((x0 + x1) / 2, TUN_Y + s * (half + 0.08), (TUN_FLOOR + 0.0) / 2), (abs(x1 - x0), 0.16, -TUN_FLOOR), mi=T_STONE)
for xe in (ENTRY_X0 + 0.18, EXIT_X0 - exit_run - 0.18):            # shaft end walls
    tb.box((xe, TUN_Y, TUN_FLOOR / 2), (0.16, TUN_W + 0.32, -TUN_FLOOR), mi=T_STONE)
# the tunnel itself: dirt floor, plank walls and ceiling, timber frames every 2.2 m
tx0, tx1 = x_entry_end, EXIT_X0
tlen, tmid = tx0 - tx1, (tx0 + tx1) / 2
tb.box((tmid, TUN_Y, TUN_FLOOR - 0.05), (tlen + 0.4, 2.1, 0.1), mi=T_DIRT)
tb.box((tmid, TUN_Y, TUN_CEIL + 0.05), (tlen + 0.4, 2.1, 0.1), mi=T_WOOD)
for s in (-1, 1):
    tb.box((tmid, TUN_Y + s * 0.98, (TUN_FLOOR + TUN_CEIL) / 2), (tlen + 0.4, 0.12, TUN_CEIL - TUN_FLOOR), mi=T_WOOD)
    for xe in (tx0, tx1):  # close the gap between the narrow shafts and the wider tunnel
        tb.box((xe, TUN_Y + s * (half + 0.3), (TUN_FLOOR + TUN_CEIL) / 2), (0.16, 0.6, TUN_CEIL - TUN_FLOOR), mi=T_STONE)
n_frames = int(tlen / 2.2)
for k in range(n_frames + 1):
    fx = tx0 - k * tlen / max(n_frames, 1)
    for s in (-1, 1):
        tb.box((fx, TUN_Y + s * 0.85, (TUN_FLOOR + TUN_CEIL) / 2 - 0.05), (0.16, 0.16, TUN_CEIL - TUN_FLOOR - 0.1), mi=T_WOOD)
    tb.box((fx, TUN_Y, TUN_CEIL - 0.1), (0.18, 1.9, 0.16), mi=T_WOOD)
tunnel_lamps = [tx0 - tlen * f for f in (0.2, 0.5, 0.8)]
for k, lx in enumerate(tunnel_lamps, 1):                            # hanging lanterns on a chain
    tb.box((lx, TUN_Y, TUN_CEIL - 0.3), (0.02, 0.02, 0.4), mi=T_IRON)
    tb.box((lx, TUN_Y, TUN_CEIL - 0.6), (0.16, 0.16, 0.24), mi=T_LAMP)
    tb.box((lx, TUN_Y, TUN_CEIL - 0.46), (0.2, 0.2, 0.04), mi=T_IRON)
    point_light(f"Tunel_Lamba_{k}", (lx, TUN_Y, TUN_CEIL - 0.75), 45, (1.0, 0.55, 0.25), 0.05)
# exit hatch frame on the ground outside the fence
ex0, ex1, ey0, ey1 = EXIT_HOLE
for (cx, cy, lx, ly) in (((ex0 + ex1) / 2, ey0 - 0.08, ex1 - ex0 + 0.32, 0.16), ((ex0 + ex1) / 2, ey1 + 0.08, ex1 - ex0 + 0.32, 0.16),
                         (ex0 - 0.08, (ey0 + ey1) / 2, 0.16, ey1 - ey0), (ex1 + 0.08, (ey0 + ey1) / 2, 0.16, ey1 - ey0)):
    tb.box((cx, cy, 0.04), (lx, ly, 0.08), mi=T_WOOD)
tb.finish("Gizli_Tunel", [M["wood"], M["gravel"], M["stone"], M["lamp"], M["iron"]], C_TUNNEL)
trapdoor("Kapi_Kapak_Cikis", LEAF_HATCH, (ex0, ey0, 0.0), C_TUNNEL)


# ---------------------------------------------------------------- trees and bushes
C_TREES = collection("Agaclar")


def make_pine(name, height, radius, tiers):
    b = Builder()
    b.cone((0, 0, height * 0.15), 0.22, 0.14, height * 0.3, 8, mi=0)
    for k in range(tiers):
        f = k / tiers
        r = radius * (1 - f * 0.7)
        d = height * 0.38
        b.cone((0, 0, height * 0.25 + f * height * 0.6 + d / 2), r, 0.0, d, 10, mi=1)
    return b.finish(name, [M["trunk"], M["pine"]], C_PROTO)


def make_oak(name, height, radius, seed):
    rnd = random.Random(seed)
    b = Builder()
    b.cone((0, 0, height * 0.3), 0.35, 0.2, height * 0.6, 8, mi=0)
    for k in range(3):  # main branches
        ang = math.tau * k / 3 + rnd.random()
        b.box((math.cos(ang) * 0.8, math.sin(ang) * 0.8, height * 0.55), (1.8, 0.15, 0.15), ang)
    for k in range(7):  # canopy clusters
        ang = rnd.random() * math.tau
        rr = rnd.uniform(0.2, 0.75) * radius
        b.blob((math.cos(ang) * rr, math.sin(ang) * rr, height * rnd.uniform(0.62, 0.9)),
               radius * rnd.uniform(0.45, 0.65), 0.8, mi=1)
    return b.finish(name, [M["trunk"], M["oak"]], C_PROTO)


def make_bush(name, radius, seed):
    rnd = random.Random(seed)
    b = Builder()
    for k in range(4):
        ang = rnd.random() * math.tau
        b.blob((math.cos(ang) * radius * 0.4, math.sin(ang) * radius * 0.4, radius * 0.5),
               radius * rnd.uniform(0.55, 0.8), 0.75, mi=0)
    return b.finish(name, [M["bush"]], C_PROTO)


trees = [make_pine("Cam_A", 13.0, 3.0, 5), make_pine("Cam_B", 9.0, 2.3, 4), make_pine("Cam_C", 17.0, 3.6, 6),
         make_oak("Mese_A", 11.0, 4.5, 1), make_oak("Mese_B", 9.0, 3.8, 2)]
bushes = [make_bush("Cali_A", 1.2, 3), make_bush("Cali_B", 0.9, 4)]
for i, pr in enumerate(trees + bushes):
    pr.location = (-150 + i * 10, -100, 0)  # keep prototypes outside the map
C_PROTO.hide_render = True


def seg_dist(pt, a, b):
    ab = b - a
    t = max(0.0, min(1.0, (pt - a).dot(ab) / ab.length_squared))
    return (pt - (a + ab * t)).length


def inside_rounded(pt, inset):
    hw, hh, r = MAP_HW - inset, MAP_HH - inset, MAP_R - inset
    qx, qy = abs(pt.x) - (hw - r), abs(pt.y) - (hh - r)
    return Vector((max(qx, 0), max(qy, 0))).length + min(max(qx, qy), 0) < r


def blocked(pt, clear):
    if not inside_rounded(pt, 2.0 + clear * 0.3):
        return True
    if STAIR_FOOT_X - 2 - clear < pt.x < mx1 + 2 + clear and my0 - 2 - clear < pt.y < my1 + 2 + clear:
        return True
    for x, y, sx, sy, _ in HUTS:
        if (pt - Vector((x, y))).length < max(sx, sy) * 0.6 + 1.0 + clear:
            return True
    for gate in GATES.values():
        if (pt - gate["pos"]).length < 8.0 + clear:
            return True
    for line in PATHS:
        for a, b in zip(line, line[1:]):
            if seg_dist(pt, a, b) < PATH_W / 2 + 0.5 + clear:
                return True
    return False


def scatter(protos, count, min_dist, clear, scale_rng, prefix, placed):
    out, tries = [], 0
    while len(out) < count and tries < 60000:
        tries += 1
        pt = Vector((random.uniform(-MAP_HW, MAP_HW), random.uniform(-MAP_HH, MAP_HH)))
        if blocked(pt, clear) or any((pt - q).length < min_dist for q in placed):
            continue
        placed.append(pt)
        out.append(pt)
        pr = random.choice(protos)
        ob = bpy.data.objects.new(f"{prefix}_{len(out):03d}", pr.data)  # linked mesh data = instancing
        ob.location = (pt.x, pt.y, 0)
        ob.rotation_euler.z = random.uniform(0, math.tau)
        s = random.uniform(*scale_rng)
        ob.scale = (s, s, s * random.uniform(0.9, 1.1))
        C_TREES.objects.link(ob)
    return out


placed = []
scatter(trees, 330, 5.0, 2.0, (0.75, 1.3), "Agac", placed)
scatter(bushes, 180, 2.5, 0.0, (0.7, 1.4), "Cali", placed)


# ---------------------------------------------------------------- gameplay markers
C_MARK = collection("Oyun_Noktalari")


def marker(name, loc, rot_z=0.0):
    ob = bpy.data.objects.new(name, None)
    ob.empty_display_type = 'SINGLE_ARROW'
    ob.empty_display_size = 2
    ob.location = loc
    ob.rotation_euler = (math.radians(-90), 0, rot_z)
    C_MARK.objects.link(ob)


marker("PlayerStart", (-MAP_HW + 5, 24.0, 1.0), 0)
marker("Kacis_Noktasi", (35.0, -MAP_HH - 4, 1.0), 0)
marker("Malikane_Giris", (mx0 + 3, dy, Z1 + 1.0), 0)


# ---------------------------------------------------------------- night atmosphere
world = bpy.data.worlds.new("Gece")
scene.world = world
world.use_nodes = True
nt = world.node_tree
bg = nt.nodes["Background"]
bg.inputs["Color"].default_value = (0.01, 0.018, 0.045, 1)
bg.inputs["Strength"].default_value = 1.0
# Sis UE5'te Exponential Height Fog ile yapiliyor (EEVEE'de world volume gunes isigini kesiyor).

moon_d = bpy.data.lights.new("Ay_Isigi", 'SUN')
moon_d.energy = 0.8
moon_d.color = (0.55, 0.65, 1.0)
moon_d.angle = math.radians(1.0)
moon = bpy.data.objects.new("Ay_Isigi", moon_d)
moon.rotation_euler = (math.radians(55), 0, math.radians(-140))
C_LIGHTS.objects.link(moon)


# ---------------------------------------------------------------- cameras + render
def camera(name, loc, rot, ortho=None):
    cd = bpy.data.cameras.new(name)
    cd.clip_end = 1000
    if ortho:
        cd.type = 'ORTHO'
        cd.ortho_scale = ortho
    else:
        cd.lens = 28
    ob = bpy.data.objects.new(name, cd)
    ob.location = loc
    ob.rotation_euler = [math.radians(a) for a in rot]
    scene.collection.objects.link(ob)
    return ob


def look(cam, eye, target):
    cam.location = eye
    cam.rotation_euler = (Vector(target) - Vector(eye)).to_track_quat('-Z', 'Y').to_euler()


cam_persp = camera("Kamera_Genel", (0, 0, 0), (0, 0, 0))
look(cam_persp, (-125, -115, 75), (5, 0, 0))
cam_top = camera("Kamera_Ust", (0, 0, 200), (0, 0, 0), ortho=225)

for eng in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
    try:
        scene.render.engine = eng
        break
    except TypeError:
        continue
scene.render.resolution_x, scene.render.resolution_y = 1600, 900
try:
    scene.eevee.taa_render_samples = 32
    scene.eevee.use_shadows = True
except AttributeError:
    pass
scene.view_settings.view_transform = 'AgX' if 'AgX' in [i.identifier for i in scene.view_settings.bl_rna.properties['view_transform'].enum_items] else 'Filmic'
scene.view_settings.exposure = 0.3
scene.camera = cam_persp

blend_path = os.path.join(OUT_DIR, "Malikane_Harita.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend_path)
PREVIEW_DIR = os.path.join(OUT_DIR, "Onizlemeler")
os.makedirs(PREVIEW_DIR, exist_ok=True)

if bpy.app.background:
    scene.render.filepath = os.path.join(PREVIEW_DIR, "onizleme_gece.png")
    bpy.ops.render.render(write_still=True)
    cam_gate = camera("Kamera_Giris", (0, 0, 0), (0, 0, 0))
    look(cam_gate, (STAIR_FOOT_X - 14, dy - 5, 4.0), (mx0 - 3, dy, 7))
    scene.camera = cam_gate
    scene.render.filepath = os.path.join(PREVIEW_DIR, "onizleme_giris.png")
    bpy.ops.render.render(write_still=True)
    cam_in = camera("Kamera_Ic", (0, 0, 0), (0, 0, 0))
    look(cam_in, (mx0 + 1.5, dy - 3, Z1 + 1.7), (SX_L, dy, ZM + 1.5))
    scene.camera = cam_in
    scene.render.filepath = os.path.join(PREVIEW_DIR, "onizleme_ic.png")
    bpy.ops.render.render(write_still=True)
    for fname, eye, target in (("onizleme_salon.png", (mx0 + 3, CX_N - 9, Z1 + 2.2), (CX_MID, NW, Z1 + 1.2)),
                               ("onizleme_yemek_salonu.png", (mx0 + 2.5, CX_S + 7, Z1 + 2.6), (CX_MID + 3, CX_S, Z1 + 0.8)),
                               ("onizleme_kutuphane.png", (mx1 - 2, my1 - 4, Z1 + 1.8), (HALL_X1, dy - 6, Z1 + 1.4)),
                               ("onizleme_yatak_odasi.png", (mx0 + 3, CX_N - 8, Z2 + 1.8), (CX_MID + 4, NW, Z2 + 1.0))):
        look(cam_in, eye, target)
        scene.render.filepath = os.path.join(PREVIEW_DIR, fname)
        bpy.ops.render.render(write_still=True)
    # top view in flat light for checking the layout
    scene.camera = cam_top
    bg.inputs["Strength"].default_value = 0
    moon_d.energy = 4.0
    scene.view_settings.exposure = 0
    scene.render.filepath = os.path.join(PREVIEW_DIR, "onizleme_ustten.png")
    bpy.ops.render.render(write_still=True)
    bpy.ops.wm.revert_mainfile()
    scene = bpy.context.scene


# ---------------------------------------------------------------- FBX export for UE5
def export(path, objs):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.export_scene.fbx(
        filepath=path, use_selection=True, object_types={'MESH', 'EMPTY'},
        apply_scale_options='FBX_SCALE_NONE', mesh_smooth_type='FACE',  # UE reads 1 m = 100 cm
        use_mesh_modifiers=True, add_leaf_bones=False, bake_anim=False,
    )


# One FBX per unique mesh, exported at the origin; a JSON scene file holds every
# object's transform, the lights and the gameplay markers. ue_build_level.py reads
# both and rebuilds the level in UE5 (same mesh asset shared by all trees).
UE_DIR = os.path.join(OUT_DIR, "UE_Aktarim")
os.makedirs(UE_DIR, exist_ok=True)
for f in os.listdir(UE_DIR):
    if f.startswith("SM_") and f.endswith(".fbx"):
        os.remove(os.path.join(UE_DIR, f))

objs = [o for o in bpy.context.view_layer.objects]
proto_names = {o.name for o in bpy.data.collections["Prototipler"].objects}
meshes = {}
for o in objs:
    if o.type == 'MESH':
        meshes.setdefault(o.data.name, o)
for mesh_name, o in meshes.items():
    saved = (o.location.copy(), o.rotation_euler.copy(), o.scale.copy())
    o.location, o.rotation_euler, o.scale = (0, 0, 0), (0, 0, 0), (1, 1, 1)
    bpy.context.view_layer.update()  # exporter reads matrix_world
    export(os.path.join(UE_DIR, f"SM_{mesh_name}.fbx"), [o])
    o.location, o.rotation_euler, o.scale = saved
    bpy.context.view_layer.update()


def to_ue(v):
    # Blender metre, +Y  ->  UE santimetre, -Y (FBX import ayni donusumu yapar)
    return [round(v[0] * 100, 2), round(-v[1] * 100, 2), round(v[2] * 100, 2)]


data = {"materials": {}, "objects": [], "lights": [], "markers": []}
for m in bpy.data.materials:
    if not m.node_tree:
        continue
    b = m.node_tree.nodes.get("Principled BSDF")
    data["materials"][m.name] = {
        "base": list(b.inputs["Base Color"].default_value)[:3],
        "roughness": b.inputs["Roughness"].default_value,
        "metallic": b.inputs["Metallic"].default_value,
        "emissive": [c * b.inputs["Emission Strength"].default_value
                     for c in list(b.inputs["Emission Color"].default_value)[:3]],
        "glass": bool(m.get("glass", False)),
    }
for o in objs:
    if o.type == 'MESH' and o.name not in proto_names:
        entry = {
            "name": o.name, "mesh": f"SM_{o.data.name}",
            "loc": to_ue(o.location), "yaw": round(-math.degrees(o.rotation_euler.z), 3),
            "scale": [round(s, 4) for s in o.scale],
        }
        if "door_open" in o:
            hatch = o.get("door_axis") == "roll"
            # yaw: the mirrored Y flips the swing; roll: UE's positive roll already lifts the (mirrored) -Y edge
            entry["door"] = {"open": o["door_open"] if hatch else -o["door_open"], "horizontal": hatch,
                             "partner": o.get("door_partner"), "locked": bool(o.get("door_locked", False))}
        data["objects"].append(entry)
    elif o.type == 'LIGHT':
        data["lights"].append({
            "name": o.name, "type": o.data.type, "loc": to_ue(o.location),
            "color": list(o.data.color), "energy": o.data.energy,
            "rot": [math.degrees(a) for a in o.rotation_euler],
        })
    elif o.type == 'EMPTY':
        data["markers"].append({"name": o.name, "loc": to_ue(o.location)})

# narrow gaps the player squeezes through sideways with E (AMalikaneSqueeze in UE)
gap_y = (MANSION_DOOR_Y - 20) + 1.3 - 0.22      # between the south-bedroom wardrobe and the door jamb
capsule_z = Z2 + 0.96
data["squeeze"] = [{
    "name": "Dar_Gecit_Dolap", "door": "Kapi_Dogu_Ust_-20_R",
    "a": to_ue((MANSION_MIN.x + 28.0 - 1.75, gap_y, capsule_z)),  # bedroom side, in front of the wardrobe
    "b": to_ue((MANSION_MIN.x + 28.0 + 1.3, gap_y, capsule_z)),   # east-wing side, past the open leaf
}]

with open(os.path.join(UE_DIR, "scene.json"), "w", encoding="utf-8") as f:
    json.dump(data, f, indent=1)

print("BITTI ->", OUT_DIR, f"({len(meshes)} mesh, {len(data['objects'])} obje, {len(data['lights'])} isik)")
