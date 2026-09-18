from pathlib import Path
import json
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from axm_animal_design.animation_motion import build_animation_frame
from axm_animal_design.animation_playback import inspect_sampled_playback

SPEC = json.loads((ROOT / "examples/quadruped_neutral_001.json").read_text())
PLAN = json.loads((ROOT / "examples/quadruped_rig_probe_001.json").read_text())
CLIP = json.loads((ROOT / "examples/quadruped_articulation_loop_001.json").read_text())


def _edges(surface):
    rows = []
    for primitive in surface["primitives"]:
        positions = primitive["positions"]
        seen = set()
        indices = primitive["indices"]
        for offset in range(0, len(indices), 3):
            tri = indices[offset:offset + 3]
            for a, b in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
                edge = tuple(sorted((int(a), int(b))))
                if edge in seen:
                    continue
                seen.add(edge)
                rows.append((positions[edge[0]], positions[edge[1]]))
    return rows


def _projection(point, view):
    x, y, z = (float(point[0]), float(point[1]), float(point[2]))
    if view == "side":
        return x, z
    if view == "front":
        return y, z
    raise ValueError(view)


def _bounds(frames, view):
    pts = []
    for frame in frames:
        for primitive in frame["surface"]["primitives"]:
            pts.extend(_projection(point, view) for point in primitive["positions"])
    xs = [point[0] for point in pts]
    ys = [point[1] for point in pts]
    return min(xs), max(xs), min(ys), max(ys)


def _path_data(surface, view, bounds, x0, y0, panel_w, panel_h):
    xmin, xmax, ymin, ymax = bounds
    margin = 24
    span_x = max(xmax - xmin, 1e-9)
    span_y = max(ymax - ymin, 1e-9)
    scale = min((panel_w - 2 * margin) / span_x, (panel_h - 2 * margin) / span_y)
    cx = x0 + panel_w / 2
    cy = y0 + panel_h / 2
    rows = []
    for a, b in _edges(surface):
        ax, ay = _projection(a, view)
        bx, by = _projection(b, view)
        sax = cx + (ax - (xmin + xmax) / 2) * scale
        say = cy - (ay - (ymin + ymax) / 2) * scale
        sbx = cx + (bx - (xmin + xmax) / 2) * scale
        sby = cy - (by - (ymin + ymax) / 2) * scale
        rows.append(f"M{sax:.2f},{say:.2f}L{sbx:.2f},{sby:.2f}")
    return "".join(rows)


