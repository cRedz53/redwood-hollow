# Malikane level'indan sabit kameralarla goruntu alir (SceneCapture2D) ve editoru kapatir.
# Editor acilisinda calistirmak icin projenin Content/Python/init_unreal.py dosyasindan cagrilir:
#   import os; os.environ.get('MALIKANE_SHOT') == '1' and exec(open(r'...\ue_kamera_goruntuleri.py').read())
# Goruntuler: <depo>/Gorseller/kamera_*.png   (level kaydedilmez)

import math
import os
import time

import unreal

OUT = os.environ.get("MALIKANE_SHOT_DIR") or os.path.join(unreal.Paths.project_dir(), "..", "..", "Gorseller")
WARMUP, SETTLE = 45.0, 8.0


def look(name, eye, target):
    dx, dy, dz = (t - e for t, e in zip(target, eye))
    yaw = math.degrees(math.atan2(dy, dx))
    pitch = math.degrees(math.atan2(dz, math.hypot(dx, dy)))
    return name, unreal.Vector(*eye), unreal.Rotator(0, pitch, yaw)


# UE koordinatlari (cm). Blender (x, y) -> UE (x*100, -y*100)
SHOTS = [
    look("kamera_hol", (2050, 300, 330), (4000, -200, 500)),
    look("kamera_salon", (2100, -1600, 350), (3200, -4100, 250)),
    look("kamera_yemek", (2050, 1700, 380), (3500, 2400, 150)),
    look("kamera_yatak", (2100, -1700, 830), (3600, -4100, 700)),
    look("kamera_kutuphane", (5900, -3800, 330), (4600, 400, 250)),
    look("kamera_dis", (-2200, 1500, 600), (2500, -200, 900)),
]
if os.environ.get("MALIKANE_SHOT_SET") == "tunel":  # hut 7 interior, the tunnel and the exit hatch
    SHOTS = [
        look("kamera_kulube_ic", (-8450, 600, 200), (-8660, 1000, 40)),
        look("kamera_tunel", (-9000, 1000, -140), (-11000, 1000, -190)),
        look("kamera_tunel_cikis", (-11700, 700, 170), (-11350, 1000, 0)),
    ]
if os.environ.get("MALIKANE_SHOT_SET") == "odalar":  # the split-up rooms and the bathrooms
    SHOTS = [
        look("kamera_oda_salon", (1900, -1500, 350), (3200, -2550, 200)),
        look("kamera_oda_yemek", (1950, 1100, 380), (4000, 2400, 150)),
        look("kamera_oda_oturma", (1900, -4050, 350), (3650, -3000, 200)),
        look("kamera_banyo_zemin", (3750, -3680, 330), (4450, -4100, 200)),
        look("kamera_banyo_ust", (3750, 3280, 830), (4450, 3700, 700)),
        look("kamera_oda_yatak", (1900, -1500, 850), (3100, -2550, 700)),
        look("kamera_oda_dar_gecit", (3800, 1300, 830), (4550, 1900, 720)),
        look("kamera_oda_dogu", (6000, -3000, 330), (5400, -1400, 200)),
    ]
SIZE, FOV, EXPOSURE = (1600, 900), 80.0, None
if os.environ.get("MALIKANE_SHOT_SET") == "dis":  # exterior: architectural shots for the README
    SIZE, FOV, EXPOSURE = (1920, 1080), 62.0, 5.2  # brighter than play (exposure bias 3.5) so the stone reads
    SHOTS = [
        look("dis_on_cephe", (-1400, -200, 240), (2400, -200, 850)),          # front, from the drive
        look("dis_genel_sag", (-6000, 2000, 2400), (3800, -200, 600)),       # whole house, front right, from above
        look("dis_alinlik", (-200, -200, 600), (1000, -200, 1350)),           # portico pediment
        look("dis_kose_gb", (300, 4700, 500), (3000, 800, 700)),             # south-west corner, 3/4
        look("dis_kose_kb", (800, -5000, 500), (3000, -1200, 700)),          # north-west corner, 3/4
        look("dis_giris_kapisi", (-11300, -2400, 330), (-8000, -2150, 300)),  # garden gate, looking in from the lane
    ]

les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
ues = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
les.load_level("/Game/Maps/Malikane")
world = ues.get_editor_world()
rt = unreal.RenderingLibrary.create_render_target2d(world, SIZE[0], SIZE[1], unreal.TextureRenderTargetFormat.RTF_RGBA8)


def steps():
    yield WARMUP
    for name, loc, rot in SHOTS:
        cap = actors.spawn_actor_from_class(unreal.SceneCapture2D, loc, rot) or \
            unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.SceneCapture2D, loc, rot)
        if not cap:
            unreal.log_error(f"[Kamera] {name}: SceneCapture olusturulamadi")
            continue
        comp = cap.get_component_by_class(unreal.SceneCaptureComponent2D)
        comp.set_editor_property("texture_target", rt)
        comp.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR)
        comp.set_editor_property("fov_angle", FOV)
        comp.set_editor_property("capture_every_frame", True)
        if EXPOSURE is not None:
            pps = comp.get_editor_property("post_process_settings")
            pps.set_editor_property("override_auto_exposure_bias", True)
            pps.set_editor_property("auto_exposure_bias", EXPOSURE)
            comp.set_editor_property("post_process_settings", pps)
            comp.set_editor_property("post_process_blend_weight", 1.0)
        yield SETTLE
        unreal.RenderingLibrary.export_render_target(world, rt, OUT, name + ".png")
        actors.destroy_actor(cap)
        yield 1.0


plan = steps()
state = {"next": time.time() + next(plan), "handle": None}


def tick(_dt):
    if state.get("busy") or time.time() < state["next"]:
        return
    state["busy"] = True
    try:
        state["next"] = time.time() + next(plan)
    except StopIteration:
        unreal.unregister_slate_post_tick_callback(state["handle"])
        unreal.SystemLibrary.quit_editor()
    finally:
        state["busy"] = False


state["handle"] = unreal.register_slate_post_tick_callback(tick)
