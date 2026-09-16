# Runtime Animal explicit-normal indexed payload budget 001

Status: EXPERIMENTAL / RUNTIME EVIDENCE ONLY

Exact parent: Geometry PR #16 head `79e1667f6cc91e2ec8e41f01df18b6933c9c876d`.

## Question

Can the exact right-side Animal logical-quad explicit-normal candidate preserve the same positions, triangle order, normal values, neutral probe material and fixed cameras while keeping the source-owned indexed representation instead of expanding every triangle corner into a separate runtime vertex?

## Measure-before contract

The current target-host review style expands `80` triangles into `240` stored vertices when it submits one explicit normal for every triangle corner. The source-owned surface is already `42` positions with `240` indices and Geometry PR #16 supplies exactly `42` normals.

The Runtime candidate changes only storage representation:

- control: `240` stored vertices / `0` stored indices;
- candidate: `42` stored vertices / `240` stored indices;
- triangle count: `80` in both;
- surface/material count: `1` in both;
- explicit normal field: identical in both;
- tangent policy remains `NOT_DEFINED_NO_UV_BASIS`.

Under the deliberately bounded logical model of position `Vector3` + normal `Vector3` per stored vertex plus 32-bit indices:

- control: `240 * 24 = 5,760 B`;
- candidate: `42 * 24 + 240 * 4 = 1,968 B`;
- expected modeled delta: `-3,792 B`, or `-65.833333%`.

This logical byte model is not a VRAM, heap, allocator, import-file or backend-packing claim. The Godot proof separately records RenderingServer buffer/texture counters.

## Acceptance boundary

A PASS requires the exact Geometry normal-field parent identity, exact source counts, the expected stored-vertex/index reduction, unchanged draw/object/primitive/texture counters, no observed buffer-memory increase, byte-identical retained PNGs in the established three-quarter and grazing cameras, and a fail-closed stored-vertex mutation control.

The candidate does not decide whether the Geometry normal field is aesthetically preferred. Art Direction / Materials / Visual QA retain that authority. It also does not establish tangents/UVs, deformed-normal behavior, animation, arbitrary-mesh indexing safety, target-device CPU/GPU/FPS behavior, UC extraction, CANON or production readiness.
