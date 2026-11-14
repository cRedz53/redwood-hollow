# Poly Haven (CC0) dokularini ve modellerini Malikane haritasina uygular.
# Once: Araclar/polyhaven_indir.ps1 (indirir), Blender/polyhaven_hazirla.py (FBX + json), ue_haritayi_kur.py.
# Editorde: Tools > Execute Python Script.
#   - blokout materyalleri -> gercek PBR yuzeyler (cimen, cakil, tas, siva, mermer, kayrak, ahsap, parke, pasli metal, kadife)
#   - Mob_* mobilyalar -> gercek modeller (koltuk, kanepe, sandalye, sehpa, yatak, dolap, konsol, saat, samdan, tablo)
#   - Avize_* -> gercek avizeler, Agac_* / Cali_* -> gercek agac ve calilar, bahceye cim ortusu
#   - somine raflarina saat ve samdan, kapi sutunlarina fener

import json
import math
import os
import random

import unreal

random.seed(21)
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.environ.get("MALIKANE_PH") or os.path.join(HERE, "PolyHaven_Kaynak")
SCENE_JSON = os.path.normpath(os.path.join(HERE, "..", "Blender", "Cikti", "UE_Aktarim", "scene.json"))
LEVEL = "/Game/Maps/Malikane"
PH = "/Game/PolyHaven"
GRASS_COUNT = 25000

# blokout materyali -> (Poly Haven dokusu, tekrar, renk carpani, desaturasyon, metalik)
SURFACES = {
    "M_Grass": ("leafy_grass", 1.5, (1, 1, 1), 0, 0),
    "M_Gravel": ("gravel_floor_02", 1.5, (1, 1, 1), 0, 0),
    "M_Stone": ("castle_wall_slates", 1.0, (1, 1, 1), 0, 0),
    "M_MansionWall": ("worn_plaster_wall", 0.5, (1, 1, 1), 0, 0),
    "M_Trim": ("marble_01", 1.0, (1, 1, 1), 0, 0),
    "M_Column": ("marble_01", 0.6, (1, 1, 1), 0, 0),
    "M_MarbleWhite": ("marble_01", 1.0, (1, 1, 1), 0, 0),
    "M_MarbleBlack": ("marble_01", 1.0, (0.07, 0.07, 0.07), 0, 0),
    "M_Roof": ("roof_slates_02", 1.5, (1, 1, 1), 0, 0),
    "M_HutWood": ("weathered_planks", 1.0, (1, 1, 1), 0, 0),
    "M_DoorWood": ("dark_wood", 1.0, (1, 1, 1), 0, 0),
    "M_DarkWood": ("dark_wood", 1.5, (1, 1, 1), 0, 0),
    "M_WoodFloor": ("herringbone_parquet", 1.5, (1, 1, 1), 0, 0),
    "M_Iron": ("rusty_metal_02", 2.0, (0.25, 0.25, 0.25), 0.5, 0.8),
    "M_Carpet": ("velour_velvet", 3.0, (0.6, 0.04, 0.05), 1, 0),
    "M_Velvet": ("velour_velvet", 2.0, (0.45, 0.02, 0.04), 1, 0),
    "M_Upholstery": ("velour_velvet", 3.0, (0.35, 0.05, 0.06), 1, 0),
}
# blokout mobilya -> Poly Haven modeli
FURNITURE = {
    "Koltuk": "ArmChair_01", "Kanepe": "Sofa_01", "Sandalye": "dining_chair_02", "Sehpa": "gothic_coffee_table",
    "Yatak": "GothicBed_01", "Gardirop": "GothicCabinet_01", "Konsol": "ClassicConsole_01",
    "Saat": "vintage_grandfather_clock_01", "Samdan": "brass_candleholders",
    "Bust": "marble_bust_01", "Ayna": "ornate_mirror_01", "Vazo_Kucuk": "antique_ceramic_vase_01",
}
FRAMED = {"Tablo": 140.0, "Ayna": 100.0}  # blockout width (cm) at scale 1; the model is scaled to match
CONIFERS = ["fir_sapling_medium"]
DECIDUOUS = ["island_tree_01", "island_tree_02", "tree_small_02"]
BUSHES = ["shrub_02", "shrub_03", "shrub_04", "fern_02"]
GRASSES = ["grass_medium_01", "grass_medium_02"]
PLANTS = CONIFERS + DECIDUOUS + BUSHES + GRASSES + ["dead_tree_trunk_02"]

asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
mel = unreal.MaterialEditingLibrary
eal = unreal.EditorAssetLibrary
actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
log = lambda m: unreal.log(f"[PolyHaven] {m}")


def setp(obj, prop, val):
    try:
        obj.set_editor_property(prop, val)
    except Exception as e:
        log(f"{prop} ayarlanamadi: {e}")


def safe(name):
    return "".join(c if c.isalnum() else "_" for c in name)


# ---------------------------------------------------------------- textures
def import_texture(path, dest, kind):
    name = "T_" + safe(os.path.splitext(os.path.basename(path))[0])
    asset_path = f"{dest}/{name}"
    if not eal.does_asset_exist(asset_path):
        t = unreal.AssetImportTask()
        t.set_editor_property("filename", path)
        t.set_editor_property("destination_path", dest)
        t.set_editor_property("destination_name", name)
        t.set_editor_property("automated", True)
        t.set_editor_property("replace_existing", True)
        asset_tools.import_asset_tasks([t])
    tex = eal.load_asset(asset_path)
    if not tex:
        log(f"doku import edilemedi: {path}")
        return None
    if kind == "normal":
        setp(tex, "compression_settings", unreal.TextureCompressionSettings.TC_NORMALMAP)
        setp(tex, "srgb", False)
        if path.lower().find("_dx") < 0:
            setp(tex, "flip_green_channel", True)  # glTF normals are OpenGL
    elif kind == "linear":
        setp(tex, "compression_settings", unreal.TextureCompressionSettings.TC_MASKS)
        setp(tex, "srgb", False)
    eal.save_loaded_asset(tex)
    return tex


def make_master(name, masked, linear_default):
    path = f"{PH}/Materyaller/{name}"
    if eal.does_asset_exist(path):
        return eal.load_asset(path)
    m = asset_tools.create_asset(name, f"{PH}/Materyaller", unreal.Material, unreal.MaterialFactoryNew())
    if masked:
        setp(m, "blend_mode", unreal.BlendMode.BLEND_MASKED)
        setp(m, "two_sided", True)
    E = lambda cls, x, y: mel.create_material_expression(m, cls, x, y)

    def scalar(pname, default, x, y):
        e = E(unreal.MaterialExpressionScalarParameter, x, y)
        e.set_editor_property("parameter_name", pname)
        e.set_editor_property("default_value", default)
        return e

    tc = E(unreal.MaterialExpressionTextureCoordinate, -1500, 0)
    uv = E(unreal.MaterialExpressionMultiply, -1300, 0)
    mel.connect_material_expressions(tc, "", uv, "A")
    mel.connect_material_expressions(scalar("Tiling", 1.0, -1500, 120), "", uv, "B")

    def tex(pname, y, default, stype):
        t = E(unreal.MaterialExpressionTextureSampleParameter2D, -1050, y)
        t.set_editor_property("parameter_name", pname)
        t.set_editor_property("texture", default)
        t.set_editor_property("sampler_type", stype)
        mel.connect_material_expressions(uv, "", t, "UVs")
        return t

    bc = tex("BaseColor", -400, eal.load_asset("/Engine/EngineMaterials/DefaultDiffuse"),
             unreal.MaterialSamplerType.SAMPLERTYPE_COLOR)
    nm = tex("Normal", 0, eal.load_asset("/Engine/EngineMaterials/DefaultNormal"),
             unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
    arm = tex("ARM", 400, linear_default, unreal.MaterialSamplerType.SAMPLERTYPE_MASKS)
    de = E(unreal.MaterialExpressionDesaturation, -700, -400)
    mel.connect_material_expressions(bc, "RGB", de, "")
    mel.connect_material_expressions(scalar("Desat", 0.0, -900, -250), "", de, "Fraction")
    tint = E(unreal.MaterialExpressionVectorParameter, -700, -250)
    tint.set_editor_property("parameter_name", "Tint")
    tint.set_editor_property("default_value", unreal.LinearColor(1, 1, 1, 1))
    mul = E(unreal.MaterialExpressionMultiply, -450, -400)
    mel.connect_material_expressions(de, "", mul, "A")
    mel.connect_material_expressions(tint, "", mul, "B")
    mel.connect_material_property(mul, "", unreal.MaterialProperty.MP_BASE_COLOR)
    mel.connect_material_property(nm, "RGB", unreal.MaterialProperty.MP_NORMAL)
    rough = E(unreal.MaterialExpressionMultiply, -450, 350)
    mel.connect_material_expressions(arm, "G", rough, "A")
    mel.connect_material_expressions(scalar("RoughMul", 1.0, -700, 450), "", rough, "B")
    mel.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)
    metal = E(unreal.MaterialExpressionLinearInterpolate, -450, 550)
    mel.connect_material_expressions(scalar("Metallic", 0.0, -700, 550), "", metal, "A")
    mel.connect_material_expressions(arm, "B", metal, "B")
    mel.connect_material_expressions(scalar("UseARMMetal", 0.0, -700, 650), "", metal, "Alpha")
    mel.connect_material_property(metal, "", unreal.MaterialProperty.MP_METALLIC)
    if masked:
        op = tex("Opacity", 800, linear_default, unreal.MaterialSamplerType.SAMPLERTYPE_MASKS)
        mel.connect_material_property(op, "R", unreal.MaterialProperty.MP_OPACITY_MASK)
    mel.recompile_material(m)
    eal.save_loaded_asset(m)
    return m


