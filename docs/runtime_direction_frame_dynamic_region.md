# Runtime — Animal persistent dynamic vertex/direction regions

Status: bounded Runtime / Optimization evidence lane. This extends the existing Animal Runtime PR after the pass-40 `ArrayMesh` object-reuse result. It does not change Animal source geometry, Rigging reconstruction semantics, Technical Art transport, Universal Creation product code, Art Direction authority, Visual QA authority, CANON, or production state.

## Question

Pass 40 proved that the exact 41-key right-side direction-frame sequence can keep one Godot `ArrayMesh` resource instead of constructing 41 resources, but it still clears and rebuilds one full surface at every authored key.

This successor asks one narrower question:

> With topology, UVs and indices fixed across the exact 41-key receiver packet, can Godot keep one persistent surface and update only the changing POSITION plus encoded NORMAL/TANGENT vertex-buffer regions, while preserving the exact receiver arrays and reducing proof-host submission cost?

## Candidate boundary

Baseline is the already-proven pass-40 lifecycle path: one persistent `ArrayMesh`, but `clear_surfaces()` plus `add_surface_from_arrays()` for every key.

Candidate:

- creates one `ArrayMesh`;
- creates one surface with `Mesh.ARRAY_FLAG_USE_DYNAMIC_UPDATE`;
- proves UVs and indices are unchanged over all 41 keys before enabling the candidate;
- keeps the same surface identity through playback;
- updates the position byte region with `surface_update_vertex_region()`;
- updates the packed normal/tangent byte region with a second `surface_update_vertex_region()` call;
- never updates UV or index regions;
- uses a conservative custom AABB covering every position from all 41 authored keys so a stale per-frame AABB cannot clip the moving surface.

The normal/tangent byte encoder mirrors Godot's uncompressed vertex-buffer octahedral encoding. The candidate is accepted only if real Godot readback is exact-array identical to the pass-40 surface-rebuild baseline across every key.

## Measurement

The probe runs on pinned Godot 4.7.2. It uses five warmup sweeps and 31 alternating measured sweeps. Each sweep applies all 41 authored keys.

The evidence records:

- surface construction/rebuild counts;
- vertex-region update call counts;
- exact buffer strides and update bytes;
- cached update-payload bytes;
- baseline and candidate median/p95 sweep time;
- Technical Art receiving tolerances for POSITION/NORMAL/TANGENT/UV/index data;
- exact candidate-vs-baseline receiver-array identity;
- full-motion custom-AABB volume versus per-frame AABB volumes.

The candidate must beat the baseline median on this proof host. Those timings are not target-device CPU/GPU/FPS/VRAM, thermal, battery, or total-frame claims.

## Visual / culling tradeoff

If the receiver arrays remain exact-array identical, no source shading input has changed at the measured keys. That still does not constitute fresh shaded-render acceptance.

The persistent surface also needs one conservative full-motion AABB. This protects against stale-culling disappearance, but can be less tight than a per-frame rebuilt AABB and therefore may keep the object visible to culling for a larger spatial volume. The exact envelope expansion is retained for Art/Runtime review rather than hidden as a free optimization.

Fresh shaded A/B, bilateral receiving, continuous/interpolated playback, target-device performance, Art Direction acceptance, Visual QA acceptance and adoption remain separate HOLDs.

## Reuse rule

This mechanism is reusable only for receivers that prove all of the following first:

1. topology/index domain is fixed;
2. static attribute regions really are static;
3. the runtime exposes stable persistent-buffer update semantics;
4. a safe motion/culling envelope is established;
5. updated raw buffer encoding re-reads equivalently through the target host.

A successful Animal example must not be silently generalized to arbitrary deforming assets.

The four AXM roots remain the merge gate: Truth, Agency / non-domination, Continuity, Wisdom before speed.
