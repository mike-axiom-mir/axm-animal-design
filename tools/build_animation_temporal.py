from pathlib import Path
import json
import math
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from axm_animal_design.animation_motion import build_animation_frame
from axm_animal_design.animation_temporal import inspect_temporal_continuity

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


def _contact_sheet(path, frames, report):
    panel_w = 190
    panel_h = 300
    margin = 26
    width = panel_w * len(frames)
    height = panel_h * 2 + 90
    bounds = {view: _bounds(frames, view) for view in ("side", "front")}
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f'<rect width="{width}" height="{height}" fill="white"/>',
        '<text x="16" y="24" font-family="monospace" font-size="16">quadruped-articulation-loop-001 — 9-sample temporal review board</text>',
        '<text x="16" y="45" font-family="monospace" font-size="12">actual sampled surfaces; smoothstep-v0; structural review aid only — not gait/runtime/art-direction acceptance</text>',
    ]
    for row_index, view in enumerate(("side", "front")):
        xmin, xmax, ymin, ymax = bounds[view]
        span_x = max(xmax - xmin, 1e-9)
        span_y = max(ymax - ymin, 1e-9)
        scale = min((panel_w - 2 * margin) / span_x, (panel_h - 2 * margin) / span_y)
        row_y = 65 + row_index * panel_h
        lines.append(f'<text x="8" y="{row_y + 16}" font-family="monospace" font-size="11">{view}</text>')
        for panel_index, frame in enumerate(frames):
            x0 = panel_index * panel_w
            cx = x0 + panel_w / 2
            cy = row_y + panel_h / 2 + 6
            lines.append(f'<rect x="{x0 + 1}" y="{row_y + 1}" width="{panel_w - 2}" height="{panel_h - 2}" fill="none" stroke="#cccccc" stroke-width="1"/>')
            for a, b in _edges(frame["surface"]):
                ax, ay = _projection(a, view)
                bx, by = _projection(b, view)
                sax = cx + (ax - (xmin + xmax) / 2) * scale
                say = cy - (ay - (ymin + ymax) / 2) * scale
                sbx = cx + (bx - (xmin + xmax) / 2) * scale
                sby = cy - (by - (ymin + ymax) / 2) * scale
                lines.append(f'<line x1="{sax:.2f}" y1="{say:.2f}" x2="{sbx:.2f}" y2="{sby:.2f}" stroke="#202020" stroke-width="0.55"/>')
            time_seconds = float(frame["time_seconds"])
            lines.append(f'<text x="{x0 + 8}" y="{row_y + panel_h - 10}" font-family="monospace" font-size="11">t={time_seconds:.3f}s</text>')
    metrics = report["metrics"]
    footer_y = height - 18
    lines.append(
        f'<text x="16" y="{footer_y}" font-family="monospace" font-size="11">max adjacent vertex step={metrics["maximum_adjacent_vertex_step_m"]:.9f} m; '
        f'peak excursion={metrics["peak_vertex_excursion_from_neutral_m"]:.9f} m; '
        f'step fraction={metrics["maximum_adjacent_step_fraction_of_peak_excursion"]:.6f} <= {metrics["step_fraction_limit"]:.2f}</text>'
    )
    lines.append('</svg>')
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


report = inspect_temporal_continuity(SPEC, PLAN, CLIP)
if report["gate"] != "PASS_LOOP_TEMPORAL_CONTINUITY":
    raise SystemExit("animation temporal continuity gate failed")

out = ROOT / "evidence"
out.mkdir(parents=True, exist_ok=True)
json_path = out / "quadruped_articulation_loop_001.temporal.json"
json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

frames = [
    build_animation_frame(SPEC, PLAN, CLIP, index / report["sample_rate_hz"])
    for index in report["review_sample_indices"]
]
_contact_sheet(out / "quadruped_articulation_loop_001.temporal_review.svg", frames, report)

summary = {
    "schema": "axm.animal-animation-temporal-summary/v0.1",
    "source_digest": report["source_digest"],
    "neutral_surface_digest": report["neutral_surface_digest"],
    "rig_plan_digest": report["rig_plan_digest"],
    "rig_weighting_profile": report["rig_weighting_profile"],
    "clip_digest": report["clip_digest"],
    "sample_rate_hz": report["sample_rate_hz"],
    "sample_count": report["sample_count"],
    "review_sample_times_seconds": report["review_sample_times_seconds"],
    "metrics": report["metrics"],
    "gate": report["gate"],
    "truth": report["truth"],
}
(out / "quadruped_articulation_loop_001.temporal_summary.json").write_text(
    json.dumps(summary, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
print(json.dumps(summary, sort_keys=True))
