# Organic Form Baseline 001

This first animal-design lane establishes one real renderer-neutral organic form study rather than a catalog of invented species.

## What it does

`examples/quadruped_neutral_001.json` authors a neutral quadruped through explicit:

- 24 spatial landmarks;
- 20 visible mass/segment regions;
- bilateral landmark pairs;
- bounded proportion checks;
- four declared bend-zone reserves for later rig/deformation review.

`src/axm_animal_design/organic_form.py` turns that source into `axm.surface-3d/v0.1` triangle geometry using neutral materials. The generated geometry is deterministic and can be consumed later by Universal Creation or another compatible tool without making this repo depend on UC at runtime.

The same generator produces front/side wire projections directly from generated triangle edges. CI retains the exact generated evidence JSON, summary and projections as the `quadruped-neutral-001-evidence` artifact.

## Why this is intentionally a form study

The first useful organic department proof should let us inspect masses, proportion, stance and joint placement before fur, skin, shaders or animation hide weak form. The baseline therefore avoids detailed surface treatment and does not pretend a disconnected mass study is a production skinned animal.

## Evidence meaning

A `PASS` from `declared-proportion-and-symmetry-intent` means only that the authored landmarks match the authored numeric proportion/symmetry contract. It is not a claim that those values are biologically correct.

Bend zones are emitted as `DECLARED_NOT_DEFORMATION_TESTED`. They are exact handoff coordinates/radii for the Rigging & Deformation specialist, not proof of weighting, edge flow, joint collapse resistance or motion quality.

The generator also checks bounded triangle indices and refuses degenerate triangles in its own produced primitives. Full manifold/self-intersection analysis belongs to the Geometry & Topology lane; when UC PR #133 is available as accepted shared machinery, this baseline is a suitable first organic mesh to challenge it.

## Non-claims

This lane does not establish:

- animal biology or anatomical correctness;
- muscle, skin or skeletal simulation;
- rigging, weight painting or animation quality;
- production retopology or a single connected deformable skin;
- collision/physics or gameplay readiness;
- target-engine import behavior;
- materials, fur, eyes or final look development;
- studio-wide organic style or mastery.

## Intended next handoffs

1. **3D Art Director** — inspect the generated side/front evidence for readable large masses and proportion before surface detail.
2. **Geometry & Topology** — run the shared topology diagnostic against this first real organic output once that lane is accepted, keeping component/disconnected-surface limits explicit.
3. **Rigging & Deformation** — use the exact bend-zone handoff to test whether the authored masses leave useful deformation room; do not inherit PASS from this lane.
4. **Materials / LookDev** — only after form review, add surface separation without using texture noise to compensate for weak masses.
5. **Capability Cartographer** — watch whether the landmark/mass/proportion contract transfers to character/nature/creature work before proposing a shared promotion.
