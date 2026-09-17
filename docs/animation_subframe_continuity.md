# Animation dense subframe continuity witness

Contract: `axm.animal-animation-subframe-continuity/v0.1`

This gate asks one narrow Animation-owned question: can the existing unchanged `quadruped-articulation-loop-001` source curve be evaluated between its retained 40 Hz authored samples through the existing rig deformation implementation without revealing a hidden between-key discontinuity?

It does **not** change the clip. The retained identities remain the exact source, rig plan, `smoothstep-v0` weighting, clip digest, `1.0 s` duration, 41 endpoint-inclusive authored samples, `+18°` front-elbow peak and `+14°` hind-knee peak.

## Positive witness

The audit evaluates 8 deterministic subframes inside every authored 25 ms interval, producing a `320 Hz` / `321`-sample diagnostic sequence. This is diagnostic sampling only; it is not a request to ship or render the animation at 320 Hz.

For every dense sample it drives the exact existing deformation implementation. It then checks:

- stable surface topology;
- exact rebind to every one of the 41 authored samples;
- exact neutral loop closure within the retained numerical tolerance;
- time-reversal symmetry of the current raised-cosine pulse;
- bilateral angle symmetry;
- monotonic rise and fall;
- bounded nonzero dense geometric steps;
- analytic source velocity of zero at loop start, midpoint and loop end;
- analytic source acceleration equality across the loop seam.

A green result is `PASS_DENSE_SUBFRAME_SOURCE_CURVE_CONTINUITY_WITNESS`.

## Fail-closed negative control

The evidence build also injects a test-only `+0.05°` `sin²` bump into `front-elbow-L` strictly between authored samples 13 and 14. The bump is exactly zero at both authored keys and therefore leaves **all 41 retained authored samples unchanged**.

The dense audit must still return `HOLD_DENSE_SUBFRAME_SOURCE_CURVE_CONTINUITY` because the hidden subframe mutation breaks bilateral/time symmetry and produces a geometric signal between keys. This demonstrates that the method contributes information that the 41 authored-sample checks alone cannot provide.

The mutated sequence is never an Animation candidate and is retained only as a verifier negative control.

## Truth boundary

This witness is source-curve and posed-geometry evidence. It does **not** establish target-engine interpolation, production skeleton/skin transport, Technical Art receiver adoption, wall-clock delivery, renderer frame pacing, perceptual smoothness or acting quality, collision/physics/input/gameplay, target-device performance, CANON, production readiness, or Animation mastery.
