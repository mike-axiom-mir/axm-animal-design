# Connected Limb-Chain Topology Study 001

This lane tests one bounded geometry pattern against the first real organic source body: replace three separately capped forelimb segment primitives with one closed connected chain that shares rings at the authored elbow and wrist landmarks.

## Why this candidate exists

`quadruped-neutral-001` is intentionally a disconnected mass/form study. Its left forelimb currently uses three independent closed primitives: `front_upper_L`, `front_lower_L`, and `front_paw_L`. That is valid for a form-study baseline, but it is not evidence for a single connected deformable skin.

The Geometry / Topology lane therefore adds a **derived candidate only**. It does not rewrite the canonical Organic Form source or silently change the Rigging / Deformation lane.

## Reusable pattern

`axm_animal_design.topology_study.build_connected_chain()` builds one closed tube through an authored path with one shared ring per path landmark and bounded endpoint caps. For the first proof it consumes the exact existing path:

`shoulder_L -> elbow_L -> wrist_L -> front_paw_L`

with radii `[0.115, 0.09, 0.07, 0.095]` metres and 10 ring segments.

The pattern is deliberately small. It does not prescribe animal anatomy, a skeleton, skin weights, production retopology, or a studio-wide organic mesh style.

## Donor topology evidence

The receiving repository re-tests the candidate with the exact Universal Creation topology inspector from:

- repository: `mike-axiom-mir/axm-universal-creation`
- commit: `b434a349cf159b392148b4dc9d68146573531a60`
- module: `src/axm_uc/mesh_topology.py`
- license: Apache-2.0

CI checks out that exact donor revision rather than copying the shared inspector into animal-design. Donor PASS does not transfer automatically: the exact animal candidate is measured again in this repository.

## Before / after structural claim

The evidence builder compares only the three existing left-front-limb primitives against the new derived connected-chain candidate. The intended gate is:

- original limb reports three edge-connected triangle components;
- candidate reports one edge-connected triangle component;
- candidate reports zero boundary edges;
- candidate reports zero non-manifold edges;
- candidate reports zero shared-edge orientation conflicts;
- candidate reports zero collapsed triangles at the declared weld tolerance.

CI is authoritative for the exact observed numbers. This document does not predeclare PASS.

## Truth boundary

Even a green topology receipt would **not** establish:

- better silhouette or anatomical form;
- deformation quality, volume preservation, or self-intersection freedom;
- rigging or animation acceptance;
- UV, material, normal/tangent, or shading quality;
- collision or gameplay suitability;
- engine import/runtime performance;
- that the canonical quadruped should immediately switch to this topology;
- animal-design or topology mastery.

Visual Observer / Art Direction must compare the candidate against the retained baseline before any source replacement. Rigging must independently test it if adopted.
