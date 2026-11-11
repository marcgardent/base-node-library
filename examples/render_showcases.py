"""Build and render the 3 Base Node (.bn) animated showcases in Blender.

Usage:
  blender -b --factory-startup --python examples/render_showcases.py -- --still
  blender -b --factory-startup --python examples/render_showcases.py -- --anim
"""

import math
import os
import subprocess
import sys

import bpy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "python"))

# Load the base_node Blender extension package
import importlib.util

EXT_DIR = os.path.join(ROOT, "base-node-for-blender")
spec = importlib.util.spec_from_file_location(
    "base_node_ext",
    os.path.join(EXT_DIR, "__init__.py"),
    submodule_search_locations=[EXT_DIR],
)
ext_mod = importlib.util.module_from_spec(spec)
sys.modules["base_node_ext"] = ext_mod
spec.loader.exec_module(ext_mod)
from base_node_ext.host import build_source  # noqa: E402

OUT_DIR = os.path.join(ROOT, "site", "images")


def make_pbr(name, color, metallic=0.0, roughness=0.35, emission=None, emission_strength=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    if emission and emission_strength > 0.0:
        bsdf.inputs["Emission Color"].default_value = (*emission, 1.0)
        bsdf.inputs["Emission Strength"].default_value = emission_strength
    return mat


def setup_materials():
    make_pbr("DarkSlate", (0.11, 0.13, 0.17), metallic=0.65, roughness=0.38)
    make_pbr("SteelRing", (0.52, 0.57, 0.65), metallic=0.85, roughness=0.25)
    make_pbr("BrassGear", (0.92, 0.64, 0.24), metallic=0.88, roughness=0.22)
    make_pbr(
        "NeonCyan",
        (0.15, 0.85, 0.96),
        metallic=0.1,
        roughness=0.15,
        emission=(0.15, 0.85, 0.96),
        emission_strength=2.8,
    )
    make_pbr(
        "NeonAmber",
        (1.0, 0.52, 0.14),
        metallic=0.1,
        roughness=0.18,
        emission=(1.0, 0.52, 0.14),
        emission_strength=2.6,
    )
    make_pbr("WarmTerrain", (0.76, 0.54, 0.36), metallic=0.08, roughness=0.55)
    make_pbr(
        "OceanTeal",
        (0.10, 0.52, 0.68),
        metallic=0.25,
        roughness=0.14,
        emission=(0.08, 0.42, 0.58),
        emission_strength=0.35,
    )
    make_pbr("EmeraldPine", (0.18, 0.66, 0.42), metallic=0.05, roughness=0.42)
    make_pbr(
        "IridescentCore",
        (0.46, 0.56, 0.94),
        metallic=0.78,
        roughness=0.18,
        emission=(0.24, 0.32, 0.85),
        emission_strength=0.45,
    )


def setup_world_and_lights():
    scene = bpy.context.scene
    world = bpy.data.worlds.new("ShowcaseWorld")
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.045, 0.052, 0.068, 1.0)
    bg.inputs["Strength"].default_value = 1.0
    scene.world = world

    # Key sun light
    sun_data = bpy.data.lights.new("KeySun", "SUN")
    sun_data.energy = 4.2
    sun_data.color = (1.0, 0.96, 0.90)
    sun = bpy.data.objects.new("KeySun", sun_data)
    sun.rotation_euler = (math.radians(42), math.radians(-18), math.radians(32))
    scene.collection.objects.link(sun)

    # Cool fill light
    fill_data = bpy.data.lights.new("CoolFill", "AREA")
    fill_data.energy = 140.0
    fill_data.size = 5.0
    fill_data.color = (0.55, 0.78, 1.0)
    fill = bpy.data.objects.new("CoolFill", fill_data)
    fill.location = (-3.5, -2.5, 4.2)
    fill.rotation_euler = (math.radians(35), math.radians(-30), math.radians(-25))
    scene.collection.objects.link(fill)

    # Warm rim light
    rim_data = bpy.data.lights.new("WarmRim", "AREA")
    rim_data.energy = 180.0
    rim_data.size = 4.0
    rim_data.color = (1.0, 0.68, 0.40)
    rim = bpy.data.objects.new("WarmRim", rim_data)
    rim.location = (3.2, 3.2, 3.5)
    rim.rotation_euler = (math.radians(-45), math.radians(35), math.radians(135))
    scene.collection.objects.link(rim)


def make_camera(name, location, rotation_deg, lens=48, ortho_scale=None):
    cam_data = bpy.data.cameras.new(name)
    if ortho_scale:
        cam_data.type = "ORTHO"
        cam_data.ortho_scale = ortho_scale
    else:
        cam_data.lens = lens
    cam = bpy.data.objects.new(name, cam_data)
    cam.location = location
    cam.rotation_euler = tuple(math.radians(a) for a in rotation_deg)
    bpy.context.scene.collection.objects.link(cam)
    return cam


def set_phase(mod, value):
    for item in mod.node_group.interface.items_tree:
        if item.item_type == "SOCKET" and item.in_out == "INPUT" and item.name == "phase":
            if hasattr(mod, "properties") and hasattr(mod.properties, "inputs"):
                getattr(mod.properties.inputs, item.identifier).value = float(value)
            else:
                mod[item.identifier] = float(value)
            break
    mod.id_data.update_tag()