ROUGH_MUL = {"M_WoodFloor": 2.6, "M_DarkWood": 1.6}  # these maps read as mirror-like under the chandeliers


def make_mi(name, master, base, normal, armtex, tiling=1.0, tint=(1, 1, 1), desat=0.0, metallic=0.0, arm_metal=0.0,
            rough_mul=1.0, opacity=None):
    path = f"{PH}/Materyaller/{name}"
    if eal.does_asset_exist(path):
        eal.delete_asset(path)
    mi = asset_tools.create_asset(name, f"{PH}/Materyaller", unreal.MaterialInstanceConstant,
                                  unreal.MaterialInstanceConstantFactoryNew())
    mel.set_material_instance_parent(mi, master)
    for pname, t in (("BaseColor", base), ("Normal", normal), ("ARM", armtex), ("Opacity", opacity)):
        if t:
            mel.set_material_instance_texture_parameter_value(mi, pname, t)
    for pname, v in (("Tiling", tiling), ("Desat", desat), ("Metallic", metallic), ("UseARMMetal", arm_metal),
                     ("RoughMul", rough_mul)):
        mel.set_material_instance_scalar_parameter_value(mi, pname, v)
    mel.set_material_instance_vector_parameter_value(mi, "Tint", unreal.LinearColor(tint[0], tint[1], tint[2], 1))
    mel.update_material_instance(mi)
    eal.save_loaded_asset(mi)
    return mi


# surface textures
tex_dir = os.path.join(SRC, "Dokular")
surface_tex = {}
for tid in sorted({v[0] for v in SURFACES.values()}):
    d = os.path.join(tex_dir, tid)
    get = lambda m: os.path.join(d, f"{tid}_{m}_2k.jpg")
    surface_tex[tid] = (import_texture(get("diffuse"), f"{PH}/Dokular/{tid}", "color"),
                        import_texture(get("nor_dx"), f"{PH}/Dokular/{tid}", "normal"),
                        import_texture(get("rough"), f"{PH}/Dokular/{tid}", "linear"))
linear_default = next(t[2] for t in surface_tex.values() if t[2])
M_OPAQUE = make_master("M_PH_Opak", False, linear_default)
M_MASKED = make_master("M_PH_Yaprak", True, linear_default)  # cut-out from a separate Opacity map
surface_mi = {}
for ours, (tid, tiling, tint, desat, metal) in SURFACES.items():
    b, n, r = surface_tex[tid]
    surface_mi[ours] = make_mi(f"MI_PH_{ours[2:]}", M_OPAQUE, b, n, r, tiling, tint, desat, metal,
                               rough_mul=ROUGH_MUL.get(ours, 1.0))
log(f"{len(surface_mi)} yuzey materyali")

# assign surfaces to the blockout meshes
for path in eal.list_assets("/Game/Malikane/Meshes", recursive=False):
    sm = eal.load_asset(path)
    if not isinstance(sm, unreal.StaticMesh):
        continue
    changed = False
    for i, slot in enumerate(sm.get_editor_property("static_materials")):
        name = str(slot.get_editor_property("material_slot_name"))
        mi = next((m for k, m in surface_mi.items() if name == k or name.startswith(k + "_")), None)
        if mi:
            sm.set_material(i, mi)
            changed = True
    if changed:
        eal.save_loaded_asset(sm)

