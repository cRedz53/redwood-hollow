# Malikane haritasini UE5 icinde kurar: mesh import, materyaller, aktorler,
# gece isiklandirmasi (ay, fenerler), sis, gokyuzu, post process, PlayerStart.
#
# Editorde: Tools > Execute Python Script (veya komut satirindan
#   UnrealEditor.exe MalikaneGame.uproject -ExecutePythonScript="ue_build_level.py").
# Aktor yerlestirmek editor dunyasi gerektirdigi icin -run=pythonscript commandlet'i ile calismaz.
# Ortam degiskeni MALIKANE_SRC = scene.json + SM_*.fbx klasoru
# (varsayilan: depodaki Blender/Cikti/UE_Aktarim).

import json
import math
import os

import unreal

SRC = os.environ.get("MALIKANE_SRC") or os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "Blender", "Cikti", "UE_Aktarim"))
ROOT = "/Game/Malikane"
LEVEL = "/Game/Maps/Malikane"

# ---- gece ayarlari (begenmezsen buradan oyna)
MOON_LUX = 0.5            # ay isigi (directional light)
EXPOSURE_BIAS = 3.5       # manuel pozlama (yuksek = daha aydinlik)
LAMP_CD_PER_WATT = 0.15   # Blender W -> UE candela
INDOOR_LIGHT_SCALE = 0.3  # avize / somine isiklari (ic mekan pozlamaya gore cok parlak)
EMISSIVE_SCALE = 0.05     # yanik pencere / fener parlakligi
FOG_DENSITY = 0.015

asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
mel = unreal.MaterialEditingLibrary
eal = unreal.EditorAssetLibrary
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
sme = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)

with open(os.path.join(SRC, "scene.json"), encoding="utf-8") as f:
    scene = json.load(f)

# start from an empty temp map so the old level / assets are not in use
unreal.EditorLoadingAndSavingUtils.new_blank_map(False)
if eal.does_directory_exist(ROOT):
    eal.delete_directory(ROOT)


def setp(obj, prop, val):
    try:
        obj.set_editor_property(prop, val)
    except Exception as e:  # property names drift between engine versions
        unreal.log_warning(f"[Malikane] {prop} ayarlanamadi: {e}")