def main():
    args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else ["--still"]
    mode = "anim" if "--anim" in args else "still"

    bpy.ops.wm.read_factory_settings(use_empty=True)
    ext_mod.register()
    setup_materials()
    setup_world_and_lights()

    # Load stdlib modules into bpy.data.texts so `use ...` resolves them
    for std in ["math.bn", "sdf2d.bn", "curves2d.bn", "patterns2d.bn", "gp_tools2d.bn"]:
        with open(os.path.join(ROOT, "stdlib", std), encoding="utf-8") as f:
            bpy.data.texts.new(std).write(f.read())

    showcases = [
        {
            "slug": "showcase-chrono-hud",
            "file": "chrono_hud.bn",
            "group": "chrono hud",
            "cam_loc": (0.0, -4.15, 4.35),
            "cam_rot": (43.0, 0.0, 0.0),
            "lens": 45,
        },
        {
            "slug": "showcase-living-diorama",
            "file": "living_diorama.bn",
            "group": "living diorama",
            "cam_loc": (0.0, -4.35, 3.35),
            "cam_rot": (51.5, 0.0, 0.0),
            "lens": 46,
        },
        {
            "slug": "showcase-metaball-symphony",
            "file": "metaball_symphony.bn",
            "group": "metaball symphony",
            "cam_loc": (0.0, -4.05, 3.25),
            "cam_rot": (50.5, 0.0, 0.0),
            "lens": 46,
        },
    ]

    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 960
    scene.render.resolution_y = 640
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.view_settings.view_transform = "AgX" if "AgX" in ("Standard", "AgX") else "Standard"
    try:
        scene.view_settings.look = "AgX - Medium High Contrast"
    except Exception:
        scene.view_settings.view_transform = "Standard"

    os.makedirs(OUT_DIR, exist_ok=True)

    # Build all showcase objects
    built_items = []
    for cfg in showcases:
        with open(os.path.join(ROOT, "examples", cfg["file"]), encoding="utf-8") as f:
            src = f.read()
        build_source(src, cfg["file"])
        coll = bpy.data.collections.new(cfg["slug"])
        scene.collection.children.link(coll)
        obj = bpy.data.objects.new(cfg["slug"], bpy.data.meshes.new(cfg["slug"]))
        coll.objects.link(obj)
        mod = obj.modifiers.new("BaseNode", "NODES")
        mod.node_group = bpy.data.node_groups[cfg["group"]]
        cam = make_camera(
            f"Cam_{cfg['slug']}",
            cfg["cam_loc"],
            cfg["cam_rot"],
            lens=cfg["lens"],
        )
        built_items.append((cfg, coll, obj, mod, cam))

    if mode == "still":
        for cfg, coll, obj, mod, cam in built_items:
            for _, c, _, _, _ in built_items:
                c.hide_render = c is not coll
            scene.camera = cam
            set_phase(mod, 0.22)
            bpy.context.view_layer.update()
            out_png = os.path.join(OUT_DIR, f"{cfg['slug']}.png")
            scene.render.filepath = out_png
            bpy.ops.render.render(write_still=True)
            print("Rendered still:", out_png)
    else:
        num_frames = 48
        fps = 24
        for cfg, coll, obj, mod, cam in built_items:
            for _, c, _, _, _ in built_items:
                c.hide_render = c is not coll
            scene.camera = cam
            tmp_dir = os.path.join("/tmp", f"bn_{cfg['slug']}")
            os.makedirs(tmp_dir, exist_ok=True)
            for frame_idx in range(num_frames):
                phase = frame_idx / float(num_frames)
                set_phase(mod, phase)
                bpy.context.view_layer.update()
                frame_path = os.path.join(tmp_dir, f"frame_{frame_idx:04d}.png")
                scene.render.filepath = frame_path
                bpy.ops.render.render(write_still=True)
                if frame_idx == 10:
                    poster_path = os.path.join(OUT_DIR, f"{cfg['slug']}.png")
                    with open(frame_path, "rb") as fin, open(poster_path, "wb") as fout:
                        fout.write(fin.read())

            mp4_path = os.path.join(OUT_DIR, f"{cfg['slug']}.mp4")
            gif_path = os.path.join(OUT_DIR, f"{cfg['slug']}.gif")
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-framerate",
                    str(fps),
                    "-i",
                    os.path.join(tmp_dir, "frame_%04d.png"),
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    "-crf",
                    "21",
                    "-preset",
                    "slow",
                    "-movflags",
                    "+faststart",
                    mp4_path,
                ],
                check=True,
            )
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-framerate",
                    str(fps),
                    "-i",
                    os.path.join(tmp_dir, "frame_%04d.png"),
                    "-vf",
                    "scale=640:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=128[p];[s1][p]paletteuse=dither=bayer:bayer_scale=3",
                    gif_path,
                ],
                check=True,
            )
            print("Encoded MP4 & GIF:", mp4_path, gif_path)


if __name__ == "__main__":
    main()
