# Animal transported-frame Materials lookdev

This is a bounded **Materials / LookDev receiving observer** on the existing Animal Materials lane. It does not define or adopt a new rigging, transport, Runtime, or production tangent-space policy.

## Question

Given the already-measured post-skin direction-frame mismatch in the transported Animal receiver, what is its visible consequence under the same deterministic tangent-space diagnostic, and does Rigging's exact position-derived owner-frame reconstruction recover the accepted owner-frame appearance baseline?

## Exact compared frames

All modes share the same skinned/reconstructed positions, UVs, topology, probe material, lights, cameras, and render host. Only the direction frame changes:

1. `owner_rederived` — Rigging's accepted owner-space deformed frame.
2. `transported_static_skin` — the exact Technical Art static NORMAL/TANGENT after skinning, with the already-audited Gram–Schmidt tangent witness used only for comparison.
3. `position_reconstructed` — Rigging's exact post-skin position-derived reconstruction.
4. `position_reconstructed_flipped_w_negative` — the same reconstruction with tangent handedness deliberately inverted as a renderer-sensitivity control.

The probe is the same deterministic periodic tangent-space field already established by Materials PR #24; it is diagnostic and is **not** a production normal map.

## Immutable provenance pins

- Rigging reconstruction owner head: `81ab44eab2e13bed95187610a476be2b2c4667a7`
- Rigging reconstruction module blob: `c9916c62e2081922b8eb7ec0b3cd1c25c019b2f6`
- Rigging reconstruction artifact: `10476642320`
- Rigging reconstruction artifact SHA-256: `2d11836cc7c1ada5146752d0b6205d0e4f476cd085ee8be4964e2f024f70fa58`
- Technical Art transport head: `4649d144841fbd1f3f43e9c7deb6f37b91fbd93d`
- Technical Art transport artifact: `10474385703`
- Technical Art transport artifact SHA-256: `7fc2a7f5d745da593e8762efa98e13661f84a057b1eb60921d576c366e71d7bb`
- Exact transported GLB SHA-256: `ecb122e3274929c3d99bc8e29a472aaa2657bcb16b13331a4f1972bb6ec6b493`
- Existing Materials owner-frame baseline ancestor: `e9d5c451b16bd05d2419248f58bef911f83dc1e8`
- Art Direction owner-frame baseline packet: `7e08ae260128a90d9c9af7cfd6c9bc67eb85f680`

The workflow consumes Rigging's exact owner code from its pinned commit rather than copying the reconstruction algorithm into Materials.

## Truth boundary

A successful render comparison is evidence about **appearance in this exact Godot GL Compatibility receiver only**. It does not by itself authorize Technical Art to adopt the reconstruction, establish a Runtime implementation, certify production tangent space, approve a production normal map, replace final Art Direction or independent Visual QA, alter CANON, or claim production readiness.

Any failure, neutral result, or mixed result is retained as evidence rather than repaired by changing the material until it looks favorable.