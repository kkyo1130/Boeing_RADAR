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
    parser.add_argument("--engine", choices=("BLENDER_EEVEE_NEXT", "CYCLES"), default="BLENDER_EEVEE_NEXT")
    parser.add_argument("--samples", type=int, default=32)
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
    scene = bpy.context.scene
    scene.render.engine = args.engine
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
    key.location = (1, 8, 12)
    key_data.energy = 1700
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
    split_counts = {"train": 0, "val": 0, "test": 0}
    bounds = [p for o in mcp_objects for p in box_points(o)]
    center = sum(bounds, Vector((0, 0, 0))) / len(bounds)
    print("MCP center", tuple(center), "mesh count", len(mcp_objects), flush=True)
    for session in range(args.sessions):
        split = "test" if session in test_ids else "val" if session in val_ids else "train"
        rng = random.Random(args.seed + session * 100003)
        # Session-specific camera viewpoint and lighting: realistic train/test variation.
        az = rng.uniform(-.35, .35)
        el = rng.uniform(-.12, .24)
        dist = rng.uniform(17, 32)
        key_data.energy = rng.uniform(900, 2500)
        for frame in range(args.frames_per_session):
            bbox = None
            # Resample until the whole panel is visible. Do not silently
            # produce empty val/test sets when random views clip the target.
            for attempt in range(args.max_attempts):
                theta = az + rng.uniform(-.13, .13)
                elevation = el + rng.uniform(-.07, .07)
                distance = dist * rng.uniform(.9, 1.4)
                camera.location = center + Vector((
                    math.sin(theta) * distance,
                    math.sin(elevation) * distance,
                    math.cos(theta) * distance,
                ))
                target = center + Vector((rng.uniform(-.6, .6), rng.uniform(-.3, .3), 0))
                look_at(camera, target)
                camera.data.lens = rng.uniform(20, 34)
                bpy.context.view_layer.update()
                bbox = projected_bbox(scene, camera, mcp_objects)
                if bbox is not None:
                    break
            if bbox is None:
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
            split_counts[split] += 1
        print(f"session {session + 1}/{args.sessions} ({split})", flush=True)
    if any(count == 0 for count in split_counts.values()):
        raise RuntimeError(f"Empty dataset split: {split_counts}")
    with (output / "manifest.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(manifest[0]))
        writer.writeheader()
        writer.writerows(manifest)
    (output / "dataset.yaml").write_text(
        f"path: {output}\ntrain: images/train\nval: images/val\ntest: images/test\nnames:\n  0: mcp\n",
        encoding="utf-8")
    (output / "generation.json").write_text(json.dumps(
        {"glb": str(args.glb), "seed": args.seed, "sessions": args.sessions,
         "frames_per_session": args.frames_per_session, "rendered": len(manifest),
         "split_counts": split_counts,
         "note": "Approximate projected 3D bounding box; verify labels visually. Dynamic UI text is absent."},
        indent=2), encoding="utf-8")
    print(f"Generated {len(manifest)} labeled images in {output}", flush=True)


if __name__ == "__main__":
    main()
