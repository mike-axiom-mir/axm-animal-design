# axm-animal-design

AXM animal / creature design department.

This repository grows organic animal/creature design capability through explicit source state, editable form, retained evidence and cross-specialist handoffs. It is one department inside the wider AXM 3D Studio campaign; it is not `axm-create-me` itself.

## Current first proof

`examples/quadruped_neutral_001.json` is a neutral form study used to exercise readable large masses, proportion, bilateral structure and deformation handoff coordinates before materials or animation can hide weak form.

Run:

```bash
python -m unittest discover -s tests -v
python tools/build_baseline.py
```

The evidence builder emits exact generated triangle geometry, front/side wire projections and a digest-bound summary under `evidence/`.

See `docs/ORGANIC_FORM_BASELINE.md` for evidence meaning and non-claims.
