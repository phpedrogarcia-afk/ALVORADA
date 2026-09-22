# THREE-DIGEST CATALOG LOCK MODEL & IMMUTABLE PROPOSAL CONTRACT

**Status:** RECOVERY-G1-002 RECOVERY CANDIDATE SPECIFICATION<br>
**Contract Suite:** `ALVORADA_CATALOG_LOCK_MODEL_V1`<br>
**Classification:** ARCHITECTURAL INTEGRITY & GOVERNANCE CONTRACT

---

## 1. Core Architectural Principle: Three Mutually Distinct Cryptographic Identities

The three digests are not aliases, stages of the same record, or re-hashed variants. They represent three ontologically distinct objects across the lifecycle of Android SDK environment stabilization:

$$\mathbf{CATALOG\_DIGEST} \neq \mathbf{LOCK\_PROPOSAL\_DIGEST} \neq \mathbf{LOCK\_DIGEST}$$

```
+-----------------------------------------------------------------------------+
| 1. CATALOG_DIGEST                                                           |
| Contract: ALVORADA_CATALOG_DIGEST_PAYLOAD_V1                                |
| Scope: Pure stable channel SDK declarations (channel 0, 5 hard lock pkgs). |
| Semantics: What Google published in the remote repository.                  |
+-----------------------------------------------------------------------------+
                                     |
                                     v
+-----------------------------------------------------------------------------+
| 2. LOCK_PROPOSAL_DIGEST                                                     |
| Contract: ALVORADA_LOCK_PROPOSAL_V1                                         |
| Scope: Immutable snapshot with provenance, environment, freshness, GPU     |
| evidence (candidate modes), and proposal_state="PENDING_HUMAN_REVIEW".     |
| Semantics: What automated discovery observed. Zero human decisions.        |
+-----------------------------------------------------------------------------+
                                     |
                                     v  +-------------------------------------+
                                     |  | EXTERNAL HUMAN DECISION OBJECT      |
                                     |  | Contract:                           |
                                     |  | ALVORADA_HUMAN_LOCK_DECISION_V1     |
                                     |  | Selected GPU from candidate list.   |
                                     +->| HUMAN AUTHORITY IS EXTERNAL.        |
                                        +-------------------------------------+
                                                           |
                                                           v
+-----------------------------------------------------------------------------+
| 3. LOCK_DIGEST                                                              |
| Contract: ALVORADA_LOCK_PAYLOAD_V1                                          |
| Scope: Final lock payload binding proposal digest, catalog digest, hard     |
| locks, environment locks, and validated selected_gpu.                       |
| Semantics: Computed lock candidate awaiting external promotion.            |
+-----------------------------------------------------------------------------+
```

---

## 2. Specification of the Three Cryptographic Objects

### A. CATALOG_DIGEST (`ALVORADA_CATALOG_DIGEST_PAYLOAD_V1`)
- **Purpose:** Cryptographically pins the exact revisions declared by Google's repository channel 0 for the five mandatory packages:
  - `build-tools;36.0.0`
  - `emulator`
  - `platform-tools`
  - `platforms;android-36`
  - `system-images;android-36;default;x86_64`
- **Payload Scope:** Contains strictly `channel: 0`, `contract`, and `packages` (array ordered lexicographically by `package_path`). Each package entry contains solely `package_path` and `catalog_revision`.
- **Strict Exclusions:** Installed revisions, local runner paths, run IDs, timestamps, SDK roots, and host observations are strictly prohibited from this digest.
- **Fail-Closed Preconditions:** Produced only if the source projection is complete (`is_complete=True`), unambiguous (`has_ambiguity=False`), and contains all five packages with non-empty revisions.
- **Computation:**
  $$\text{CATALOG\_DIGEST} = \text{SHA-256}(\text{ALVORADA\_CANONICAL\_JSON\_V1}(\text{payload}))$$

