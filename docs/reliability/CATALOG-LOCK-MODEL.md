# THREE-DIGEST CATALOG LOCK MODEL & IMMUTABLE PROPOSAL CONTRACT

**Status:** RECOVERY-G1-002-R2 RECOVERY CANDIDATE SPECIFICATION<br>
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
| evidence, ready_for_human_review flag, proposal_state="PENDING_HUMAN_REVIEW"|
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
- **Validated Boundary:** `validate_catalog_digest_payload()` is executed on every payload passed to `create_lock_proposal()`. No trust-by-call-chain: external payloads (Route B) have identical cryptographic guarantees as pipeline-generated payloads (Route A).
- **Computation:**
  $$\text{CATALOG\_DIGEST} = \text{SHA-256}(\text{ALVORADA\_CANONICAL\_JSON\_V1}(\text{payload}))$$
  $$\text{Static Fixture: } \mathtt{6c27ebaa82b34492b4f99c8ef52e63fc76b7ac7da70b02208f42045b884e0677}$$

### B. LOCK_PROPOSAL_DIGEST (`ALVORADA_LOCK_PROPOSAL_V1`)
- **Purpose:** Immutably freezes the complete discovery observation produced by automated CI probes.
- **Immutability Invariant:** The proposal is strictly immutable once created. It has **NO** mutable boolean flags (such as `lock_approved = YES/NO`). Its state is permanently `proposal_state = "PENDING_HUMAN_REVIEW"`.
- **Closed Semantic Builder Inputs:** `create_lock_proposal()` enforces closed schemas on all input dicts (`environment`, `provenance`, `freshness`, `gpu_evidence`). Principle: **NO SILENTLY UNBOUND SEMANTIC INPUT**. Callers cannot supply extra fields that would be silently ignored or omitted from the digest.
- **Payload Contents:**
  - `catalog_digest`: Binds the exact stable catalog payload.
  - `hard_locks`: Revisions derived strictly from the catalog payload (cannot be independently supplied).
  - `environment`: Bound to `jdk_major: 17`, runner OS, and runner image labels (no local paths allowed).
  - `gpu_evidence`: Strict fail-closed schema with no silent defaults (`status`, `emulator_revision`, `projection_sha256`, `parser_status`, `candidate_modes`, `evidence_ready`).
  - `freshness`: `observed_at`, `fresh_until` (`observed_at + 7 days`), and `max_age_days: 7`.
  - `provenance`: Git commit SHA, GitHub Actions run ID, runner image labels.
  - `ready_for_human_review`: Explicit boolean flag indicating structural readiness for human evaluation.
- **Provenance Structural Format Validation:**
  - `repository_commit_sha`: Strictly 40 lowercase hexadecimal characters (`^[0-9a-f]{40}$`). Rejects short SHAs, uppercase SHAs, non-hex strings, whitespace, URLs, and branch names.
  - `catalog_run_id`: Strictly positive decimal integer string (`^[1-9][0-9]*$`). Rejects zero, negative numbers, decimals, and non-digit characters.
