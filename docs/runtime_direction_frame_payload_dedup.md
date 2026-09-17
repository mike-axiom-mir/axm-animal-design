# Runtime direction-frame exact-key payload dedup — pass 42

Status: `PASS_ANIMAL_EXACT_KEY_VERTEX_PAYLOAD_DEDUP__LOWER_CACHE__41_RENDER_PAIRS_IDENTICAL__HOLD_DEVICE_ART`

Exact measured Runtime head: `911d1443eff2188a28727f98b79747058998e443`.

This pass extends the existing Runtime PR #29 / pass-41 persistent dynamic-surface receiver. It does not change the Technical Art packet, source geometry, normals, tangents, UVs, indices, persistent surface representation, motion envelope, Universal Creation, or ownership boundaries.

## Bounded question

Pass 41 removed surface rebuilds but cached one exact Godot-packed 1,680-byte vertex payload for every authored key, for 68,880 bytes across 41 keys. Pass 42 asks whether byte-identical authored-key payloads can share cached storage without interpolation, quantization, regeneration, retiming, or reinterpretation.

## Exact result

The 41-key cache contains 21 unique exact payload byte streams. The exact key-to-unique sequence is:

`0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,19,18,17,16,15,14,13,12,11,10,9,8,7,6,5,4,3,2,1,0`

Prepared payload bytes therefore fall:

- full cache: `41 × 1,680 B = 68,880 B`;
- exact-deduplicated payload pool: `21 × 1,680 B = 35,280 B`;
- payload bytes saved: `33,600 B`;
- payload-byte reduction: `48.780487804878%`.

The proof receipt explicitly excludes the key-to-unique mapping container from that byte figure. This is therefore a prepared-payload byte budget, not a claim about total runtime heap or allocator overhead.

All 41 authored keys reconstruct the exact pass-41 packed byte stream before submission. Both control and candidate keep one persistent `ArrayMesh`, one persistent dynamic surface, zero surface rebuilds, and 41 `surface_update_vertex_region()` calls per playback.

## Visual evidence

Pinned Godot 4.7.2 GL Compatibility / Mesa llvmpipe compared all 41 full-cache versus deduplicated-cache receiver states through the existing POSITION/NORMAL/TANGENT debug observer:

- render pairs: `41`;
- byte-identical pairs: `41/41`;
- changed pixels: `0`;
- maximum channel delta: `0 LSB`.

Observer sensitivity remains live: key 0 versus key 20 changes `7,811` pixels, maximum channel delta `214`.

Measured visual tradeoff: `NONE_OBSERVED_41_OF_41_DEBUG_RENDER_PAIRS_BYTE_IDENTICAL`.

This is not production-material shaded acceptance.

## CPU tradeoff

Five warmups plus 31 alternating 41-key sweeps show that the extra cache lookup is not free on the proof host:

- full 41-payload cache median: `9 us`;
- 21-payload deduplicated cache median: `14 us` (`+55.5556%`);
- full-cache p95: `9 us`;
- deduplicated-cache p95: `15 us` (`+66.6667%`).

These very small proof-host timings are retained as observations only and are not an acceptance gate or a target-device claim. Pass 42 is a memory/cache-footprint option, not an unconditional speed win. Pass 41 remains the stronger default when 33.6 KB of prepared payload storage is acceptable.

## Verification

Dedicated workflow `35269893851 — Runtime Animal exact-key payload dedup evidence` completed `SUCCESS`.

Retained artifact:

- ID `10518013399`;
- size `686,887 B`;
- SHA-256 `111a43c131dce45f552fad307ce7d93b1a7f0733ec7ea4b994b5ca2912c9b31d`;
- independently downloaded and rehashed to the same digest.

Negative controls fail closed when the cache reduction is removed or when render equivalence is weakened to 40/41 pairs.

## Truth boundary

Pass 42 proves only exact-byte authored-key cache sharing for this right-side 41-key receiver. It does not prove a generic symmetric-animation rule, total runtime heap saving, target-device benefit, bilateral receiving, continuous/interpolated playback, production shaded equivalence, Art Direction acceptance, Visual QA acceptance, UC extraction, CANON, or production readiness.

The four AXM roots remain the merge gate: Truth, Agency / non-domination, Continuity, Wisdom before speed.
