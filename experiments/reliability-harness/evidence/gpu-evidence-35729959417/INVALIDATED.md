# EVIDENCE INVALIDATION RECORD: Run 35729959417

**Status**: INVALIDATED / SUPERSEDED
**Original Run ID**: 35729959417
**RUN_HEAD_SHA**: 68e094a3d1966a6f466e332630890fd166003c01
**HISTORICAL_PROPOSAL_COMMIT**: a75623749b998b2affd2834cc5ce31c9fda3e4b2
**INVALIDATION_RECORD_COMMIT**: 8c26c4ce3a42841b543e709207460ab190b78321
**SUPERSEDING_RUN_ID**: 35734871241
**SUPERSEDING_RUN_HEAD_SHA**: e7f1601e04fc151a791d6cdf033cbdb679bd4060

---

### Clarification on Provenance Lineage:
- `RUN_HEAD_SHA` (`68e094a3d1966a6f466e332630890fd166003c01`): The exact repository commit checked out and executed by GitHub Actions runner during run `35729959417`.
- `HISTORICAL_PROPOSAL_COMMIT` (`a75623749b998b2affd2834cc5ce31c9fda3e4b2`): The subsequent commit that assembled `ALVORADA_LOCK_PROPOSAL_V1` and checked the evidence folder into git tracking.
- `INVALIDATION_RECORD_COMMIT` (`8c26c4ce3a42841b543e709207460ab190b78321`): The commit where this invalidation notice was introduced.

---

### Audit Findings Leading to Invalidation:

1. **F-001 (Trigger Policy Non-Compliance)**:
   The workflow `e1-lab-gpu-evidence-recovery.yml` at execution commit `68e094a` contained automatic `push` triggers on `fio/g1-autonomy-recovery`, violating the mandatory contract requirement that experimental evidence generation be `workflow_dispatch` ONLY.

2. **F-002 (Commit Admission Gap)**:
   The workflow lacked strict triple-guard commit admission verification against `expected_head_sha`.

3. **F-004 (Cryptographic Projection Misbinding)**:
   `gpu-evidence.json` bound `projection_sha256: 64f3ddd82cc72dacc9146e492345d1f7db8196cff053d7343521021140a7404e` (the catalog projection SHA-256), rather than the dedicated canonical GPU projection contract `ALVORADA_GPU_PROJECTION_V1` (`dc4b6c15243217d1c04c6347b5a671910346d4753f603a4869b3723b09677b98`).

4. **F-006 & F-007 (Causal Freshness & Runner Mutation)**:
   Lacked dual-provenance cross-run causal freshness timestamping and contained unconditional `apt-get install -y libpulse0 || true` without causal probe and verification.

---

### Replacement:
All findings have been resolved in forensic repair. Run 35734871241 satisfies all frozen G1 contracts and binds to canonical proposal `5517290ec9b90cdcbc13ad34a1228a1ff422f2a5c2326d622e9f2ae249b411b4`.