- **Tripartite Revision Binding:**
  $$\text{gpu\_evidence.emulator\_revision} == \text{environment.emulator\_revision} == \text{hard\_locks[\"emulator\"].revision}$$
- **Runner Coherence:**
  $$\text{environment.runner\_image\_label} == \text{provenance.runner\_image\_label}$$
  $$\text{environment.runner\_image\_version} == \text{provenance.runner\_image\_version}$$
- **Computation:**
  $$\text{LOCK\_PROPOSAL\_DIGEST} = \text{SHA-256}(\text{ALVORADA\_CANONICAL\_JSON\_V1}(\text{proposal}))$$
  $$\text{Static Fixture: } \mathtt{c4a2a86584ebe84e51073a521cebaf9f2c79ed2eafb387b065c19c786915cc1b}$$

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
  $$\text{Static Fixture: } \mathtt{c81ec5da2054ebdb626aad308f4c03c162144809b84338834649ce2b5a45ffe9}$$

---

## 3. Trust Boundaries and Governance Contracts

### A. Dual-Window Freshness & Temporal Causality Enforcement
Freshness verification does not rely on implicit system clocks (`datetime.now()` is strictly prohibited). An evaluation requires an explicit, mandatory `evaluation_time_utc` parameter.

To be valid, temporal causality and two distinct time windows must hold simultaneously:
1. **Decision Time Validity (`REVIEW_TIME_VALID`):**
   $$\text{observed\_at} \le \text{reviewed\_at} \le \text{fresh\_until}$$
2. **Evaluation Time Validity (`EVALUATION_TIME_VALID`):**
   $$\text{observed\_at} \le \text{evaluation\_time\_utc} \le \text{fresh\_until}$$
3. **Temporal Causality (`DECISION_PRECEDES_OR_EQUALS_EVALUATION`):**
   $$\text{reviewed\_at} \le \text{evaluation\_time\_utc}$$

$$\mathbf{FRESHNESS\_VALID} = \mathbf{REVIEW\_TIME\_VALID} \land \mathbf{EVALUATION\_TIME\_VALID} \land \mathbf{DECISION\_PRECEDES\_OR\_EQUALS\_EVALUATION}$$

This contract prevents two critical attacks:
- **Backdated Revival:** An expired proposal cannot be authorized today using a historical decision timestamp.
- **Future Decision:** A decision recorded with a timestamp in the future relative to the evaluation time is rejected immediately.

### B. `ready_for_human_review` != Approval
`ready_for_human_review` is an informational readiness indicator, not an approval.
- It is `True` only when all automated probe invariants pass: valid catalog, valid environment, `evidence_ready=True`, `status="PASS_STRICT"`, `parser_status="PASS_STRICT"`, `candidate_modes >= 1`, lowercase 64-hex projection hash, and revision bindings hold.
- Diagnostic proposals (`evidence_ready=False`) carry `ready_for_human_review=False`. They can be hashed and audited, but cannot be approved (`APPROVE` decisions fail closed).
- `proposal_state` remains permanently `"PENDING_HUMAN_REVIEW"`.

### C. `review_context` != Authentication
`HumanDecision` has a closed top-level schema:
```json
{
  "contract": "ALVORADA_HUMAN_LOCK_DECISION_V1",
  "proposal_digest": "...",
  "catalog_digest": "...",
  "decision": "APPROVE",
  "selected_gpu": "swiftshader_indirect",
  "reviewed_at": "2026-09-21T15:00:00Z",
  "review_context": {
    "authority_basis": "EXTERNAL_FOUNDER_GATE"
  }
}
```
- `review_context` is mandatory and must be a non-empty dictionary providing audit trace context.
- `review_context` does **NOT** authenticate the human. The library does not infer identity from user claims.
- The verifier unconditionally returns:
  $$\mathbf{HUMAN\_AUTHORITY\_EXTERNALLY\_REQUIRED = True}$$
- `review_context` is decoupled from `LOCK_DIGEST`: mutating `review_context` does not change `LOCK_DIGEST` because the decision object is not embedded in the lock payload.

---

## 4. Execution Sandbox Note: CatalogReadOnlyPolicy

`CatalogReadOnlyPolicy` and its `verify_script()` function provide static AST/regex policy filtering against dangerous commands in scripts. **It is NOT an OS-level execution sandbox.**

For future Catalog Discovery automation:
- Workflows and runners must avoid shell execution strings (`shell=True`).
- Command invocations must construct argument vectors (`argv`) directly.
- SDK manager calls must be strictly validated by `verify_sdkmanager_invocation(argv)` against the semantic read-only allowlist (`--sdk_root=<val>`, `--list`, `--verbose`, `--channel=0`).
- Emulator calls must be strictly validated by `verify_emulator_invocation(argv)`.
- Binaries must be resolved exclusively within `CANONICAL_SDK_ROOT`.
