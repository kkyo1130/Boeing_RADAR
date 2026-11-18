"""Audit a GLB's 737NG-inspired MCP geometry in Blender (no manufacturer CAD verification)."""
import argparse
import json
import sys
from pathlib import Path
import bpy
from mathutils import Vector

p = argparse.ArgumentParser()
p.add_argument("--glb", type=Path, required=True)
p.add_argument("--output", type=Path, default=Path("vision/data/mcp_model_audit.json"))
args = p.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=str(args.glb.resolve()))
objects = bpy.data.objects
root = objects.get("mcp_root")
if root is None:
    raise RuntimeError("mcp_root missing")
members = [o for o in objects if root in o.parent_recursive]
meshes = [o for o in members if o.type == "MESH"]
names = [o.name for o in members]
expected = ["mcp_face", "heading_display", "altitude_display", "speed_display",
            "heading_knob", "altitude_knob", "speed_knob"]
found = {name: any(n == name or n.startswith(name + ".") for n in names) for name in expected}
points = [o.matrix_world @ Vector(c) for o in meshes for c in o.bound_box]
mins = [min(p[i] for p in points) for i in range(3)]
maxs = [max(p[i] for p in points) for i in range(3)]
report = {
    "model": str(args.glb), "mcp_root": root.name,
    "mesh_count": len(meshes), "expected_objects": found,
    "mcp_world_bounds": {"min": mins, "max": maxs},
    "limitations": [
        "Original source describes this as an original simulated cockpit, not Boeing CAD.",
        "Geometry dimensions are arbitrary visualization units, not certified aircraft measurements.",
        "Runtime HDG/ALT text is generated in React and is not baked into the GLB.",
        "Boeing 737-800 fidelity requires visual reference comparison and real-camera validation."
    ]
}
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))
