# Poly Haven glTF modellerini UE icin hazirlar:
#   - parcalari tek mesh'te birlestirir, donusumleri uygular
#   - mobilyalari haritadaki blokout'larla ayni yone cevirir (on yuz +X)
#   - origin: bitki/mobilya = taban ortasi, avize = tepe, tablo = merkez
#   - FBX olarak export eder ve materyal dokularini + boyutlari ph_modeller.json'a yazar
#
#   blender -b -P Blender/polyhaven_hazirla.py -- Unreal/PolyHaven_Kaynak

import json
import math
import os
import sys

import bpy
from mathutils import Matrix, Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
SRC = os.path.abspath(argv[0] if argv else os.path.join(os.path.dirname(__file__), "..", "Unreal", "PolyHaven_Kaynak"))
MODELS = os.path.join(SRC, "Modeller")
OUT = os.path.join(SRC, "FBX")
os.makedirs(OUT, exist_ok=True)

PLANTS = ("tree", "sapling", "shrub", "fern", "grass")
TOP_ORIGIN = ("chandelier",)
CENTER_ORIGIN = ("picture_frame", "mirror")
# how to find the front so it can be turned to +X (the blockout convention)
BACK_IS_TALL = ("armchair", "sofa", "chair", "bed")          # backrest / headboard -> -X
FRONT_IS_DETAILED = ("console", "nightstand", "cabinet", "clock", "picture_frame", "mirror")  # busier side -> +X
THIN_FACES_FRONT = ("picture_frame", "mirror")               # thin axis is the facing axis


def image_path(node):
    if node and node.type == 'TEX_IMAGE' and node.image:
        return os.path.normpath(bpy.path.abspath(node.image.filepath, library=node.image.library))
    return None


def upstream(socket, depth=4):
    """First image texture feeding a socket (through normal-map / separate nodes)."""
    if not socket.is_linked or depth == 0:
        return None
    node = socket.links[0].from_node
    if node.type == 'TEX_IMAGE':
        return node
    for inp in node.inputs:
        hit = upstream(inp, depth - 1)
        if hit:
            return hit
    return None


def material_info(mat):
    info = {"name": mat.name, "base": None, "normal": None, "arm": None, "masked": False}
    if not mat.use_nodes:
        return info
    bsdf = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if not bsdf:
        return info
    info["base"] = image_path(upstream(bsdf.inputs["Base Color"]))
    info["normal"] = image_path(upstream(bsdf.inputs["Normal"]))
    info["arm"] = image_path(upstream(bsdf.inputs["Roughness"]))
    info["masked"] = bsdf.inputs["Alpha"].is_linked
    if info["masked"] and info["base"]:
        # Poly Haven ships the cut-out as a separate *_alpha map (see Araclar/polyhaven_indir.ps1)
        alpha = info["base"].replace("_diff_", "_alpha_")
        info["alpha"] = alpha if os.path.exists(alpha) else None
    col = bsdf.inputs["Base Color"].default_value
    info["color"] = [col[0], col[1], col[2]]
    return info


def world_bbox(o):
    pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
    return (min(p.x for p in pts), min(p.y for p in pts), max(p.x for p in pts), max(p.y for p in pts))


