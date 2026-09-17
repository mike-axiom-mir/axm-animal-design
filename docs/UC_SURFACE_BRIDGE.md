# Animal-design -> Universal Creation surface bridge

Status: EXPERIMENTAL TECHNICAL-ART INTEGRATION

This bridge exists because animal-design and Universal Creation can share a portable surface label while still having different source conventions, evidence ownership and revision identities. The bridge makes those boundaries explicit rather than treating a matching schema name as proof of integration.

The animal source convention is metres with `+X forward, +Y left, +Z up`. Universal Creation's portable surface/GLB path uses metres in its Y-up / +Z-forward convention, requires a top-level surface `name`, and carries material color as `#RRGGBB[AA]` text.

## Historical form-study bridge

`axm_animal_design.uc_bridge.adapt_form_evidence_for_uc()` preserves the original first-pass Technical Art path for the disconnected organic form study:

- validates exact animal evidence identity and refuses unknown coordinate systems or units;
- maps `[x_forward, y_left, z_up] -> [-y_left, z_up, x_forward]`;
- reverses every triangle winding because this source-to-target map changes handedness;
- transforms normals through the same axis map;
- preserves vertex colors and PBR scalar factors;
- converts local linear `base_color` RGBA into UC's bounded hex material field;
- adds the UC-required surface name and removes local-only `units` from the wire packet;
- never changes the original organic-form evidence in place.

The historical workflow remains pinned to Universal Creation commit:

`640bd7dc177b90e023aad879b4c00051df7f4ee3`

That evidence remains valid for that exact disconnected form-study lineage and is not relabelled as connected-topology evidence.

## Connected Geometry successor bridge

Geometry PR #4 later produced a separate source-derived connected forelimb candidate. Technical Art therefore adds a successor transport path rather than silently substituting that candidate into the historical form-study receipt.

Exact Geometry producer revision:

`feb4b24cd36bcc879173138d240754f71db34834`

Exact candidate identity:

`front-left-connected-chain-001`

Candidate SHA-256:

`6e620ce4b1d810b259011d0d22d38ba7c7eea0e2500177df2bf28e08fe1caf6c`

The successor proof rebuilds that candidate from the exact Geometry checkout. The Technical Art branch does not copy its positions or indices into a second source of truth.

Because the Geometry candidate intentionally owns only positions/indices, `build_candidate_source_primitive()` supplies only the transport attributes required by the already-existing UC portable surface contract:

- positions and indices remain Geometry-owned and byte-semantically unchanged before coordinate conversion;
- vertex normals are derived as an explicit transport-only average of incident unit face normals, matching the neutral Animal form-study method;
- the unchanged neutral Animal source material is attached explicitly;
- those normals/materials are **not** claimed to be final authored shading data;
- `adapt_geometry_candidate_for_uc()` then applies the same explicit Animal -> UC coordinate/winding/material conversion as the historical bridge.

`require_candidate_identity()` fails closed if the rebuilt Geometry candidate drifts from the pinned candidate digest. The retained CI proof includes an intentional 1 mm position mutation and requires that mutation to be rejected.

The current successor proof is pinned to Universal Creation commit:

`9a4ab8156772536526dd75bb2acab81e9b88f517`

No Animal topology rule, radius policy, rig weighting, animation semantics or source-material authority is moved into Universal Creation. UC only receives its existing portable surface contract.

## Exact cross-repo proof

`.github/workflows/uc-surface-bridge.yml` now keeps two evidence jobs separate:

1. the historical disconnected form-study -> pinned historical UC proof;
2. the connected Geometry candidate -> pinned current UC proof.

The connected proof:

1. checks out the exact Technical Art head, exact Geometry producer revision and exact current UC revision;
2. rebuilds the connected candidate from Geometry-owned source landmarks/regions;
3. requires the exact candidate digest before transport;
4. adds transport-only normals plus the unchanged neutral Animal source material;
5. converts through the explicit Animal -> UC coordinate/material contract;
6. publishes through UC's real `publish_glb()` implementation;
7. re-verifies the emitted GLB with UC's real `verify_glb()`;
8. requires the candidate and verified GLB triangle counts to remain equal;
9. retains the UC surface, GLB, receipt and all three exact checkout identities;
10. fails closed on candidate-identity drift.

This is a receiving-domain integration proof. It is not a copy of UC's GLB implementation or Geometry's topology generator inside Technical Art.

## Truth boundary

A green connected successor bridge proves only that the exact connected Animal Geometry candidate can be rebuilt from its pinned producer revision, converted through the explicit Animal -> UC portable-surface boundary, emitted by the pinned UC GLB generator and re-verified without changing triangle count.

It does **not** prove that the candidate is canonical, visually accepted or production topology. It does not establish final authored normals/tangents/UVs/materials, skeleton/skin/weight transport, deformation quality, animation transport, engine/runtime/controller import, collision/gameplay behavior, target-device performance, CANON or production readiness.

The bridge remains in `axm-animal-design`. This activation provides no evidence that the Animal-specific boundary should be moved into Universal Creation or Profession Fabric.
