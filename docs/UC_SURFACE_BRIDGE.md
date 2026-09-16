# Animal-design -> Universal Creation surface bridge

Status: EXPERIMENTAL TECHNICAL-ART INTEGRATION

This bridge exists because the first animal-design form study and Universal Creation were using the same `axm.surface-3d/v0.1` label while not actually sharing the same wire contract.

The animal form evidence is authored in metres with `+X forward, +Y left, +Z up`, keeps `units` inside its local surface packet, omits the UC-required surface `name`, and carries neutral material color as linear `base_color` RGBA values. Universal Creation's portable surface/GLB path expects metres in its Y-up / +Z-forward visual convention, a top-level surface `name`, and `material.color` as `#RRGGBB[AA]` text.

Silently feeding the local packet into UC would therefore be false integration. It would either fail schema validation or, after a superficial key repair, place the geometry in the wrong coordinate convention.

## Bounded adapter

`axm_animal_design.uc_bridge.adapt_form_evidence_for_uc()` performs one explicit source-owned conversion:

- validates exact animal evidence identity and refuses unknown coordinate systems or units;
- maps `[x_forward, y_left, z_up] -> [-y_left, z_up, x_forward]`;
- reverses every triangle winding because this source-to-target map changes handedness;
- transforms normals through the same axis map;
- preserves vertex colors and PBR scalar factors;
- converts the local linear `base_color` RGBA into UC's bounded hex material field;
- adds the UC-required surface name and removes the local-only `units` key from the wire packet;
- never changes the original organic-form evidence in place.

The adapter remains in `axm-animal-design`. Universal Creation is not widened to understand animal landmarks, anatomy, bend zones, or this repository's local evidence schema.

## Exact cross-repo proof

`.github/workflows/uc-surface-bridge.yml` checks out the exact animal candidate plus pinned Universal Creation commit:

`640bd7dc177b90e023aad879b4c00051df7f4ee3`

The workflow then:

1. runs focused bridge regressions;
2. rebuilds the exact quadruped form study;
3. converts its local surface packet into strict UC surface input;
4. publishes the result through UC's real `publish_glb()` path;
5. re-verifies the emitted GLB with UC's `verify_glb()` using the exact normalized specification digest;
6. requires source and verified GLB triangle counts to remain equal;
7. retains the canonicalized surface JSON, GLB bytes, and bridge receipt as one CI artifact.

This is a real pipeline proof, not a copy of UC's validation logic inside animal-design.

## Truth boundary

A green bridge proves only that the exact animal form evidence can cross this explicit coordinate/material/schema boundary into the pinned UC generator and survive UC's bounded GLB verification.

It does **not** prove visual quality, biological correctness, production topology, self-intersection freedom, rig/deformation quality, animation, target-engine import, collision, gameplay, performance, final materials, Art Director acceptance, or production readiness.

The conversion rule should not be moved into UC merely because this one animal candidate passes. A second materially different design repository should first demonstrate that the same boundary actually recurs.
