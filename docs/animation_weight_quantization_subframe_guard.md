# Animation u16 weight subframe trajectory guard

Schema: `axm.animal-animation-u16-weight-subframe-guard/v0.1`

This is an Animation-owned temporal evidence method. It changes no source motion, rig, weights, Runtime quantizer, glTF producer, controller, or gameplay state.

It consumes two exact retained dependencies:

- Runtime PR #27 exact head `e7874c4a8dca1db48bc66f3546c2134f7d724456`, artifact `10477292250`, containing the exact FLOAT control and normalized-u16 `WEIGHTS_0` candidate;
- Rigging PR #25 exact head `e4ce8c1f4c3deb55220cf962206d51013d0cfe73`, artifact `10478912800`, containing the 41-authored-key deformation bound and preserved direction-frame HOLD.

The existing Animation clip remains `quadruped-articulation-loop-001`, digest `407903cbc5fe8803fc6a749e128b7736ebf139b414e61f77d9bbd32fc46f427b`, with the existing `1.0 s / 40 Hz / 41-key` identity unchanged.

## Bounded question

Rigging already bounds FLOAT-control versus normalized-u16 skinned POSITION error across the 41 authored keys. This guard asks a different Animation-owned question: when the exact transported glTF `LINEAR` quaternion rotation channel is evaluated between those keys, does the exact Runtime candidate remain inside the same positional bound throughout the motion trajectory?

The guard deterministically evaluates eight subframes per authored interval: `321` total samples at diagnostic density `320 Hz`. At each sample it evaluates the exact retained transported rotation, skins the exact retained render vertices with each exact retained weight representation, and records the maximum control/candidate POSITION delta.

The gate additionally requires:

- recomputed authored-key maximum to reproduce the exact Rigging receipt;
- exact neutral loop closure for both representations within the stated bound;
- time-mirrored error-series stability;
- the dense maximum to remain within Rigging's existing `2e-7 m` positional bound;
- a verifier-only `+64` u16 child-weight-step mutation at `0.3375 s`, strictly between authored keys 13 and 14, to exceed the bound and fail closed.

The negative control is not an Animation candidate and never changes retained source or Runtime bytes. It exists only to prove the dense temporal observer can detect a between-key representation defect that a 41-key-only check would not directly observe.

## Truth boundary

A green result establishes only a deterministic dense temporal POSITION comparison for these exact retained transported GLBs and their exact glTF interpolation contract. It does not establish Godot or another engine's interpolation implementation equivalence, production weight adoption, deformed NORMAL/TANGENT direction-frame correctness, final visual quality, wall-clock frame delivery, controller/state-machine behavior, physics/collision/input/gameplay, target-device performance, CANON, production readiness, or mastery.
