# Post-skin owner-frame reconstruction constraint

Rigging follow-up for PR #25.

This bounded witness preserves the exact transported source, Geometry topology/UV identity, Rigging hierarchy and weights, authored Animation keys, and retained Technical-Art GLB bytes. It does **not** replace the retained finding that statically transported `NORMAL`/`TANGENT` directions diverge from the Geometry/Rigging owner frame under deformation.

The follow-up asks only whether the already-proven transported **skinned POSITION** field is sufficient to recover that owner direction frame. For each of the 41 exact authored keys, Rigging collapses the fixed 84-render-vertex UV-split domain back to the fixed 42-source-vertex domain, converts target-space positions back through the exact transport coordinate mapping, and reruns the unchanged Geometry/Rigging posed normal+tangent derivation. A coherent 1 mm posed-shape mutation is retained as a fail-closed sensitivity control.

A green result therefore establishes a structural reconstruction option at this exact identity; it does not mean Technical Art adopted that option, does not change Animation timing/interpolation, does not prove target-engine/runtime implementation, and does not grant shaded visual, gameplay, CANON, or production acceptance.
