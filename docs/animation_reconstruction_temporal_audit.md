# Animation reconstruction temporal audit

Schema: `axm.animal-animation-transport-reconstruction-temporal-stability/v0.1`

This is an Animation-owned **consumer audit** over the exact retained Rigging post-skin owner-frame reconstruction evidence. It does not reconstruct normals or tangents itself, alter the rig, modify the authored clip, adopt a Technical Art receiver, or claim production transport.

## Question

Given Rigging's exact 41-key reconstruction PASS, do the measured reconstruction errors stay temporally symmetric and loop-closed over the unchanged `quadruped-articulation-loop-001` sample sequence?

The distinction matters because a per-key spatial PASS can still hide an asymmetric or isolated temporal error spike. Animation owns the sampled temporal comparison, while Rigging retains spatial reconstruction authority and Technical Art retains receiver implementation authority.

## Pinned identities

- Animation baseline head: `731ce2d8bf3481bde1a9731f361fb9820efcdfc1`
- clip digest: `407903cbc5fe8803fc6a749e128b7736ebf139b414e61f77d9bbd32fc46f427b`
- clip: `1.0 s`, `40 Hz`, `41` endpoint-inclusive samples, `smoothstep-v0`
- Rigging reconstruction head: `81ab44eab2e13bed95187610a476be2b2c4667a7`
- Rigging reconstruction artifact: `10476642320`
- artifact SHA-256: `2d11836cc7c1ada5146752d0b6205d0e4f476cd085ee8be4964e2f024f70fa58`

## Gate

A PASS requires:

- exact 41-sample ordering and bounded transported float-time residuals around the authored 25 ms spacing;
- exact neutral-loop identity and expected midpoint peak;
- mirrored reconstruction-error series across the rise/fall halves;
- bounded adjacent change in position, normal, tangent and orthogonality reconstruction errors;
- identical reconstruction-error state at samples 0 and 40;
- zero tangent-handedness mismatches across all retained keys.

The negative control injects a `0.0001°` normal-error spike at sample 13. This is intentionally below Rigging's `0.001°` per-key direction tolerance, so the Animation audit must reject the asymmetric temporal drift independently rather than merely duplicating the Rigging spatial gate.

## Truth boundary

A green result proves only sampled temporal stability of the **measurement witness** at the exact 41 authored keys. It does not establish a Technical Art reconstruction receiver, production skin-normal/tangent transport, continuous interpolation, wall-clock playback pacing, final shaded appearance, animation timing/personality acceptance, runtime-controller/state-machine behavior, physics/collision/input/gameplay, target-device performance, CANON, production readiness, or Animation mastery.

The intended handoff is to preserve the exact clip unchanged until Technical Art adopts and proves a concrete receiver. Animation can then exercise this same clip through that receiver before changing timing, amplitude, keys, weighting or interpolation semantics.
