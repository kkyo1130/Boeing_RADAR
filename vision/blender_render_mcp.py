"""Blender headless synthetic MCP detection dataset generator.

Usage:
 blender -b -t 4 --python vision/blender_render_mcp.py -- \
   --glb frontend/public/models/cockpit.glb --output vision/data/mcp_blender \
   --sessions 20 --frames-per-session 100

The GLB is authored as a 737NG-inspired demo, not certified 737 geometry.
"""
import argparse
import csv
import json
import math
import random
import sys
from pathlib import Path

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector


def arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--glb", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("vision/data/mcp_blender"))
    parser.add_argument("--sessions", type=int, default=20)
    parser.add_argument("--frames-per-session", type=int, default=100)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--engine", choices=("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT", "CYCLES"), default="BLENDER_EEVEE")
    parser.add_argument("--samples", type=int, default=32)
    parser.add_argument("--digits", action=argparse.BooleanOptionalAction, default=True,
                        help="Render synthetic HDG/ALT values in MCP display windows")
    parser.add_argument("--view", choices=("pilot", "overhead"), default="pilot",
                        help="Pilot-eye interior views by default; overhead for debugging only")
    parser.add_argument("--max-attempts", type=int, default=40,
                        help="Camera framing attempts per requested frame")
    return parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])


def descendants(root):
    return [root, *root.children_recursive]


def box_points(obj):
    return [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]


def projected_bbox(scene, camera, objects):
    points = [world_to_camera_view(scene, camera, p) for obj in objects if obj.type == "MESH" for p in box_points(obj)]
    if not points or any(p.z <= 0 for p in points):
        return None
    xmin, xmax = min(p.x for p in points), max(p.x for p in points)
    ymin, ymax = min(p.y for p in points), max(p.y for p in points)
    # Do not label heavily clipped or minuscule targets.
    if xmin < 0.01 or ymin < 0.01 or xmax > .99 or ymax > .99:
        return None
    if (xmax - xmin) < .035 or (ymax - ymin) < .015:
        return None
    return ((xmin + xmax) / 2, 1 - (ymin + ymax) / 2, xmax - xmin, ymax - ymin)


def look_at(obj, target):
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()



def make_display_text(display, name, digits, material):
    """Add centered emission text just in front of an imported display face.

    Support local XY faces (depth Z) and imported XZ faces (depth Y).
    Parenting preserves the GLB object's rotation (including glTF Y-up conversion).
    """
    local = [Vector(v) for v in display.bound_box]
    low = [min(v[i] for v in local) for i in range(3)]
    high = [max(v[i] for v in local) for i in range(3)]
    width = high[0] - low[0]
    dimensions = [high[i] - low[i] for i in range(3)]
    depth_axis = min(range(3), key=lambda i: dimensions[i])
    if depth_axis not in (1, 2):
        raise RuntimeError(f"Unsupported display face axes: {display.name}, {dimensions}")
    up_axis = 2 if depth_axis == 1 else 1
    height = dimensions[up_axis]
    depth = dimensions[depth_axis]
    if not (width > 0 and height > 0 and depth < min(width, height)):
        raise RuntimeError(
            f"Unexpected display geometry {display.name}: "
            f"dimensions {(width, height, depth)}; cannot place text safely"
        )
    font = bpy.data.curves.new(name, type="FONT")
    font.body = digits
    font.align_x = "CENTER"
    font.align_y = "CENTER"
    font.size = height * 0.72
    font.space_character = 1.1
    obj = bpy.data.objects.new(name, font)
    bpy.context.scene.collection.objects.link(obj)
    obj.parent = display
    location = [(low[i] + high[i]) / 2 for i in range(3)]
    offset = max(0.012, depth * 0.25)
    if depth_axis == 1:
        # XZ face: X is text right, Z is text up; front faces negative Y.
        obj.rotation_euler = (math.pi / 2, 0, 0)
        location[1] = low[1] - offset
    else:
        location[2] = high[2] + offset
    obj.location = location
    obj.data.materials.append(material)
    return obj


def display_bbox(scene, camera, display):
    """Projected display window coordinates, normalized YOLO xywh."""
    return projected_bbox(scene, camera, [display])