# ---------------------------------------------------------------- models
with open(os.path.join(SRC, "ph_modeller.json"), encoding="utf-8") as f:
    models = json.load(f)
unreal.SystemLibrary.execute_console_command(None, "Interchange.FeatureFlags.Import.FBX 0")
meshes = {}
for mid, info in models.items():
    dest = f"{PH}/Modeller/{mid}"
    asset_path = f"{dest}/SM_PH_{mid}"
    if not eal.does_asset_exist(asset_path):
        ui = unreal.FbxImportUI()
        ui.set_editor_property("import_mesh", True)
        ui.set_editor_property("import_as_skeletal", False)
        ui.set_editor_property("import_materials", False)
        ui.set_editor_property("import_textures", False)
        ui.set_editor_property("mesh_type_to_import", unreal.FBXImportType.FBXIT_STATIC_MESH)
        sd = ui.static_mesh_import_data
        sd.set_editor_property("combine_meshes", True)
        sd.set_editor_property("generate_lightmap_u_vs", False)
        plant = info.get("base", mid) in PLANTS
        sd.set_editor_property("auto_generate_collision", not plant)
        setp(sd, "build_nanite", plant or info["tris"] > 50000)
        t = unreal.AssetImportTask()
        t.set_editor_property("filename", info["fbx"])
        t.set_editor_property("destination_path", dest)
        t.set_editor_property("destination_name", f"SM_PH_{mid}")
        t.set_editor_property("automated", True)
        t.set_editor_property("replace_existing", True)
        t.set_editor_property("options", ui)
        asset_tools.import_asset_tasks([t])
    sm = eal.load_asset(asset_path)
    if not sm:
        log(f"model import edilemedi: {mid}")
        continue
    if info.get("base", mid) in PLANTS:
        # without Preserve Area Nanite simplifies thin leaf cards away and trees look bare
        ns = sm.get_editor_property("nanite_settings")
        keep = unreal.NaniteShapePreservation.PRESERVE_AREA
        if ns.get_editor_property("shape_preservation") != keep:
            ns.set_editor_property("shape_preservation", keep)
            sm.set_editor_property("nanite_settings", ns)
    sme = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    if info.get("base") == "dead_tree_trunk_02" and sme.get_simple_collision_count(sm) == 0:
        sme.add_simple_collisions(sm, unreal.ScriptingCollisionShapeType.BOX)  # fallen logs block the player
    slots = sm.get_editor_property("static_materials")
    for i, mat in enumerate(info["materials"]):
        if i >= len(slots):
            break
        base = import_texture(mat["base"], dest, "color") if mat.get("base") else None
        nrm = import_texture(mat["normal"], dest, "normal") if mat.get("normal") else None
        arm = import_texture(mat["arm"], dest, "linear") if mat.get("arm") else None
        alpha = import_texture(mat["alpha"], dest, "linear") if mat.get("alpha") else None
        tint = mat.get("color", (1, 1, 1)) if not base else (1, 1, 1)
        mi = make_mi(f"MI_PH_{safe(mid)}_{i}", M_MASKED if alpha else M_OPAQUE,
                     base, nrm, arm, 1.0, tint, 0.0, 0.0, 1.0 if arm else 0.0, opacity=alpha)
        sm.set_material(i, mi)
    eal.save_loaded_asset(sm)
    meshes[mid] = (sm, info["size"])
log(f"{len(meshes)} model hazir")
by_base = {}
for key in meshes:
    base, (sx, sy, sz) = models[key].get("base", key), models[key]["size"]
    if base in GRASSES and sz < 0.12:
        continue  # stray blades
    if base in BUSHES and max(sx, sy) > 2.5:
        continue  # long hedge rows look wrong where a single bush stood
    by_base.setdefault(base, []).append(key)


def pick(*bases):
    """Random variant of one of the given Poly Haven models (None if none were imported)."""
    keys = [k for b in bases for k in by_base.get(b, [])]
    return random.choice(keys) if keys else None

# ---------------------------------------------------------------- replace blockouts in the level
levels.load_level(LEVEL)


def spawn(mid, loc, yaw, scale, label, folder, shadow=True):
    sm, _ = meshes[mid]
    a = actor_sub.spawn_actor_from_object(sm, loc, unreal.Rotator(0, 0, yaw))
    a.set_actor_scale3d(unreal.Vector(scale, scale, scale))
    a.set_actor_label(label)
    a.set_folder_path(folder)
    if not shadow:
        a.get_component_by_class(unreal.StaticMeshComponent).set_cast_shadow(False)
    return a


