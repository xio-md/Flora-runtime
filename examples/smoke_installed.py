"""Check an installed wheel without a GPU; add --gpu for RGB/depth/VLM validation.

Run with `python -I smoke_installed.py [--gpu]` outside the source checkout.
No window or development assets are needed. This file can accompany the wheel.
"""
from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

import numpy as np
import flora as dr
import flora_backend
from flora_backend.glb_builder import GlbSceneBuilder
from flora_runtime import get_runtime_layout


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def tool(layout, name):
    return layout["module_dir"] / (name + (".exe" if sys.platform == "win32" else ""))


def install_check(layout):
    root = layout["python_dir"].resolve()
    check(Path(dr.__file__).resolve().parent == root / "flora", "Flora imported from another installation")
    check(Path(flora_backend.__file__).resolve().parent == root / "flora_backend",
          "Flora backend imported from another installation")
    sys.path.insert(0, str(layout["module_dir"]))
    # Use the same Windows DLL-directory registration as the Python renderer.
    import os
    directory = os.add_dll_directory(str(layout["module_dir"])) if sys.platform == "win32" else None
    try:
        native = importlib.import_module("FloraRenderPyNative")
        check(Path(native.__file__).resolve().parent == layout["module_dir"].resolve(),
              "Native module imported from another installation")
        for name in ("flora-vlm-bake", "flora-vlm-inspect", "flora-vlm-delta"):
            result = subprocess.run([str(tool(layout, name)), "--help"],
                                    check=True, capture_output=True, text=True, timeout=30)
            check("usage" in (result.stdout + result.stderr).lower(), f"Missing help output: {name}")
        return {"native_module": str(Path(native.__file__).resolve()), "cli_help": "passed"}
    finally:
        if directory is not None:
            directory.close()


def render_check():
    camera = dr.PinholeCamera(
        name="camera", pose=dr.MatrixTransform(((1, 0, 0, 0), (0, 1, 0, 0),
                                               (0, 0, 1, 3), (0, 0, 0, 1))),
        film=dr.Film((64, 48)), filter=dr.Filter(1), spp=1, fov=45,
    )
    surface = dr.PlasticSurface(name="red", kd=dr.ColorTexture((.8, .1, .05, 1)))
    shape = dr.RigidShape(name="quad", surface=surface,
                         vertices=((-1, -1, 0), (1, -1, 0), (1, 1, 0), (-1, 1, 0)),
                         triangles=((0, 1, 2), (0, 2, 3)), normals=((0, 0, 1),) * 4,
                         uvs=((0, 0), (1, 0), (1, 1), (0, 1)))
    dr.init()
    try:
        scene = dr.create_scene()
        scene.init(dr.Render(name="smoke", spectrum=dr.SRGBSpectrum(), integrator=dr.WavePathIntegrator()))
        scene.update_surface(surface)
        scene.update_shape(shape)
        scene.update_camera(camera, denoise=False)
        frame = scene.render_sensor(camera)
        check(frame.color.shape == (48, 64, 4), "Incorrect RGB shape")
        check(frame.depth.shape == (48, 64), "Incorrect depth shape")
        check(np.isfinite(frame.depth).all(), "Non-finite depth")
        check(abs(float(frame.depth[24, 32]) - 3.) < 1e-4, "Expected 3 m optical-axis depth")
        rgb = frame.color[24, 32, :3].astype(int)
        check(rgb[0] > rgb[1] and rgb[0] > rgb[2] and rgb[0] > 0, "Red surface was not rendered")
        return dict(rgb=rgb.tolist(), center_depth_m=float(frame.depth[24, 32]))
    finally:
        dr.destroy()


def bake_check(layout):
    builder = GlbSceneBuilder()
    material = builder.add_material("white", np.array([.7, .7, .7, 1]), 1, 0, np.zeros(3), True)
    # A horizontal receiving plane and a downward directional light.
    builder.add_mesh("floor", np.array([[-1, 0, 1], [1, 0, 1], [1, 0, -1], [-1, 0, -1]], dtype=np.float32),
                     np.array([[0, 1, 2], [0, 2, 3]], dtype=np.uint32),
                     np.array([[0, 1, 0]] * 4, dtype=np.float32), np.zeros((4, 2), dtype=np.float32),
                     material, np.eye(4, dtype=np.float32))
    builder.add_light(name="sun", light_type="directional", color=np.ones(3),
                      intensity=2, direction=np.array([0, -1, 0]))
    with tempfile.TemporaryDirectory(prefix="flora-vlm-smoke-") as work:
        root = Path(work)
        scene = root / "scene.glb"
        output = root / "scene.fvlm"
        scene.write_bytes(builder.build())
        subprocess.run([str(tool(layout, "flora-vlm-bake")), "--scene", str(scene), "--output", str(output),
                        "--bounds", "0", "0.5", "0", "0", "0.5", "0", "--cell-size", "0.5",
                        "--samples", "64", "--bounces", "2", "--seed", "17", "--deterministic"],
                       cwd=work, check=True, timeout=180)
        result = subprocess.run([str(tool(layout, "flora-vlm-inspect")), str(output), "--json"],
                                cwd=work, check=True, capture_output=True, text=True, timeout=30)
        report = json.loads(result.stdout)
        check(report["compatible"] and report["valid_probe_count"] == 1, "VLM probe invalid")
        check(np.isfinite(report["coefficient_range"]).all() and report["coefficient_range"][1] > 1e-5,
              "VLM bake has no finite positive lighting")
        return dict(valid_probes=report["valid_probe_count"], coefficient_range=report["coefficient_range"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gpu", action="store_true", help="Run real headless RGB, depth and VLM bake")
    args = parser.parse_args()
    layout = get_runtime_layout(verify=True)
    check(layout is not None, "Install the release wheel before running this example")
    report = dict(runtime=str(layout["runtime_root"]), version=layout["version"],
                  installation=install_check(layout), gpu="not_run")
    if args.gpu:
        report.update(gpu="passed", render=render_check(), vlm=bake_check(layout))
    print(json.dumps(report, indent=2))
    print("PASS: installed Flora " + ("RGB, metric depth and VLM bake (headless)" if args.gpu
                                      else "native import and CLI checks; GPU NOT tested"))


if __name__ == "__main__":
    main()
