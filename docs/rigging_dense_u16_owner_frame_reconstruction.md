# Rigging dense normalized-u16 owner-frame reconstruction

This bounded Rigging observer closes one specific gap between already-green evidence lanes without changing the Animal source, rig, weights, clip, Technical-Art transport, Runtime representation, Materials, or target host.

## Question

Animation already proved the exact Runtime normalized-u16 `WEIGHTS_0` candidate stays inside Rigging's positional deformation bound at 321 deterministic samples / 320 Hz across the transported glTF `LINEAR` rotation channel. Rigging separately proved that, at the 41 authored keys, the owner normal/tangent frame can be reconstructed from transported skinned POSITION plus the fixed Geometry source/render mapping and UV identity.

This observer asks only whether that same post-skin owner-frame reconstruction remains structurally valid at all 321 exact Animation subframes for the exact normalized-u16 Runtime candidate.

## Exact dependencies

- predecessor Rigging head: `e4ce8c1f4c3deb55220cf962206d51013d0cfe73`;
- authored-key reconstruction predecessor: `81ab44eab2e13bed95187610a476be2b2c4667a7`;
- Animation dense guard head: `37f5a77d39d221be796ac3b0c3a179fd3c86a8c0`;
- Animation artifact: `10485697941`, archive SHA-256 `496e744f6bd3c8ad3b0648298cceecd7c7170a651f510674a92c957424a954e3`;
- Runtime head: `e7874c4a8dca1db48bc66f3546c2134f7d724456`;
- Runtime artifact: `10477292250`, archive SHA-256 `76455589e0dde3327f72ebff6a117a2ce12ff57edaaf1d0e61304056d03063c3`;
- FLOAT control GLB: `8d9bfb80369bda09eaad786a35833cd5e04da5e608211f53648daaa1cde29566`;
- normalized-u16 candidate GLB: `81c5422f8cf13ca65a253d3b05ebcf88fc0b20601dfb466b3c92f0d5e28dafcb`;
- historical rig donor: `04760112deb81a8d145226fe7ee02923107c9916`;
- weighting: unchanged `smoothstep-v0`.

The workflow checks out and hashes the exact Animation guard implementation rather than silently re-authoring Animation interpolation semantics.

## Observer

For every dense sample:

1. consume the exact Animation `LINEAR` quaternion interpolation result;
2. evaluate the unchanged source Rigging pose at the resulting owner angle;
3. skin the exact retained FLOAT control and normalized-u16 candidate POSITION fields;
4. collapse UV-split render positions through Geometry's fixed render-to-source mapping;
5. re-derive the unchanged Rigging owner normal/tangent frame from each reconstructed posed shape;
6. compare FLOAT reconstruction and u16 reconstruction independently to the source-owner frame;
7. compare normalized-u16 reconstruction directly to FLOAT reconstruction;
8. retain representative samples at dense indices `0 / 80 / 160 / 240 / 320`.

The existing static transported `NORMAL/TANGENT` direction-frame mismatch remains an explicit HOLD. This observer does not reinterpret static attribute skinning as correct; it tests only the already-separated post-skin reconstruction constraint.

## Fail-closed control

At a between-authored-key sample (`0.3375 s`), the observer applies the same `+64` u16 child-weight-step class used by Animation, but coherently to all UV-split render representatives of one Geometry source vertex. It must break either the retained position or direction-frame tolerance. The mutation is verifier-only and is never written back to a source or Runtime candidate.

## Truth boundary

A green result proves only a structural dense-subframe reconstruction constraint for the exact identities above. It does not grant Animation timing/interpolation/playback acceptance, Technical-Art target-runtime implementation, Runtime/controller/device acceptance, Materials/Art/QA appearance acceptance, biological motion, arbitrary clips, source/rig adoption, CANON, production readiness, or mastery.