def _animated_svg(path, frames, report):
    width = 960
    height = 720
    panel_w = 920
    panel_h = 270
    panel_x = 20
    side_y = 88
    front_y = 390
    bounds = {view: _bounds(frames, view) for view in ("side", "front")}
    key_times = [index / report["sample_rate_hz"] / report["duration_seconds"] for index in range(report["displayed_frame_count_per_cycle"] + 1)]
    key_times_text = ";".join(f"{value:.9f}" for value in key_times)

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f'<rect width="{width}" height="{height}" fill="white"/>',
        '<text x="20" y="28" font-family="monospace" font-size="17">quadruped-articulation-loop-001 — exact 40 Hz sampled playback</text>',
        '<text x="20" y="50" font-family="monospace" font-size="12">discrete authored samples only; no interpolation; not target-engine, controller, gameplay, gait or aesthetic acceptance</text>',
        f'<text x="20" y="70" font-family="monospace" font-size="11">source={report["source_digest"][:12]} rig={report["rig_plan_digest"][:12]} clip={report["clip_digest"][:12]} weighting={report["rig_weighting_profile"]}</text>',
        f'<rect x="{panel_x}" y="{side_y}" width="{panel_w}" height="{panel_h}" fill="none" stroke="#b0b0b0"/>',
        f'<rect x="{panel_x}" y="{front_y}" width="{panel_w}" height="{panel_h}" fill="none" stroke="#b0b0b0"/>',
        f'<text x="{panel_x + 8}" y="{side_y + 18}" font-family="monospace" font-size="12">side</text>',
        f'<text x="{panel_x + 8}" y="{front_y + 18}" font-family="monospace" font-size="12">front</text>',
    ]

    frame_count = report["displayed_frame_count_per_cycle"]
    for index, frame in enumerate(frames):
        values = ["1" if slot == index else "0" for slot in range(frame_count)]
        values.append("1" if index == 0 else "0")
        values_text = ";".join(values)
        time_seconds = report["display_schedule_seconds"][index]
        initial_opacity = "1" if index == 0 else "0"
        side_path = _path_data(frame["surface"], "side", bounds["side"], panel_x, side_y, panel_w, panel_h)
        front_path = _path_data(frame["surface"], "front", bounds["front"], panel_x, front_y, panel_w, panel_h)
        lines.extend([
            f'<g id="frame-{index:02d}" opacity="{initial_opacity}">',
            f'<animate attributeName="opacity" dur="{report["duration_seconds"]:.9f}s" repeatCount="indefinite" calcMode="discrete" keyTimes="{key_times_text}" values="{values_text}"/>',
            f'<path d="{side_path}" fill="none" stroke="#202020" stroke-width="0.70"/>',
            f'<path d="{front_path}" fill="none" stroke="#202020" stroke-width="0.70"/>',
            f'<text x="760" y="687" font-family="monospace" font-size="13">frame {index:02d}/39  t={time_seconds:.3f}s</text>',
            '</g>',
        ])

    metrics = report["metrics"]
    lines.append(
        f'<text x="20" y="690" font-family="monospace" font-size="11">seam endpoint exact={str(metrics["exact_endpoint_seam"]).lower()}; '
        f'wrap step={metrics["wrap_step_m"]:.9f} m; authored final step={metrics["authored_last_adjacent_step_m"]:.9f} m; '
        f'residual={metrics["wrap_step_residual_m"]:.3e} m</text>'
    )
    lines.append('</svg>')
    svg_text = "\n".join(lines) + "\n"
    ET.fromstring(svg_text)
    path.write_text(svg_text, encoding="utf-8")


report = inspect_sampled_playback(SPEC, PLAN, CLIP)
if report["gate"] != "PASS_DISCRETE_SAMPLED_PLAYBACK_SEAM":
    raise SystemExit("animation sampled-playback seam gate failed")

frames = [
    build_animation_frame(SPEC, PLAN, CLIP, time_seconds)
    for time_seconds in report["display_schedule_seconds"]
]

out = ROOT / "evidence"
out.mkdir(parents=True, exist_ok=True)
(out / "quadruped_articulation_loop_001.playback.json").write_text(
    json.dumps(report, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
_animated_svg(out / "quadruped_articulation_loop_001.playback.svg", frames, report)

summary = {
    "schema": "axm.animal-animation-sampled-playback-summary/v0.1",
    "source_digest": report["source_digest"],
    "neutral_surface_digest": report["neutral_surface_digest"],
    "rig_plan_digest": report["rig_plan_digest"],
    "rig_weighting_profile": report["rig_weighting_profile"],
    "clip_digest": report["clip_digest"],
    "playback_mode": report["playback_mode"],
    "duration_seconds": report["duration_seconds"],
    "sample_rate_hz": report["sample_rate_hz"],
    "endpoint_inclusive_source_sample_count": report["endpoint_inclusive_source_sample_count"],
    "displayed_frame_count_per_cycle": report["displayed_frame_count_per_cycle"],
    "display_frame_interval_seconds": report["display_frame_interval_seconds"],
    "metrics": report["metrics"],
    "gate": report["gate"],
    "truth": report["truth"],
}
(out / "quadruped_articulation_loop_001.playback_summary.json").write_text(
    json.dumps(summary, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
print(json.dumps(summary, sort_keys=True))
