# Runtime compiled post-skin direction-frame plan

This Runtime lane consumes, without changing, the Rigging-owned post-skin owner-frame reconstruction and the Technical Art receiving contract that adopted it.

## Performance question

The owner implementation is intentionally evidence-heavy. On every posed key it rebuilds source representative groups, deep-copies a posed candidate, rebuilds pose-local layout metadata, emits an evidence-grade normal record including a candidate digest, and recomputes UV deltas/determinants for all tangent triangles.

Those checks are useful when establishing truth, but topology, UVs and render/source identity are fixed for this receiving asset. The bounded Runtime hypothesis is therefore:

> Compile the immutable mapping/topology/UV derivative facts once, then perform only the pose-dependent position, normal, tangent and handedness work on each update.

## What is preserved

The compiled plan does not alter:

- source positions or topology;
- the exact 42-source / 84-render vertex identity;
- UVs or render indices;
- Rigging's logical-quad normal derivation;
- tangent Gram-Schmidt semantics;
- tangent handedness;
- the transported 41-key animation;
- the Technical Art source GLB;
- the Technical Art receiving contract;
- Universal Creation.

The exact-head evidence builder compares the existing owner reconstruction against the compiled Runtime path at all 41 transported keys. A PASS requires exact frame-array identity, zero handedness mismatch, an independently detected plan-corruption mutation, and a measured proof-host median CPU reduction.

## Deliberate boundary

This is not yet the real target-runtime implementation requested by Technical Art, Art Direction and Visual QA. It is the smallest performance-oriented receiving plan before that port: prove that the static work can be factored out without changing the owner frame, then carry that compiled contract into the target engine separately.

A green result does **not** establish bilateral runtime receiving, continuous/interpolated playback, fresh shaded equivalence, target-device CPU/GPU/FPS/VRAM, Art Direction acceptance, Visual QA acceptance, CANON or production readiness.
