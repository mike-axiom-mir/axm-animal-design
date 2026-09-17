# Runtime — Animal persistent vertex-buffer receiver

Status: **bounded PASS on exact measured Runtime head `57d6f10ab04694d4fea8ef0803ac32f8623b15e6`**. This extends the existing Animal Runtime PR after pass 40. It does not change Animal source geometry, Rigging reconstruction semantics, Technical Art transport, Universal Creation product code, Art Direction authority, Visual QA authority, CANON, or production state.

## Bounded question

Pass 40 proved that the exact 41-key right-side direction-frame sequence can keep one Godot `ArrayMesh` resource instead of constructing 41, but it still clears and rebuilds one complete surface for every authored key.

This pass asks one narrower question:

> With topology, UVs and indices fixed over the exact 41-key receiver packet, can Godot keep one dynamic surface and update its changing vertex buffer in place while preserving rendered POSITION/NORMAL/TANGENT output and reducing proof-host submission cost?

## Measured candidate

Baseline remains pass 40: one persistent `ArrayMesh`, but `clear_surfaces()` plus `add_surface_from_arrays()` for every key.

The accepted candidate:

- creates one `ArrayMesh` and one surface with `Mesh.ARRAY_FLAG_USE_DYNAMIC_UPDATE`;
- proves UVs and indices are unchanged over all 41 keys before enabling the path;
- keeps `ArrayMesh` and surface identity stable;
- captures Godot's own exact engine-packed `vertex_data` from each verified surface-rebuild control key rather than reimplementing private vertex packing;
- applies one `surface_update_vertex_region()` call per key;
- leaves UV/attribute and index buffers untouched;
- uses one conservative custom AABB covering the complete 41-key motion envelope.

Measured representation change:

- surface rebuilds per 41-key playback: **41 -> 0 (100% fewer)**;
- surface constructions needed for the 41-key receiver: **41 -> 1 (97.5609756% fewer)**;
- persistent `ArrayMesh`: **1 -> 1**;
- vertex-region updates: **0 -> 41**, one per authored key;
- cached Godot-packed vertex payload: **1,680 B/key, 68,880 B for all 41 keys**.

## Before / after timing

Pinned target host: Godot **4.7.2**, GL Compatibility / Mesa llvmpipe GitHub proof host.

Protocol: five warmup sweeps plus 31 alternating measured sweeps, each covering all 41 keys.

- median sweep: **164 us -> 10 us (-93.9024%)**;
- p95 sweep: **183 us -> 11 us (-93.9891%)**.

These numbers measure the already-prepared submission path only. Capturing/preparing the 68,880 B engine-packed cache is excluded. They are proof-host observations, not target-device CPU/GPU/FPS/VRAM/thermal/battery claims.

## Render correctness and visual tradeoff

The final correctness gate does not depend on stale CPU-side surface metadata. A Godot target-renderer observer directly exercises:

- geometry POSITION through the rendered silhouette;
- NORMAL and TANGENT through a deterministic debug shader.

Across **all 41 control/candidate rendered pairs**:

- byte-identical pairs: **41/41**;
- changed pixels: **0**;
- maximum channel delta: **0 LSB**.

The observer is demonstrably sensitive: the baseline key-0 versus key-20 control changes **7,811 pixels** with a maximum channel delta of **214**, so the zero candidate delta is not a dead-render false positive.

Measured visual tradeoff: **`NONE_OBSERVED_41_OF_41_POSITION_NORMAL_TANGENT_DEBUG_RENDER_PAIRS_BYTE_IDENTICAL`**.

That is not production shaded approval. Fresh production-material shading remains for Art Direction / Visual QA.

The culling tradeoff is real: the all-motion custom AABB is **1.20289644x** the median authored-key AABB volume. It protects the persistent surface from stale-culling disappearance, but can keep the object inside visibility tests for a larger volume than a per-key rebuilt bound.

## Preserved failed evidence

No failed draft was rewritten into success.

1. Manual vertex-packing attempt — Runtime head `fbc9c8a86daa299c6a3bf2b9aa421cf30b01df41`, workflow `35267861278`, artifact `10516719596`, SHA-256 `a00a9af5192bc7c923e1f4a1891faa7880a3c47eec263d82c1e04e664eaf7413` — failed the receiving correctness gate.
2. Engine-packed attempt with CPU `surface_get_arrays()` as the acceptance observer — head `79c3fead177996e7b825885701c877c81a1f46c7`, workflow `35268361181`, artifact `10518260489`, SHA-256 `3c2c5ae33fc0706994aff24fbb491e54d175fe0826411fae6136dd8a8735a83c` — remained HOLD because the observer did not establish the renderer-visible update.
3. First rendered-observer workflow — head `050a4675d550312c533cea5fa24e5897ca32e8e0`, artifact `10517816717`, SHA-256 `f4fccfa5e47787c27da4b2558e48aca98cb3734e0bc63bcdc5f2dbf976ac9eb4` — failed in harness setup before measurement because the Camera3D was oriented before entering the SceneTree. The repair changed only camera setup order; candidate and acceptance gates remained unchanged.

The successful repaired workflow is `35269033255`; retained artifact `10517956976` is **351,092 B**, SHA-256 **`4e4062004015f4bf2f14c99b7179ee8b362063699a98c80dc383f4baf9740486`**, independently downloaded and rehashed to the same digest.

## Reuse boundary

This mechanism is reusable only after a receiver proves fixed topology/static side buffers, stable target-host update semantics, a safe culling envelope, and renderer-visible equivalence. It must not be generalized automatically to arbitrary deforming assets.

Still separate / HOLD:

- bilateral target-host receiving;
- continuous/interpolated playback;
- fresh production shaded A/B;
- target-device CPU/GPU/FPS/VRAM/thermal/battery;
- Art Direction acceptance;
- independent Visual QA acceptance;
- Technical Art adoption;
- UC extraction;
- CANON;
- production/game readiness.

The four AXM roots remain the merge gate: Truth, Agency / non-domination, Continuity, Wisdom before speed.
