# Runtime Animal direction-frame ArrayMesh reuse

This Runtime lane consumes the exact green Technical Art target-host reference at `43e2cf0ddf3096c665aa7c29b4393dcafdd26114`, workflow `35251459815`, artifact `10509802878` / SHA-256 `912a1c391edc51ef5a3e2ac2dfc0344bc400f2606fe7f3eabf2c1424cf4faddc`.

The earlier Runtime draft was based on Technical Art head `8dd9e1aea586df6d156b6b54eba0fa751e3bf76f`. Exact workflow history later showed that head had not completed the real target-host proof, so Runtime preserves that failed lineage and rebases its measurement authority onto the repaired green Technical Art receiver instead of treating the earlier assumption as fact.

Technical Art now proves that all 41 right-side owner-reconstructed frames can be applied to real Godot 4.7.2 `ArrayMesh` surfaces and read back within its unchanged receiver tolerances. Runtime does not replace that ownership or reconstruction algorithm.

## Bounded performance question

The Technical Art reference creates a fresh `ArrayMesh` resource for every authored frame. The topology, UVs and index domain do not change across those 41 frames; positions, normals and tangents do.

The smallest lifecycle optimization is therefore:

- baseline: construct 41 `ArrayMesh` resources for one 41-key playback;
- candidate: construct one `ArrayMesh` resource, preserve its object identity, clear/rebuild its one surface for each key;
- keep exactly the same owner-reconstructed frame arrays and the same surface submission/readback path.

This reduces only **resource-object construction**. It deliberately does **not** claim that vertex/index buffers are updated in place. Surface construction remains 41 -> 41 in this pass.

## Evidence contract

The runtime probe:

- consumes the exact Technical Art target-host packet regenerated from the green `43e2cf0d...` receiver lineage;
- independently re-proves the Technical Art baseline before measuring the Runtime candidate;
- validates all 41 baseline and candidate readbacks with the same position, normal, tangent, UV, tangent-W and index tolerances used by the Technical Art reference;
- uses the same stable near-parallel direction-angle metric as the green Technical Art probe: `atan2(|a×b|/(|a||b|), (a·b)/(|a||b|))`;
- keeps the original `0.015°` angular tolerance and `0.00025` direction-vector tolerance unchanged;
- self-checks the angle metric at `0.01°` before accepting evidence;
- requires the candidate `ArrayMesh` instance ID to remain stable;
- measures alternating baseline/candidate 41-key sweeps after warmup on the GitHub/Godot proof host;
- rejects a result if a mutated receipt relabels the candidate as 41 resource constructions;
- retains exact before/after timing and readback metrics in `runtime-mesh-reuse-summary.json`;
- records that fresh shaded rendering was not performed here.

The proof-host timing is diagnostic only. It is not a target-device CPU/GPU/FPS/VRAM claim.

## Why dynamic buffer updates are held for a later lane

Godot exposes dynamic mesh/update APIs, but moving from surface rebuilds to true region updates changes the receiving mechanism and its packed attribute layout. That is a separate higher-risk step. This pass first establishes whether stable resource identity itself is safe before touching dynamic vertex/attribute regions.

## Visual / authority boundary

No positions, normals, tangents, UVs or indices are reauthored. If the 41-key readback remains within the exact Technical Art receiving gates, the bounded visual tradeoff is recorded only as:

`NONE_OBSERVED_AT_RECEIVER_ARRAY_READBACK_ALL_41_KEYS__FRESH_SHADED_RENDER_NOT_RUN`

That is not a final rendered-appearance decision. Art Direction and Visual QA retain appearance acceptance. Technical Art retains target-host receiving authority; Rigging/Geometry retain owner-frame semantics; Runtime owns only the lifecycle candidate and measurement.

A green result does not establish bilateral Runtime receiving, continuous interpolated playback, dynamic region updates, fresh shaded equivalence, target-device performance, Art Direction or Visual QA acceptance, Universal Creation extraction, CANON or production readiness. `axm-create-me` remains coordination-only, and the four AXM roots remain the merge gate.
