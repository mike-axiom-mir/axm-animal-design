# Runtime Animal direction-frame ArrayMesh reuse

This Runtime lane begins from the exact Technical Art target-host reference at `8dd9e1aea586df6d156b6b54eba0fa751e3bf76f`. Technical Art already proves that all 41 right-side owner-reconstructed frames can be applied to real Godot 4.7.2 `ArrayMesh` surfaces and read back within its receiver tolerances. Runtime does not replace that ownership or reconstruction algorithm.

## Bounded performance question

The current Technical Art reference creates a fresh `ArrayMesh` resource for every authored frame. The topology, UVs and index domain do not change across those 41 frames; positions, normals and tangents do.

The smallest lifecycle optimization is therefore:

- baseline: construct 41 `ArrayMesh` resources for one 41-key playback;
- candidate: construct one `ArrayMesh` resource, preserve its object identity, clear/rebuild its one surface for each key;
- keep exactly the same owner-reconstructed frame arrays and the same surface submission/readback path.

This reduces only **resource-object construction**. It deliberately does **not** claim that vertex/index buffers are updated in place. Surface construction remains 41 -> 41 in this pass.

## Evidence boundary

The runtime probe:

- consumes the exact Technical Art target-host packet;
- validates all 41 baseline and candidate readbacks with the same position, normal, tangent, UV, tangent-W and index tolerances used by the Technical Art reference;
- requires the candidate `ArrayMesh` instance ID to remain stable;
- measures alternating baseline/candidate 41-key sweeps after warmup on the GitHub/Godot proof host;
- rejects a result if a mutated receipt relabels the candidate as 41 resource constructions;
- records that fresh shaded rendering was not performed here.

The proof-host timing is diagnostic only. It is not a target-device CPU/GPU/FPS/VRAM claim.

## Why dynamic buffer updates are held for a later lane

Godot exposes dynamic mesh/update APIs, but moving from surface rebuilds to true region updates changes the receiving mechanism and its packed attribute layout. That is a separate higher-risk step. This pass first establishes that stable resource identity itself is safe before touching dynamic vertex/attribute regions.

## Authority / truth boundary

A green result does not establish bilateral runtime receiving, continuous interpolated playback, dynamic region updates, fresh shaded equivalence, target-device performance, Art Direction or Visual QA acceptance, Universal Creation extraction, CANON or production readiness. `axm-create-me` remains coordination-only, and the four AXM roots remain the merge gate.
