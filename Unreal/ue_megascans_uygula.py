# Fab'dan projeye eklenen Megascans / Megaplants asset'lerini Malikane haritasina uygular:
#   - yuzey materyalleri (cim, cakil, tas, siva/tugla, kiremit, ahsap, metal) blockout materyallerinin yerine
#   - Agac_* aktorleri -> gercek agaclar (konifer / yaprakli ayrimi korunur), Cali_* -> calilar
#   - bahceye cim ortusu (tek aktorde instanced mesh)
# Once ue_haritayi_kur.py calismis olmali. Editorde: Tools > Execute Python Script.
# Asset'ler isimlerindeki anahtar kelimelerle bulunur; hangi paketi ekledigin onemli degil.

import json
import math
import os
import random

import unreal

random.seed(11)
LEVEL = "/Game/Maps/Malikane"
MESH_DIR = "/Game/Malikane/Meshes"
SEARCH_ROOTS = ["/Game/Fab", "/Game/Megascans", "/Game/MSPresets", "/Game/Quixel"]
SRC = os.environ.get("MALIKANE_SRC") or os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "Blender", "Cikti", "UE_Aktarim"))

GRASS_COUNT = 20000
MAP_HW, MAP_HH, MAP_R = 10000.0, 5500.0, 2000.0         # cm, Blender'daki cit siniri
MANSION = (400.0, -4400.0, 6400.0, 4000.0)               # x0, y0, x1, y1 (UE cm, merdiven dahil)
PATHS = [[(-10000, -2400), (-6000, -1800), (-2000, -500), (600, -200)],
         [(500, -200), (0, 4600), (3500, 4800), (3500, 5500)]]

# blockout materyali -> Megascans yuzey anahtar kelimeleri (ilk eslesen kazanir)
SURFACE_RULES = {
    "M_Grass": ["forest_floor", "forest floor", "grass", "meadow", "ground", "soil", "moss"],
    "M_Gravel": ["gravel", "pebble", "dirt"],
    "M_Stone": ["cobble", "stone", "rock", "masonry", "medieval_wall", "medieval wall"],
    "M_MansionWall": ["plaster", "stucco", "brick"],
    "M_Trim": ["marble", "concrete", "plaster"],
    "M_Column": ["marble", "concrete", "plaster", "stone"],
    "M_Roof": ["roof", "tile", "slate", "shingle"],
    "M_HutWood": ["plank", "wood", "timber"],
    "M_DoorWood": ["wood", "plank"],
    "M_WoodFloor": ["floor", "parquet", "plank", "wood"],
    "M_Iron": ["iron", "metal", "rust", "steel"],
}
CONIFER = ["spruce", "pine", "fir", "cypress", "juniper", "cedar"]
DECIDUOUS = ["oak", "poplar", "hornbeam", "beech", "maple", "birch", "elder", "ginkgo", "laurel", "medlar", "tree"]
BUSH = ["bush", "shrub", "fern", "hedge"]
GRASS = ["grass", "clump", "weed", "tuft"]

ar = unreal.AssetRegistryHelpers.get_asset_registry()
eal = unreal.EditorAssetLibrary
actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
log = lambda m: unreal.log(f"[Megascans] {m}")


def gather():
    found = []
    for root in SEARCH_ROOTS:
        if not eal.does_directory_exist(root):
            continue
        for ad in ar.get_assets_by_path(root, recursive=True):
            found.append((str(ad.asset_class_path.asset_name), str(ad.package_name)))
    return found


def has(path, words):
    p = path.lower()
    return any(w in p for w in words)


assets = gather()
log(f"{len(assets)} asset bulundu ({', '.join(SEARCH_ROOTS)})")
mis = [p for c, p in assets if c in ("MaterialInstanceConstant", "Material")]
surfaces = [p for p in mis if "surface" in p.lower()] or mis
meshes = [p for c, p in assets if c in ("StaticMesh", "Blueprint")]


def tall(path, min_cm):
    a = eal.load_asset(path)
    if isinstance(a, unreal.StaticMesh):
        return a.get_bounds().box_extent.z * 2 >= min_cm
    return True  # blueprints (e.g. tree actors): trust the name


plant_meshes = [p for p in meshes if not has(p, ["surface", "decal", "_lod", "billboard", "impostor"])]
conifers = [p for p in plant_meshes if has(p, CONIFER) and tall(p, 400)]
deciduous = [p for p in plant_meshes if has(p, DECIDUOUS) and not has(p, CONIFER) and tall(p, 400)]
bushes = [p for p in plant_meshes if has(p, BUSH)]
grasses = [p for p in plant_meshes if has(p, GRASS) and not tall(p, 200)]
log(f"agac: {len(conifers)} konifer, {len(deciduous)} yaprakli | cali: {len(bushes)} | cim: {len(grasses)} | yuzey: {len(surfaces)}")

levels.load_level(LEVEL)