def height(mid):
    return meshes[mid][1][2] * 100.0


CYLINDER = eal.load_asset("/Engine/BasicShapes/Cylinder")  # 100 cm wide, 100 cm tall, pivot at centre


def blocker(loc, radius, height_cm, label):
    """Invisible collision cylinder (trunks, bushes) — the player can no longer walk through plants."""
    b = actor_sub.spawn_actor_from_object(CYLINDER, unreal.Vector(loc.x, loc.y, loc.z + height_cm / 2),
                                          unreal.Rotator(0, 0, 0))
    b.set_actor_scale3d(unreal.Vector(radius / 50.0, radius / 50.0, height_cm / 100.0))
    comp = b.get_component_by_class(unreal.StaticMeshComponent)
    comp.set_visibility(False)
    comp.set_cast_shadow(False)
    b.set_actor_label(label + "_Carpisma")
    b.set_folder_path("Malikane/Agaclar/Carpisma")
    return b


counts = {}
for a in list(actor_sub.get_all_level_actors()):  # extras from an earlier run of this script
    lbl = a.get_actor_label()
    if lbl == "Cim_Ortusu" or lbl.endswith(("_Saat", "_Samdan-1", "_Samdan1", "_Model", "_Carpisma")):
        actor_sub.destroy_actor(a)
for a in list(actor_sub.get_all_level_actors()):
    if not isinstance(a, unreal.StaticMeshActor):
        continue  # lights share the Avize_ prefix
    label = a.get_actor_label()
    loc, yaw, sc = a.get_actor_location(), a.get_actor_rotation().yaw, a.get_actor_scale3d()
    new = None
    if label.startswith("Mob_"):
        kind = label[4:].rsplit("_", 1)[0]
        mid = pick(FURNITURE[kind]) if kind in FURNITURE else None
        if kind == "Konsol" and abs(sc.x - sc.y) > 0.05:
            mid = pick("ClassicNightstand_01") or mid  # scaled-down consoles are bedside tables
        if kind == "Tablo":
            mid = pick("fancy_picture_frame_01", "fancy_picture_frame_02")
        if mid:
            s = 1.0
            if kind in FRAMED:
                s = FRAMED[kind] * sc.y / max(meshes[mid][1][1] * 100.0, 1.0)
            new = spawn(mid, loc, yaw, s, label, "Malikane/Mobilya")
    elif label.startswith("Avize_"):
        mid = pick("Chandelier_03" if label == "Avize_Hol" else "Chandelier_01")
        if mid:
            target = 380.0 if label == "Avize_Hol" else 160.0
            new = spawn(mid, loc, yaw, target / max(height(mid), 1.0), label, "Malikane/Avizeler", shadow=False)
    elif label.startswith("Agac_"):
        comp = a.get_component_by_class(unreal.StaticMeshComponent)
        conifer = comp and comp.static_mesh and comp.static_mesh.get_name().startswith("SM_Cam")
        log_tree = random.random() < 0.06 and pick("dead_tree_trunk_02")
        mid = log_tree or pick(*(CONIFERS if conifer else DECIDUOUS))
        if mid:
            target = random.uniform(900, 1500) if conifer else random.uniform(800, 1300)
            s = 1.0 if log_tree else target / max(height(mid), 1.0)
            new = spawn(mid, loc, random.uniform(0, 360), s, label, "Malikane/Agaclar")
            if not log_tree:  # foliage has no collision of its own: block the trunk
                blocker(loc, 30.0 * s ** 0.5, 400.0, label)
    elif label.startswith("Cali_"):
        mid = pick(*BUSHES)
        if mid:
            s = random.uniform(100, 180) / max(height(mid), 1.0)
            new = spawn(mid, loc, random.uniform(0, 360), s, label, "Malikane/Agaclar")
            sx, sy, _ = meshes[mid][1]
            blocker(loc, 35.0 * max(sx, sy) * s, 120.0, label)
    if new:
        actor_sub.destroy_actor(a)
        counts[label.split("_")[0]] = counts.get(label.split("_")[0], 0) + 1
log(f"degistirilen: {counts}")

