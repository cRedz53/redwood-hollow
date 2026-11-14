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

les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
ues = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
les.load_level("/Game/Maps/Malikane")
world = ues.get_editor_world()
rt = unreal.RenderingLibrary.create_render_target2d(world, 1600, 900, unreal.TextureRenderTargetFormat.RTF_RGBA8)


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
        comp.set_editor_property("fov_angle", 80.0)
        comp.set_editor_property("capture_every_frame", True)
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