# ---------------------------------------------------------------- surfaces
chosen = {}
for ours, words in SURFACE_RULES.items():
    hit = next((p for w in words for p in surfaces if w in os.path.basename(p).lower()), None)
    if hit:
        chosen[ours] = eal.load_asset(hit)
for path in eal.list_assets(MESH_DIR, recursive=False):
    sm = eal.load_asset(path)
    if not isinstance(sm, unreal.StaticMesh):
        continue
    changed = False
    for i, slot in enumerate(sm.get_editor_property("static_materials")):
        name = str(slot.get_editor_property("material_slot_name"))
        mat = next((m for k, m in chosen.items() if name.startswith(k)), None)
        if mat:
            sm.set_material(i, mat)
            changed = True
    if changed:
        eal.save_loaded_asset(sm)
for k, m in chosen.items():
    log(f"{k} -> {m.get_name()}")

# ---------------------------------------------------------------- trees and bushes


def replace(actor, choices, scale_rng):
    loc = actor.get_actor_location()
    new = actor_sub.spawn_actor_from_object(eal.load_asset(random.choice(choices)), loc,
                                            unreal.Rotator(0, 0, random.uniform(0, 360)))
    if not new:
        return False
    s = random.uniform(*scale_rng)
    new.set_actor_scale3d(unreal.Vector(s, s, s))
    new.set_actor_label(actor.get_actor_label())
    new.set_folder_path("Malikane/Agaclar")
    actor_sub.destroy_actor(actor)
    return True


all_trees = conifers + deciduous
counts = {"agac": 0, "cali": 0}
for a in actor_sub.get_all_level_actors():
    label = a.get_actor_label()
    comp = a.get_component_by_class(unreal.StaticMeshComponent)
    mesh_name = comp.static_mesh.get_name() if comp and comp.static_mesh else ""
    if label.startswith("Agac_") and all_trees:
        pool = (conifers if mesh_name.startswith("SM_Cam") else deciduous) or all_trees
        counts["agac"] += replace(a, pool, (0.8, 1.2))
    elif label.startswith("Cali_") and (bushes or grasses):
        counts["cali"] += replace(a, bushes or grasses, (0.8, 1.3) if bushes else (1.5, 2.5))
log(f"{counts['agac']} agac, {counts['cali']} cali degistirildi")

# ---------------------------------------------------------------- grass cover


def inside_map(x, y, inset):
    hw, hh, r = MAP_HW - inset, MAP_HH - inset, MAP_R - inset
    qx, qy = abs(x) - (hw - r), abs(y) - (hh - r)
    return math.hypot(max(qx, 0), max(qy, 0)) + min(max(qx, qy), 0) < r


def seg_dist(px, py, a, b):
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + dx * t), py - (ay + dy * t))


with open(os.path.join(SRC, "scene.json"), encoding="utf-8") as f:
    scene = json.load(f)
huts = [o["loc"][:2] for o in scene["objects"] if o["name"].startswith("Kulube_") and o["name"].count("_") == 1]


def free(x, y):
    if not inside_map(x, y, 150):
        return False
    x0, y0, x1, y1 = MANSION
    if x0 < x < x1 and y0 < y < y1:
        return False
    if any(math.hypot(x - hx, y - hy) < 700 for hx, hy in huts):
        return False
    return all(seg_dist(x, y, a, b) > 250 for line in PATHS for a, b in zip(line, line[1:]))


if grasses:
    try:
        holder = actor_sub.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(0, 0, 0))
        holder.set_actor_label("Cim_Ortusu")
        holder.set_folder_path("Malikane/Agaclar")
        sds = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
        root = sds.k2_gather_subobject_data_for_instance(holder)[0]
        lib = unreal.SubobjectDataBlueprintFunctionLibrary
        per_mesh = GRASS_COUNT // len(grasses)
        for gpath in grasses:
            params = unreal.AddNewSubobjectParams(parent_handle=root,
                                                  new_class=unreal.HierarchicalInstancedStaticMeshComponent)
            handle, fail = sds.add_new_subobject(params)
            comp = lib.get_object(lib.get_data(handle))
            comp.set_static_mesh(eal.load_asset(gpath))
            comp.set_cast_shadow(False)
            comp.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
            comp.set_editor_property("instance_end_cull_distance", 6000)
            xforms, tries = [], 0
            while len(xforms) < per_mesh and tries < per_mesh * 4:
                tries += 1
                x, y = random.uniform(-MAP_HW, MAP_HW), random.uniform(-MAP_HH, MAP_HH)
                if free(x, y):
                    s = random.uniform(0.7, 1.3)
                    xforms.append(unreal.Transform(unreal.Vector(x, y, 0), unreal.Rotator(0, 0, random.uniform(0, 360)),
                                                   unreal.Vector(s, s, s)))
            comp.add_instances(xforms, False, True)
        log(f"cim ortusu: {GRASS_COUNT} instance")
    except Exception as e:
        log(f"cim ortusu eklenemedi: {e}")

levels.save_current_level()
log("BITTI")