# mantel clocks and candleholders on the fireplaces, lanterns on the gate pillars
for a in list(actor_sub.get_all_level_actors()):
    label = a.get_actor_label()
    loc, yaw = a.get_actor_location(), a.get_actor_rotation().yaw
    if label.startswith("Mob_Somine") and pick("mantel_clock_01"):
        fx, fy = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
        top = unreal.Vector(loc.x + fx * 12, loc.y + fy * 12, loc.z + 150)
        spawn(pick("mantel_clock_01"), top, yaw, 1.0, label + "_Saat", "Malikane/Mobilya")
        for side in (-1, 1):
            mid = pick("brass_candleholders")
            if mid:
                p = unreal.Vector(top.x - fy * side * 110, top.y + fx * side * 110, top.z)
                spawn(mid, p, yaw, 1.0, label + f"_Samdan{side}", "Malikane/Mobilya")
    elif "_Fener_" in label and isinstance(a, unreal.PointLight) and pick("Lantern_01"):
        # the model is a small hand lantern; scale it up to read as a pillar lantern
        spawn(pick("Lantern_01"), unreal.Vector(loc.x, loc.y, loc.z - 30), 0, 2.0, label + "_Model", "Malikane/Kapilar")

# ---------------------------------------------------------------- grass cover
MAP_HW, MAP_HH, MAP_R = 10000.0, 5500.0, 2000.0
MANSION = (400.0, -4400.0, 6400.0, 4000.0)
PATHS = [[(-10000, -2400), (-6000, -1800), (-2000, -500), (600, -200)],
         [(500, -200), (0, 4600), (3500, 4800), (3500, 5500)]]


def inside_map(x, y, inset):
    hw, hh, r = MAP_HW - inset, MAP_HH - inset, MAP_R - inset
    qx, qy = abs(x) - (hw - r), abs(y) - (hh - r)
    return math.hypot(max(qx, 0), max(qy, 0)) + min(max(qx, qy), 0) < r


def seg_dist(px, py, a, b):
    (ax, ay), (bx, by) = a, b
    dx, dy = bx - ax, by - ay
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + dx * t), py - (ay + dy * t))


with open(SCENE_JSON, encoding="utf-8") as f:
    huts = [o["loc"][:2] for o in json.load(f)["objects"] if o["name"].startswith("Kulube_") and o["name"].count("_") == 1]


def free(x, y):
    if not inside_map(x, y, 150):
        return False
    x0, y0, x1, y1 = MANSION
    if x0 < x < x1 and y0 < y < y1:
        return False
    if any(math.hypot(x - hx, y - hy) < 700 for hx, hy in huts):
        return False
    return all(seg_dist(x, y, a, b) > 250 for line in PATHS for a, b in zip(line, line[1:]))


grass = [k for b in GRASSES for k in by_base.get(b, [])]
if grass:
    try:
        holder = actor_sub.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(0, 0, 0))
        holder.set_actor_label("Cim_Ortusu")
        holder.set_folder_path("Malikane/Agaclar")
        sds = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
        root = sds.k2_gather_subobject_data_for_instance(holder)[0]
        lib = unreal.SubobjectDataBlueprintFunctionLibrary
        for mid in grass:
            params = unreal.AddNewSubobjectParams(parent_handle=root,
                                                  new_class=unreal.HierarchicalInstancedStaticMeshComponent)
            handle, _ = sds.add_new_subobject(params)
            comp = lib.get_object(lib.get_data(handle))
            comp.set_static_mesh(meshes[mid][0])
            comp.set_cast_shadow(False)
            comp.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
            setp(comp, "instance_end_cull_distance", 5000)
            xforms, tries = [], 0
            while len(xforms) < GRASS_COUNT // len(grass) and tries < GRASS_COUNT * 3:
                tries += 1
                x, y = random.uniform(-MAP_HW, MAP_HW), random.uniform(-MAP_HH, MAP_HH)
                if free(x, y):
                    s = random.uniform(0.8, 1.5)
                    xforms.append(unreal.Transform(unreal.Vector(x, y, 0),
                                                   unreal.Rotator(0, 0, random.uniform(0, 360)), unreal.Vector(s, s, s)))
            comp.add_instances(xforms, False, True)
        log(f"cim ortusu: {GRASS_COUNT} instance")
    except Exception as e:
        log(f"cim ortusu eklenemedi: {e}")

levels.save_current_level()
log("BITTI")
if os.environ.get("MALIKANE_QUIT") == "1":
    unreal.SystemLibrary.quit_editor()