def main():
    args = arguments()
    if not args.glb.is_file():
        raise FileNotFoundError(f"Missing GLB: {args.glb}")
    if args.sessions < 3 or args.frames_per_session < 1:
        raise ValueError("Need >=3 sessions and >=1 frame per session")
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.gltf(filepath=str(args.glb.resolve()))
    root = bpy.data.objects.get("mcp_root")
    if root is None:
        raise ValueError("No mcp_root object in GLB; inspect imported object names")
    mcp_objects = [o for o in descendants(root) if o.type == "MESH"]
    if not mcp_objects:
        raise ValueError("mcp_root has no mesh descendants")
    # Label only the front MCP face. The mcp_root hierarchy also contains
    # glareshield and lower sill, whose projected corners extend into the PFD/ND.
    faces = [o for o in mcp_objects if o.name == "mcp_face"]
    if len(faces) != 1:
        raise RuntimeError(f"Expected exactly one mcp_face mesh; found {len(faces)}")
    mcp_face = faces[0]
    displays = {}
    for key in ("heading", "altitude"):
        matches = [o for o in mcp_objects if o.name == key + "_display"]
        if len(matches) != 1:
            raise RuntimeError(f"Expected one {key}_display mesh; got {len(matches)}")
        displays[key] = matches[0]
    scene = bpy.context.scene
    available_engines = {item.identifier for item in scene.render.bl_rna.properties["engine"].enum_items}
    selected_engine = args.engine
    if selected_engine not in available_engines:
        if selected_engine == "BLENDER_EEVEE_NEXT" and "BLENDER_EEVEE" in available_engines:
            selected_engine = "BLENDER_EEVEE"
        elif selected_engine == "BLENDER_EEVEE" and "BLENDER_EEVEE_NEXT" in available_engines:
            selected_engine = "BLENDER_EEVEE_NEXT"
        else:
            raise RuntimeError(f"Unsupported render engine {args.engine}; available: {sorted(available_engines)}")
    scene.render.engine = selected_engine
    digit_texts = {}
    if args.digits:
        digit_material = bpy.data.materials.new("MCP_synthetic_digits_amber")
        digit_material.diffuse_color = (1.0, 0.38, 0.04, 1.0)
        digit_material.use_nodes = True
        nodes = digit_material.node_tree.nodes
        nodes.clear()
        emission = nodes.new("ShaderNodeEmission")
        emission.inputs["Color"].default_value = (1.0, 0.31, 0.018, 1.0)
        emission.inputs["Strength"].default_value = 2.2
        output_node = nodes.new("ShaderNodeOutputMaterial")
        digit_material.node_tree.links.new(emission.outputs["Emission"], output_node.inputs["Surface"])
        digit_texts["heading"] = make_display_text(displays["heading"], "synthetic_HDG", "000", digit_material)
        digit_texts["altitude"] = make_display_text(displays["altitude"], "synthetic_ALT", "00000", digit_material)
    if args.engine == "CYCLES":
        scene.cycles.samples = args.samples
    else:
        scene.render.image_settings.file_format = "PNG"
        scene.render.film_transparent = False
    scene.render.resolution_x = args.width
    scene.render.resolution_y = args.height
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.world.color = (0.16, 0.16, 0.16)
    camera_data = bpy.data.cameras.new("dataset_camera")
    camera = bpy.data.objects.new("dataset_camera", camera_data)
    scene.collection.objects.link(camera)
    scene.camera = camera
    camera.data.type = "PERSP"
    camera.data.lens = 38
    key_data = bpy.data.lights.new("dataset_key", type="AREA")
    key = bpy.data.objects.new("dataset_key", key_data)
    scene.collection.objects.link(key)
    key_data.shape = "DISK"
    key_data.size = 8
    key.location = (0, -2.5, 6.5)
    key_data.energy = 2300
    fill_data = bpy.data.lights.new("dataset_fill", type="AREA")
    fill_light = bpy.data.objects.new("dataset_fill", fill_data)
    scene.collection.objects.link(fill_light)
    fill_data.shape = "DISK"
    fill_data.size = 7
    fill_data.energy = 1400
    fill_light.location = (-4, -5, 5)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    # A fixed split by entire independent camera/lighting session, never individual frames.
    # Guarantee all three splits have data for >=3 sessions.
    session_ids = list(range(args.sessions))
    random.Random(args.seed).shuffle(session_ids)
    n_test = max(1, round(args.sessions * .1))
    n_val = max(1, round(args.sessions * .1))
    test_ids = set(session_ids[:n_test])
    val_ids = set(session_ids[n_test:n_test + n_val])
    manifest = []
    ocr_manifest = []
    split_counts = {"train": 0, "val": 0, "test": 0}
    bounds = box_points(mcp_face)
    center = sum(bounds, Vector((0, 0, 0))) / len(bounds)
    print("MCP center", tuple(center), "mesh count", len(mcp_objects), flush=True)
    for session in range(args.sessions):
        split = "test" if session in test_ids else "val" if session in val_ids else "train"
        rng = random.Random(args.seed + session * 100003)
        # GLB was authored in Three.js (Y-up): Blender import maps the
        # pilot seats (original +Z) to negative Blender Y.
        # Keep the camera INSIDE the cockpit, facing forward toward MCP.
        seat_x = rng.choice((-4.3, 4.3, 0.0))
        base_y = rng.uniform(-7.2, -5.0)
        eye_z = rng.uniform(3.5, 4.8)
        key_data.energy = rng.uniform(2000, 3600)
        fill_data.energy = rng.uniform(1100, 2200)
        for frame in range(args.frames_per_session):
            hdg = rng.randrange(360)
            alt = rng.randrange(0, 41000, 100)
            if args.digits:
                digit_texts["heading"].data.body = f"{hdg:03d}"
                digit_texts["altitude"].data.body = f"{alt:05d}"
            bbox = None
            for attempt in range(args.max_attempts):
                if args.view == "pilot":
                    camera.location = Vector((
                        seat_x + rng.uniform(-0.65, 0.65),
                        base_y + rng.uniform(-0.45, 0.45),
                        eye_z + rng.uniform(-0.25, 0.25),
                    ))
                    target = center + Vector((
                        rng.uniform(-0.4, 0.4),
                        rng.uniform(-0.2, 0.2),
                        rng.uniform(-0.15, 0.15),
                    ))
                    camera.data.lens = rng.uniform(20, 34)
                else:
                    camera.location = center + Vector((
                        rng.uniform(-7, 7), rng.uniform(-2, 2),
                        rng.uniform(12, 24),
                    ))
                    target = center
                    camera.data.lens = rng.uniform(20, 34)
                look_at(camera, target)
                bpy.context.view_layer.update()
                # Fit the complete MCP in the frame without moving the pilot eye.
                # The panel is ~12 units wide; fixed 20-34mm lenses can clip it.
                projected = [world_to_camera_view(scene, camera, point)
                             for obj in mcp_objects for point in box_points(obj)]
                if projected and all(point.z > 0 for point in projected):
                    extent = max(max(abs(point.x - .5), abs(point.y - .5))
                                 for point in projected)
                    if extent > .46:
                        camera.data.lens *= .46 / extent
                        bpy.context.view_layer.update()
                bbox = projected_bbox(scene, camera, [mcp_face])
                heading_box = display_bbox(scene, camera, displays["heading"])
                altitude_box = display_bbox(scene, camera, displays["altitude"])
                if bbox is not None and heading_box is not None and altitude_box is not None:
                    break
            if bbox is None or heading_box is None or altitude_box is None:
                raise RuntimeError(
                    f"No valid MCP framing after {args.max_attempts} attempts "
                    f"for session {session}, frame {frame}. "
                    "Check imported GLB axes and object hierarchy."
                )
            filename = f"session{session:03d}_frame{frame:04d}"
            image_rel = Path("images") / split / (filename + ".png")
            label_rel = Path("labels") / split / (filename + ".txt")
            (output / image_rel).parent.mkdir(parents=True, exist_ok=True)
            (output / label_rel).parent.mkdir(parents=True, exist_ok=True)
            scene.render.filepath = str(output / image_rel)
            bpy.ops.render.render(write_still=True)
            (output / label_rel).write_text("0 " + " ".join(f"{v:.6f}" for v in bbox) + "\n", encoding="utf-8")
            manifest.append(dict(source_path=str(image_rel), image_path=str(image_rel),
                                 label_path=str(label_rel), session_id=f"session{session:03d}",
                                 split=split, x=bbox[0], y=bbox[1], width=bbox[2], height=bbox[3]))
            ocr_manifest.append(dict(image_path=str(image_rel), split=split,
                                     session_id=f"session{session:03d}",
                                     heading=f"{hdg:03d}", altitude=f"{alt:05d}",
                                     hdg_cx=heading_box[0], hdg_cy=heading_box[1],
                                     hdg_w=heading_box[2], hdg_h=heading_box[3],
                                     alt_cx=altitude_box[0], alt_cy=altitude_box[1],
                                     alt_w=altitude_box[2], alt_h=altitude_box[3]))
            split_counts[split] += 1
        print(f"session {session + 1}/{args.sessions} ({split})", flush=True)
    if any(count == 0 for count in split_counts.values()):
        raise RuntimeError(f"Empty dataset split: {split_counts}")
    with (output / "manifest.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(manifest[0]))
        writer.writeheader()
        writer.writerows(manifest)
    with (output / "ocr_manifest.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(ocr_manifest[0]))
        writer.writeheader()
        writer.writerows(ocr_manifest)
    (output / "dataset.yaml").write_text(
        f"path: {output}\ntrain: images/train\nval: images/val\ntest: images/test\nnames:\n  0: mcp\n",
        encoding="utf-8")
    (output / "generation.json").write_text(json.dumps(
        {"glb": str(args.glb), "seed": args.seed, "sessions": args.sessions,
         "frames_per_session": args.frames_per_session, "rendered": len(manifest),
         "split_counts": split_counts, "view": args.view, "digits": args.digits,
         "note": "MCP bounding box is projected from mcp_face only (excludes glareshield and lower sill); inspect rendered label overlays before training."},
        indent=2), encoding="utf-8")
    print(f"Generated {len(manifest)} labeled images in {output}", flush=True)


if __name__ == "__main__":
    main()