# ---------------------------------------------------------------- materials
def make_material(name, spec):
    path = f"{ROOT}/Materials"
    mat = asset_tools.create_asset(name, path, unreal.Material, unreal.MaterialFactoryNew())

    def const3(rgb, prop, y, x=-400):
        e = mel.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector, x, y)
        e.set_editor_property("constant", unreal.LinearColor(rgb[0], rgb[1], rgb[2], 1.0))
        if prop is not None:
            mel.connect_material_property(e, "", prop)
        return e

    def const1(v, prop, y):
        e = mel.create_material_expression(mat, unreal.MaterialExpressionConstant, -400, y)
        e.set_editor_property("r", v)
        mel.connect_material_property(e, "", prop)

    emissive = max(spec["emissive"]) > 0
    if spec.get("glass"):
        setp(mat, "blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
        setp(mat, "translucency_lighting_mode", unreal.TranslucencyLightingMode.TLM_SURFACE_PER_PIXEL_LIGHTING)
        const3(spec["base"], unreal.MaterialProperty.MP_BASE_COLOR, 0)
        const1(0.25, unreal.MaterialProperty.MP_OPACITY, 450)
    elif emissive:
        const3(spec["base"], unreal.MaterialProperty.MP_BASE_COLOR, 0)
    else:
        # world-space noise breaks up the flat colour (dirt, weathering)
        noise = mel.create_material_expression(mat, unreal.MaterialExpressionNoise, -700, 0)
        setp(noise, "scale", 0.015)
        setp(noise, "levels", 5)
        lerp = mel.create_material_expression(mat, unreal.MaterialExpressionLinearInterpolate, -200, 0)
        dark = const3([c * 0.6 for c in spec["base"]], None, -100, -450)
        light = const3([c * 1.25 for c in spec["base"]], None, 50, -450)
        mel.connect_material_expressions(dark, "", lerp, "A")
        mel.connect_material_expressions(light, "", lerp, "B")
        mel.connect_material_expressions(noise, "", lerp, "Alpha")
        mel.connect_material_property(lerp, "", unreal.MaterialProperty.MP_BASE_COLOR)
    const1(spec["roughness"], unreal.MaterialProperty.MP_ROUGHNESS, 150)
    const1(spec["metallic"], unreal.MaterialProperty.MP_METALLIC, 250)
    if emissive:
        const3([c * EMISSIVE_SCALE for c in spec["emissive"]], unreal.MaterialProperty.MP_EMISSIVE_COLOR, 350)
    mel.recompile_material(mat)
    eal.save_loaded_asset(mat)
    return mat


materials = {n: make_material(n, s) for n, s in scene["materials"].items()}
unreal.log(f"[Malikane] {len(materials)} materyal")

# ---------------------------------------------------------------- meshes
unreal.SystemLibrary.execute_console_command(None, "Interchange.FeatureFlags.Import.FBX 0")
mesh_names = sorted({o["mesh"] for o in scene["objects"]})
tasks = []
for name in mesh_names:
    ui = unreal.FbxImportUI()
    ui.set_editor_property("import_mesh", True)
    ui.set_editor_property("import_as_skeletal", False)
    ui.set_editor_property("import_materials", False)
    ui.set_editor_property("import_textures", False)
    ui.set_editor_property("import_animations", False)
    ui.set_editor_property("mesh_type_to_import", unreal.FBXImportType.FBXIT_STATIC_MESH)
    sm = ui.static_mesh_import_data
    sm.set_editor_property("combine_meshes", True)
    sm.set_editor_property("auto_generate_collision", False)
    sm.set_editor_property("generate_lightmap_u_vs", True)
    sm.set_editor_property("convert_scene", True)
    # Nanite keeps virtual shadow maps cheap; glass is translucent and cannot use it
    setp(sm, "build_nanite", not name.endswith("_Cam"))
    t = unreal.AssetImportTask()
    t.set_editor_property("filename", os.path.join(SRC, f"{name}.fbx"))
    t.set_editor_property("destination_path", f"{ROOT}/Meshes")
    t.set_editor_property("destination_name", name)
    t.set_editor_property("automated", True)
    t.set_editor_property("replace_existing", True)
    t.set_editor_property("save", False)
    t.set_editor_property("options", ui)
    tasks.append(t)
asset_tools.import_asset_tasks(tasks)

meshes = {}
for name in mesh_names:
    sm = eal.load_asset(f"{ROOT}/Meshes/{name}")
    if not sm:
        unreal.log_error(f"[Malikane] import edilemedi: {name}")
        continue
    for i, slot in enumerate(sm.get_editor_property("static_materials")):
        slot_name = str(slot.get_editor_property("material_slot_name"))
        mat = materials.get(slot_name) or next((m for n, m in materials.items() if slot_name.startswith(n)), None)
        if mat:
            sm.set_material(i, mat)
    # kapi bosluklarindan gecilebilsin: complex collision as simple. Import without
    # auto collision leaves no BodySetup, so add a box first to create one.
    body = sm.get_editor_property("body_setup")
    if not body:
        sme.add_simple_collisions(sm, unreal.ScriptingCollisionShapeType.BOX)
        body = sm.get_editor_property("body_setup")
    if body:
        body.set_editor_property("collision_trace_flag", unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
    else:
        unreal.log_warning(f"[Malikane] collision yok: {name}")
    eal.save_loaded_asset(sm)
    meshes[name] = sm
unreal.log(f"[Malikane] {len(meshes)} mesh")

# ---------------------------------------------------------------- level
if eal.does_asset_exist(LEVEL):
    # re-run: reuse the level, clear what is in it
    levels.load_level(LEVEL)
    for a in actors.get_all_level_actors():
        actors.destroy_actor(a)
elif not levels.new_level(LEVEL):
    raise RuntimeError(f"[Malikane] level olusturulamadi: {LEVEL}")
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
if not world.get_path_name().startswith(LEVEL):
    raise RuntimeError(f"[Malikane] yanlis level acik: {world.get_path_name()}")


def folder_for(name):
    for prefix, folder in (("Agac_", "Agaclar"), ("Cali_", "Agaclar"), ("Kulube", "Kulubeler"),
                           ("Malikane", "Malikane"), ("Avize", "Malikane/Avizeler"), ("Mob_", "Malikane/Mobilya"),
                           ("Giris", "Kapilar"), ("Kacis", "Kapilar"), ("Sinir", "Duvar")):
        if name.startswith(prefix):
            return f"Malikane/{folder}"
    return "Malikane/Zemin"


def vec(v):
    return unreal.Vector(v[0], v[1], v[2])


for o in scene["objects"]:
    sm = meshes.get(o["mesh"])
    if not sm:
        continue
    a = actors.spawn_actor_from_object(sm, vec(o["loc"]), unreal.Rotator(0, 0, o["yaw"]))
    a.set_actor_scale3d(vec(o["scale"]))
    a.set_actor_label(o["name"])
    a.set_folder_path(folder_for(o["name"]))
    if o["name"].startswith("Avize_"):
        a.get_component_by_class(unreal.StaticMeshComponent).set_cast_shadow(False)  # light sits inside it
    if "_Kanat_" in o["name"] or "_Kapi_" in o["name"]:
        a.get_component_by_class(unreal.StaticMeshComponent).set_mobility(unreal.ComponentMobility.MOVABLE)  # acilip kapanabilsin


def color8(c):
    return unreal.Color(r=int(c[0] * 255), g=int(c[1] * 255), b=int(c[2] * 255), a=255)


def spawn(cls, loc=(0, 0, 0), rot=unreal.Rotator(0, 0, 0), label=None, folder="Malikane/Atmosfer"):
    a = actors.spawn_actor_from_class(cls, vec(loc), rot)
    if label:
        a.set_actor_label(label)
    a.set_folder_path(folder)
    return a


# ---------------------------------------------------------------- lights
for l in scene["lights"]:
    if l["type"] == "POINT":
        a = spawn(unreal.PointLight, l["loc"], label=l["name"], folder="Malikane/Isiklar")
        c = a.get_component_by_class(unreal.PointLightComponent)
        c.set_editor_property("intensity_units", unreal.LightUnits.CANDELAS)
        indoor = l["name"].startswith(("Avize", "Somine"))
        c.set_editor_property("intensity", l["energy"] * LAMP_CD_PER_WATT * (INDOOR_LIGHT_SCALE if indoor else 1.0))
        c.set_editor_property("light_color", color8(l["color"]))
        c.set_editor_property("attenuation_radius", 1400.0 if indoor else 1800.0)
        c.set_editor_property("source_radius", 10.0)
    elif l["type"] == "SUN":
        # Blender sun: shines along local -Z after XYZ euler rotation
        rx, ry, rz = (math.radians(v) for v in l["rot"])
        x, y, z = 0.0, 0.0, -1.0
        y, z = y * math.cos(rx) - z * math.sin(rx), y * math.sin(rx) + z * math.cos(rx)
        x, z = x * math.cos(ry) + z * math.sin(ry), -x * math.sin(ry) + z * math.cos(ry)
        x, y = x * math.cos(rz) - y * math.sin(rz), x * math.sin(rz) + y * math.cos(rz)
        y = -y  # Blender -> UE
        pitch = math.degrees(math.atan2(z, math.hypot(x, y)))
        yaw = math.degrees(math.atan2(y, x))
        a = spawn(unreal.DirectionalLight, (0, 0, 3000), unreal.Rotator(0, pitch, yaw), "Ay_Isigi")
        c = a.get_component_by_class(unreal.DirectionalLightComponent)
        setp(c, "intensity", MOON_LUX)
        setp(c, "light_color", color8((0.62, 0.72, 1.0)))  # mavimsi ay isigi
        setp(c, "atmosphere_sun_light", True)
        setp(c, "mobility", unreal.ComponentMobility.MOVABLE)

# ---------------------------------------------------------------- sky, fog, post
spawn(unreal.SkyAtmosphere, label="Gokyuzu")

sky = spawn(unreal.SkyLight, (0, 0, 2000), label="Gok_Isigi")
sc = sky.get_component_by_class(unreal.SkyLightComponent)
setp(sc,"mobility", unreal.ComponentMobility.MOVABLE)
setp(sc,"real_time_capture", True)
setp(sc,"intensity", 1.0)

fog = spawn(unreal.ExponentialHeightFog, (0, 0, 0), label="Sis")
fc = fog.get_component_by_class(unreal.ExponentialHeightFogComponent)
setp(fc,"fog_density", FOG_DENSITY)
setp(fc,"fog_height_falloff", 0.35)
setp(fc,"fog_inscattering_luminance", unreal.LinearColor(0.004, 0.006, 0.012, 1))
setp(fc, "enable_volumetric_fog", True)
setp(fc,"volumetric_fog_extinction_scale", 2.0)

pp = spawn(unreal.PostProcessVolume, label="Gece_PostProcess")
pp.set_editor_property("unbound", True)
s = pp.get_editor_property("settings")
for prop, val in (
    ("auto_exposure_method", unreal.AutoExposureMethod.AEM_MANUAL),
    ("auto_exposure_apply_physical_camera_exposure", False),
    ("auto_exposure_bias", EXPOSURE_BIAS),
    ("vignette_intensity", 0.6),
    ("film_grain_intensity", 0.15),
    ("bloom_intensity", 0.8),
):
    setp(s, prop, val)
    setp(s, "override_" + prop, True)
pp.set_editor_property("settings", s)

# ---------------------------------------------------------------- gameplay
# MALIKANE_START=hol puts the player inside the mansion hall (handy for testing the interior)
start_marker = "Malikane_Giris" if os.environ.get("MALIKANE_START") == "hol" else "PlayerStart"
for m in scene["markers"]:
    if m["name"] == start_marker:
        spawn(unreal.PlayerStart, (m["loc"][0], m["loc"][1], m["loc"][2] if m["name"] != "PlayerStart" else 100),
              label="PlayerStart", folder="Malikane/Oyun")
    if m["name"] == "Kacis_Noktasi":
        t = spawn(unreal.TriggerBox, (m["loc"][0], m["loc"][1], 150), label="Kacis_Trigger", folder="Malikane/Oyun")
        t.set_actor_scale3d(unreal.Vector(6, 2, 3))

levels.save_current_level()
unreal.log(f"[Malikane] BITTI: {LEVEL} ({len(scene['objects'])} obje, {len(scene['lights'])} isik)")
if os.environ.get("MALIKANE_QUIT") == "1":
    unreal.SystemLibrary.quit_editor()