### B. LOCK_PROPOSAL_DIGEST (`ALVORADA_LOCK_PROPOSAL_V1`)
- **Purpose:** Immutably freezes the complete discovery observation produced by automated CI probes.
- **Immutability Invariant:** The proposal is strictly immutable once created. It has **NO** mutable boolean flags (such as `lock_approved = YES/NO`). Its state is permanently `proposal_state = "PENDING_HUMAN_REVIEW"`.
- **Payload Contents:**
  - `catalog_digest`: Binds the exact stable catalog payload.
  - `hard_locks`: Revisions derived strictly from the catalog payload (cannot be independently supplied).
  - `environment`: Bound to `jdk_major: 17`, runner OS, and runner image labels (no local paths allowed).
  - `gpu_evidence`: Candidate GPU modes parsed strictly from `emulator -help-gpu`, `status`, `parser_status = "PASS_STRICT"`, `evidence_ready = True`. Selection of a GPU (`selected_gpu`, `gpu_mode`) is **STRICTLY FORBIDDEN** in the proposal.
  - `freshness`: `observed_at`, `fresh_until` (`observed_at + 7 days`), and `max_age_days: 7`.
  - `provenance`: Git commit SHA, GitHub Actions run ID, runner image labels.
- **Computation:**
  $$\text{LOCK\_PROPOSAL\_DIGEST} = \text{SHA-256}(\text{ALVORADA\_CANONICAL\_JSON\_V1}(\text{proposal}))$$

### C. LOCK_DIGEST (`ALVORADA_LOCK_PAYLOAD_V1`)
- **Purpose:** Represents the final lock payload binding all frozen packages, environment constraints, and the externally selected GPU mode.
- **Payload Contents:**
  - `contract`: `ALVORADA_LOCK_PAYLOAD_V1`
  - `proposal_digest`: Reference to immutable proposal digest.
  - `catalog_digest`: Reference to stable catalog digest.
  - `hard_locks`: The 5 hard-locked package revisions.
  - `environment_locks`: Pinned `jdk_major: 17` and `emulator_revision`.
  - `selected_gpu`: The GPU mode chosen by external human decision from `candidate_modes`.
- **Computation:**
  $$\text{LOCK\_DIGEST} = \text{SHA-256}(\text{ALVORADA\_CANONICAL\_JSON\_V1}(\text{lock\_payload}))$$

---

## 3. Human Authority Is External

A critical failure identified in the Autonomy v1 audit was the introduction of self-approval mechanisms (`approve-lock` CLI subcommand, mutable `lock_approved` flags, and automated gate jumping).

In RECOVERY-G1-002, authority is governed by strict boundaries:

1. **No Self-Approval:** The library provides no commands, flags (`--approve`), or interactive prompts to grant human authorization.
2. **Schema Validation Only:** The verifier function `verify_human_decision()` validates structural integrity only (`SCHEMA_VALID`, `REFERENCES_MATCH`, `SELECTED_GPU_VALID`, `FRESHNESS_VALID`).
3. **Mandatory Invariant:** The library explicitly and unconditionally reports:
   $$\mathbf{HUMAN\_AUTHORITY\_EXTERNALLY\_REQUIRED = True}$$
4. **Candidate Status:** Computation of a lock payload returns `LOCK_CANDIDATE_COMPUTED`, never `LOCK_APPROVED`. Promotion of a candidate to canonical status belongs to an external human gate.

---

## 4. Execution Sandbox Note: CatalogReadOnlyPolicy

`CatalogReadOnlyPolicy` and its `verify_script()` function provide static AST/regex policy filtering against dangerous commands in scripts. **It is NOT an OS-level execution sandbox.**

For future Catalog Discovery automation:
- Workflows and runners must avoid shell execution strings (`shell=True`).
- Command invocations must construct argument vectors (`argv`) directly.
- SDK manager calls must be strictly validated by `verify_sdkmanager_invocation(argv)` against the semantic read-only allowlist (`--sdk_root=<val>`, `--list`, `--verbose`, `--channel=0`).
- Emulator calls must be strictly validated by `verify_emulator_invocation(argv)`.
- Binaries must be resolved exclusively within `CANONICAL_SDK_ROOT`.
