# Connected Limb-Chain Topology Study 001

This lane tests one bounded geometry pattern against the first real organic source body: replace three separately capped forelimb segment primitives with one closed connected chain that shares rings at the authored elbow and wrist landmarks.

## Why this candidate exists

`quadruped-neutral-001` is intentionally a disconnected mass/form study. Its left forelimb currently uses three independent closed primitives: `front_upper_L`, `front_lower_L`, and `front_paw_L`. That is valid for a form-study baseline, but it is not evidence for a single connected deformable skin.

The Geometry / Topology lane therefore adds a **derived candidate only**. It does not rewrite the canonical Organic Form source or silently change the Rigging / Deformation lane.

## Reusable pattern

`axm_animal_design.topology_study.build_connected_chain()` builds one closed tube through an authored path with one shared ring per path landmark and bounded endpoint caps. For the first proof it consumes the exact existing path:

`shoulder_L -> elbow_L -> wrist_L -> front_paw_L`

with 10 ring segments.

### Source-owned radius reconciliation

The candidate no longer hand-types its shared-ring radius list. `derive_shared_ring_radii()` resolves the ordered source segment chain directly from the Organic Form regions and applies one explicit local policy:

- preserve the first source `radius_a` exactly;
- preserve the last source `radius_b` exactly;
- when two source spans meet at one landmark, use the arithmetic mean of the incoming `radius_b` and outgoing `radius_a` for the one connected shared ring;
- retain both authored values and their gap in the evidence packet.

For this exact source that derives:

- shoulder: `0.115 m` from `front_upper_L.radius_a`;
- elbow: `(0.09 + 0.09) / 2 = 0.09 m`;
- wrist: `(0.065 + 0.075) / 2 = 0.07 m`;
- paw endpoint: `0.095 m` from `front_paw_L.radius_b`.

The `0.07 m` wrist ring is therefore an explicit reconciliation of a real `0.01 m` authored endpoint-radius mismatch, not a silent replacement value. The policy is candidate-local and is **not** claimed to be anatomical truth or a studio-wide retopology rule.

The pattern is deliberately small. It does not prescribe animal anatomy, a skeleton, skin weights, production retopology, or a studio-wide organic mesh style.

## Donor topology evidence

The receiving repository re-tests the candidate with the exact Universal Creation topology inspector from:

- repository: `mike-axiom-mir/axm-universal-creation`
- commit: `b434a349cf159b392148b4dc9d68146573531a60`
- module: `src/axm_uc/mesh_topology.py`
- license: Apache-2.0

CI checks out that exact donor revision rather than copying the shared inspector into animal-design. Donor PASS does not transfer automatically: the exact animal candidate is measured again in this repository.

That donor deliberately leaves vertex-neighborhood manifoldness and self-intersection unproven. This lane therefore adds one **receiving-domain-local** supplement, `inspect_vertex_fan_connectivity()`, for the exact indexed candidate. It checks that every indexed vertex belongs to exactly one edge-connected fan of incident triangles and that no indexed vertex is isolated. A negative control made from two closed tetrahedra sharing only one vertex must report two disconnected fans at that shared vertex, proving the gate can detect the bow-tie topology that ordinary per-edge closedness can miss.

The supplement is not promoted into Universal Creation from one receiving case. It does not weld positional seams and it does not test geometric self-intersection.

## Before / after structural claim

The evidence builder compares only the three existing left-front-limb primitives against the new derived connected-chain candidate. The intended gate is:

- original limb reports three edge-connected triangle components;
- candidate reports one edge-connected triangle component;
- candidate reports zero boundary edges;
- candidate reports zero non-manifold edges;
- candidate reports zero shared-edge orientation conflicts;
- candidate reports zero collapsed triangles at the declared weld tolerance;
- candidate reports zero isolated indexed vertices;
- every candidate indexed vertex reports exactly one incident-triangle fan;
- candidate radii are reproduced from the exact source-region chain rather than a detached hand-authored numeric list.

CI is authoritative for the exact observed numbers. This document does not predeclare PASS.

## Truth boundary

Even a green topology receipt would **not** establish:

- better silhouette or anatomical form;
- that the arithmetic-mean junction policy is the visually or anatomically best radius transition;
- seam-welded vertex manifoldness for arbitrary split-vertex meshes;
- freedom from geometric self-intersection;
- deformation quality or volume preservation;
- rigging or animation acceptance;
- UV, material, normal/tangent, or shading quality;
- collision or gameplay suitability;
- engine import/runtime performance;
- that the canonical quadruped should immediately switch to this topology;
- animal-design or topology mastery.

Visual Observer / Art Direction must compare the candidate against the retained baseline before any source replacement. Rigging must independently test this exact topology if adopted.