def clusters(objs, pad=0.05):
    """Group mesh objects whose XY footprints overlap: Poly Haven often lays variants out side by side."""
    boxes = [world_bbox(o) for o in objs]
    parent = list(range(len(objs)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(objs)):
        for j in range(i + 1, len(objs)):
            a, b = boxes[i], boxes[j]
            if a[0] - pad < b[2] and b[0] - pad < a[2] and a[1] - pad < b[3] and b[1] - pad < a[3]:
                parent[find(i)] = find(j)
    groups = {}
    for i, o in enumerate(objs):
        groups.setdefault(find(i), []).append(o)
    return sorted(groups.values(), key=lambda g: world_bbox(g[0])[0])


def facing_angle(verts, lid):
    """Rotation (radians, about Z) that turns the model's front to +X."""
    xs, ys, zs = zip(*verts)
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    sx, sy, h = max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)
    if any(k in lid for k in BACK_IS_TALL):
        high = [(x, y) for x, y, z in verts if z > min(zs) + 0.65 * h] or [(cx, cy)]
        ox = (sum(p[0] for p in high) / len(high) - cx) / max(sx, 1e-6)
        oy = (sum(p[1] for p in high) / len(high) - cy) / max(sy, 1e-6)
        back = (math.copysign(1, ox), 0) if abs(ox) >= abs(oy) else (0, math.copysign(1, oy))
        return math.pi - math.atan2(back[1], back[0])            # back -> -X
    if any(k in lid for k in FRONT_IS_DETAILED):
        thin_x = sx < sy
        use_x = thin_x if any(k in lid for k in THIN_FACES_FRONT) else sx <= sy
        coords, c, s = (xs, cx, sx) if use_x else (ys, cy, sy)
        plus = sum(1 for v in coords if v > c + 0.25 * s)
        minus = sum(1 for v in coords if v < c - 0.25 * s)
        front = (1 if plus >= minus else -1, 0) if use_x else (0, 1 if plus >= minus else -1)
        return -math.atan2(front[1], front[0])                    # front -> +X
    return 0.0


result = {}
for model_id in sorted(os.listdir(MODELS)):
    gltf = os.path.join(MODELS, model_id, f"{model_id}.gltf")
    if not os.path.exists(gltf):
        continue
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=gltf)
    objs = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    if not objs:
        continue
    lid = model_id.lower()
    groups = clusters(objs) if any(k in lid for k in PLANTS + ("candleholders",)) else [objs]
    for vi, group in enumerate(groups):
        key = model_id if len(groups) == 1 else f"{model_id}_v{vi + 1}"
        bpy.ops.object.select_all(action='DESELECT')
        for o in group:
            o.select_set(True)
        bpy.context.view_layer.objects.active = group[0]
        bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
        if len(group) > 1:
            bpy.ops.object.join()
        ob = bpy.context.view_layer.objects.active
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        me = ob.data
        me.transform(Matrix.Rotation(facing_angle([v.co[:] for v in me.vertices], lid), 4, 'Z'))
        xs, ys, zs = zip(*[v.co[:] for v in me.vertices])
        lo, hi = Vector((min(xs), min(ys), min(zs))), Vector((max(xs), max(ys), max(zs)))
        if any(k in lid for k in TOP_ORIGIN):
            oz = hi.z
        elif any(k in lid for k in CENTER_ORIGIN):
            oz = (lo.z + hi.z) / 2
        else:
            oz = lo.z
        me.transform(Matrix.Translation((-(lo.x + hi.x) / 2, -(lo.y + hi.y) / 2, -oz)))
        ob.location = (0, 0, 0)
        ob.name = me.name = f"PH_{key}"
        bpy.ops.object.select_all(action='DESELECT')
        ob.select_set(True)
        fbx = os.path.join(OUT, f"SM_PH_{key}.fbx")
        bpy.ops.export_scene.fbx(filepath=fbx, use_selection=True, object_types={'MESH'},
                                 apply_scale_options='FBX_SCALE_NONE', mesh_smooth_type='OFF',
                                 add_leaf_bones=False, bake_anim=False, path_mode='STRIP')
        size = hi - lo
        result[key] = {
            "base": model_id, "fbx": fbx, "size": [size.x, size.y, size.z],
            "tris": sum(len(p.vertices) - 2 for p in me.polygons),
            "materials": [material_info(s.material) for s in ob.material_slots if s.material],
        }
        print(f"[PH] {key}: {size.x:.2f} x {size.y:.2f} x {size.z:.2f} m, {result[key]['tris']} ucgen, "
              f"{len(result[key]['materials'])} materyal")

with open(os.path.join(SRC, "ph_modeller.json"), "w", encoding="utf-8") as f:
    json.dump(result, f, indent=1)
print(f"[PH] BITTI: {len(result)} model")
