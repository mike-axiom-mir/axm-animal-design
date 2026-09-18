# Rigging guard for the Animal Runtime animation-key budget

This bounded successor stays inside the existing Animal Rigging PR #25. It does not create a second Rigging lane and does not alter source geometry, joint hierarchy, weighting, authored Animation, Runtime representation, Technical Art, Materials, or target-host behavior.

## Fresh handoff

Runtime PR #30 reduces the exact normalized-u16 Animal rotation channel from 41 serialized keys to 19 while preserving the unchanged 1.0 s glTF `LINEAR` channel. Runtime reports a maximum 321-sample `qerr_deg` value of about `0.0547204398 deg` under its exact `0.075 deg` threshold and explicitly does not claim Rigging acceptance.

Exact Runtime owner:

- head `13ba20d198d2b7c5e428167745d59927b3084004`;
- artifact `10525970648`;
- archive SHA-256 `ad071f58796b606d707168af9619d988a497ba1a745dda8ac62b42e7f814b996`;
- 41-key normalized-u16 control GLB SHA-256 `81c5422f8cf13ca65a253d3b05ebcf88fc0b20601dfb466b3c92f0d5e28dafcb`;
- 19-key candidate GLB SHA-256 `a8a32b58ad3bad44176a676b00f5cf1c20d1a2ec6da275b683d8f73a69088d6b`.

Immediate Rigging predecessor: `d0c27db357b015a1ff270de294e39c1a44e3931d`.

## Bounded Rigging question

Does the exact 19-key Runtime representation remain inside the existing Animal elbow command envelope and preserve the current owner deformation at dense representative subframes, without promoting a Runtime storage optimization into Animation or target-host acceptance?

## Important metric-semantic finding

The first proof attempt correctly failed instead of hiding a mismatch: its position bound treated Runtime's `0.075 deg` threshold as a physical owner-command angle. Runtime PR #30's exact helper computes

`2 * asin(min(||q1-q2||, ||q1+q2||) / 2)`.

For unit quaternions, that is the quaternion half-angle distance; the corresponding shortest physical rotation angle is twice that value. Rigging therefore reproduces Runtime's metric exactly but **does not silently reinterpret it as a physical-degree owner-angle budget**.

The repaired guard measures both independently:

- Runtime's exact quaternion metric, to preserve source truth;
- the physical same-axis rotation / owner-command angle residual, to protect the Rigging boundary.

If the exact candidate remains within Runtime's metric threshold but exceeds `0.075 deg` of owner-command angle, the bounded result is a **HOLD**, while command-envelope inclusion and sampled deformation witnesses can still PASS. Runtime may choose to revise its metric semantics or candidate; Rigging does not do that silently.

## Proof shape

The guard preserves the exact historical Rigging plan/profile digests and reconstructs the current right-side owner surface. It then:

1. decodes the exact control/candidate glTF rotation channels;
2. proves the retained quaternions share one fixed rotation axis and every reduced segment stays on the shortest same-axis arc;
3. uses that property only to prove **continuous command-envelope inclusion** inside the existing Rigging `[-60,+60] deg` review envelope;
4. evaluates control and candidate owner deformation at all `321` samples / `320 Hz` across the unchanged 1.0 s channel;
5. requires every sampled owner pose to retain the existing Rigging PASS;
6. independently records Runtime's quaternion metric, physical rotation residual, and same-axis owner-command angle residual;
7. derives a conservative position bound from the actual measured owner-command residual and the farthest source point from the exact joint pivot;
8. re-derives the owner normal/tangent frame on both sampled poses and records normal/tangent deltas plus handedness changes;
9. retains representative witnesses at `0.00 / 0.25 / 0.475 / 0.50 / 0.75 / 1.00 s` plus the actual worst owner-command sample if different;
10. rejects a verifier-only `+1 deg` retained-key mutation and rejects widening the existing Rigging review envelope.

The continuous statement remains deliberately narrow: the reduced **command channel** remains within the existing review envelope. Deformation/collision safety is sampled evidence only; this lane does not silently turn the older discrete Rigging envelope into a mathematical continuous-collision theorem.

## Authority boundary

A green workflow does not adopt the 19-key Runtime representation, retime or rewrite Animation, accept target-host playback, grant Runtime/controller/device performance, accept Materials/Art/QA appearance, or authorize CANON/production use. Runtime retains the optimization decision and metric semantics; Animation retains timing/interpolation/playback authority; Technical Art retains transport/target-host authority; Art/QA retain perceptual acceptance.

`axm-create-me` remains coordination-only. The four AXM roots remain the gate: Truth, Agency / non-domination, Continuity, Wisdom before speed.
