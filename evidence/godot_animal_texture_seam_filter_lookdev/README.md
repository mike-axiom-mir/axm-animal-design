# Animal UV seam / texture-filter Materials lookdev

This is a bounded Materials receiving observer layered on the existing Animal PR #24 direction-frame proof. It keeps the exact reconstructed owner frame, positions, topology, UVs, lights and cameras fixed and changes only the diagnostic normal texture/filter condition.

Compared modes:

1. `flat_control` — neutral tangent-space normal texture.
2. `periodic_mipped` — self-generated 256x256 periodic tangent-space normal texture with generated mipmaps and repeat sampling.
3. `periodic_no_mip` — the same base texels sampled without mip filtering, retained only to characterize filter sensitivity.
4. `edge_mutated_mipped_negative` — identical interior texels, but the first/last eight U-edge columns are deliberately pushed in opposite tangent directions before mip generation so a seam discontinuity exists.
5. `seam_locator` — unshaded projected UV-edge locator used only to localize the deliberate negative in screen space.

The candidate's base-level first/last columns are generated from the same periodic endpoint and must quantize identically. The negative exists to prove the real Godot receiver can see a localized seam-edge defect under the same reconstructed frame.

This is not a production Animal normal map, final UV packing or texel-density policy, proof that all mip levels are wrap-perfect, Technical-Art or Runtime adoption, final Art/QA acceptance, CANON, or production readiness.
