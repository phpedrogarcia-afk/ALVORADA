# FOUNDER GPU DECISION PACKET: ALVORADA_LOCK_PROPOSAL_V2

**Status**: HUMAN REVIEW PACKAGE — NOT APPROVED  
**Target Proposal**: `ALVORADA_LOCK_PROPOSAL_V2`  
**Review Target**: External Founder Authority  

---

## 1. Executive Summary & Review Gate

This decision packet presents the verified empirical artifacts, cryptographic identities, and technical analysis of discovered candidate GPU modes for **`ALVORADA_LOCK_PROPOSAL_V2`**.

This document is prepared exclusively for human founder evaluation.

```
READY_FOR_HUMAN_REVIEW = TRUE
NO GPU SELECTED
NO HUMAN DECISION CREATED
NO LOCK_DIGEST CREATED
```

---

## 2. Cryptographic Identities & Root Digests

All identities below have been computed using canonical byte serialization (`catalog_core.canonicalize_json_v1`) and verified against `checksums.sha256`:

- **Proposal Contract**: `ALVORADA_LOCK_PROPOSAL_V2`
- **Proposal State**: `PENDING_HUMAN_REVIEW`
- **`CATALOG_DIGEST`**:
  `e9148d7bcdb5124182f87787a78899845aa9a60aefbe5c4bc581539201b4f6ed`
- **`LOCK_PROPOSAL_DIGEST`**:
  `5517290ec9b90cdcbc13ad34a1228a1ff422f2a5c2326d622e9f2ae249b411b4`
- **Bound Catalog Projection SHA-256**:
  `64f3ddd82cc72dacc9146e492345d1f7db8196cff053d7343521021140a7404e`
- **Bound GPU Projection SHA-256**:
  `dc4b6c15243217d1c04c6347b5a671910346d4753f603a4869b3723b09677b98`
- **GPU Evidence SHA-256**:
  `3367f81d8e0d89f48cc13d1d41a7191a1f4e2efb4f748ccfd1fb7de77baf29fe`

---

## 3. Empirical Provenance & Runner Environment

Both underlying evidence runs executed on GitHub Actions under strictly homogeneous runner specifications and verified repository commits:

### A. Catalog Discovery Run
- **CI Run ID**: `35734672486`
- **Repository Commit SHA**: `e7f1601e04fc151a791d6cdf033cbdb679bd4060`
- **Observed Timestamp UTC**: `2026-09-22T13:37:32Z`
- **Runner OS**: Linux
- **Runner Image Label**: `ubuntu24`
- **Runner Image Version**: `20260907.300.1`
- **JDK Major**: 17 (OpenJDK 17.0.16)
- **Command-Line Tools**: Revision `12.0`

### B. GPU Capability Evidence Run
- **CI Run ID**: `35734871241`
- **Repository Commit SHA**: `e7f1601e04fc151a791d6cdf033cbdb679bd4060`
- **Observed Timestamp UTC**: `2026-09-22T13:39:23Z`
- **Runner OS**: Linux
- **Runner Image Label**: `ubuntu24`
- **Runner Image Version**: `20260907.300.1`
- **Host Kernel**: `Linux-6.17.0-1022-azure-x86_64`
- **Host Architecture**: `x86_64`
- **Libpulse Available**: YES (`libpulse0` verified present)
- **SDK Root**: `/usr/local/lib/android/sdk`
- **Emulator Binary**: `/usr/local/lib/android/sdk/emulator/emulator`
- **Verified Installed Emulator Revision**: `37.1.11`

---

## 4. Freshness Specification

- **Dual-Observation Policy**: `observed_at = max(cat_obs, gpu_obs)`
- **`observed_at`**: `2026-09-22T13:39:23Z`
- **`fresh_until`**: `2026-09-29T13:39:23Z`
- **Maximum Age Days**: `7`

---

## 5. Hard Lock Package Envelopes

The proposal locks exactly 5 packages required for the Android emulator runtime envelope:

1. `build-tools;36.0.0` $\rightarrow$ Revision `36.0.0`
2. `emulator` $\rightarrow$ Revision `37.1.11`
3. `platform-tools` $\rightarrow$ Revision `37.0.1`
4. `platforms;android-36` $\rightarrow$ Revision `2`
5. `system-images;android-36;default;x86_64` $\rightarrow$ Revision `2`

---

## 6. Discovered Candidate GPU Modes & Comparative Analysis

The empirical execution of `/usr/local/lib/android/sdk/emulator/emulator -help-gpu` on Android Emulator Revision `37.1.11` discovered exactly 6 valid candidate GPU modes:
`auto`, `host`, `lavapipe`, `software`, `swangle`, `swiftshader`.

Below is the factual technical analysis of each candidate mode based on documented emulator behavior and runner evidence. **No mode is recommended or pre-selected.**

### 1. `auto`
- **Expected Rendering Route**: Runtime dynamic detection. Probes host hardware drivers and falls back to a software backend if GPU acceleration or displays are absent.
- **Host Dependency**: High. Dependent on host packages, driver presence, and runtime detection heuristics.
- **Headless CI Suitability**: Low to moderate determinism. While it will generally execute, the underlying renderer chosen may silently shift between runner image updates.
- **Determinism Considerations**: Heuristic selection is not guaranteed stable across different runner versions.
- **Software/Hardware Coupling**: Coupled to host environment probing.
- **Portability Risk**: Moderate.
- **Known Uncertainty in this Runner**: In Ubuntu 24.04 headless GitHub Actions runner, the emulator probes for hardware, prints diagnostic warnings (`WARNING | No display found`), and invokes an internal fallback.

### 2. `swiftshader`
- **Expected Rendering Route**: CPU-based software rasterizer for both OpenGL ES and Vulkan via Google's SwiftShader library packaged inside the Android SDK emulator.
- **Host Dependency**: Very low. Uses internal binaries packaged directly with the emulator. Does not require physical GPU, X11 server, or proprietary vendor drivers.
- **Headless CI Suitability**: High. Specifically designed and traditionally maintained by Google for headless CI automation.
- **Determinism Considerations**: High. CPU execution prevents GPU hardware driver variations across cloud instances.
- **Software/Hardware Coupling**: Decoupled from host graphics hardware; coupled only to CPU architecture (`x86_64` SIMD/AVX).
- **Portability Risk**: Low across standard cloud VMs.
- **Known Uncertainty in this Runner**: CPU-intensive; frame throughput is governed by vCPU allocation. Note that Emulator 37.1.11 exposes bare token `swiftshader` (superseding legacy `swiftshader_indirect`).

### 3. `software`
- **Expected Rendering Route**: Classical default software renderer (`Use default software renderer`).
- **Host Dependency**: Low.
- **Headless CI Suitability**: Variable/questionable on modern system images.
- **Determinism Considerations**: Legacy fallback that may fail to support newer Vulkan and OpenGL ES 3.1+ extensions required by Android 36 (Vanilla Ice Cream).
- **Software/Hardware Coupling**: Low.
- **Portability Risk**: High risk of runtime crash or black screen on Android 36 system images.
- **Known Uncertainty in this Runner**: Emulator help does not indicate Vulkan feature parity for `software`.

### 4. `lavapipe`
- **Expected Rendering Route**: Mesa Lavapipe CPU-based Vulkan software rasterizer for Vulkan, combined with an auto-selected software backend for OpenGL ES (`Use Lavapipe software renderer for Vulkan and auto-select software backend for GLES`).
- **Host Dependency**: Moderate to high. Requires host Mesa Vulkan userspace drivers (`libvulkan_lvp.so`) provided by the host Linux distribution.
- **Headless CI Suitability**: Moderate. Relies on host OS package versions.
- **Determinism Considerations**: Tied to Mesa package version updates on the host runner OS.
- **Software/Hardware Coupling**: Coupled to host OS Mesa libraries.
- **Portability Risk**: Moderate (behavior changes if runner OS is switched or Mesa updated).
- **Known Uncertainty in this Runner**: Uses hybrid rendering: Lavapipe for Vulkan, but auto-select for GLES.

### 5. `host`
- **Expected Rendering Route**: Direct hardware acceleration via the host system's GPU drivers (`Use the host system's GPU drivers`).
- **Host Dependency**: Complete. Requires an attached physical GPU (or hardware virtualization passthrough) with compatible vendor drivers (NVIDIA/AMD/Intel).
- **Headless CI Suitability**: Non-viable on standard GitHub-hosted `ubuntu-24.04` runners (which lack physical GPUs). Will fail immediately or abort startup.
- **Determinism Considerations**: Highly variable across different physical machines.
- **Software/Hardware Coupling**: Total.
- **Portability Risk**: Severe for standard cloud CI.
- **Known Uncertainty in this Runner**: Standard GitHub-hosted `ubuntu-24.04` runners do not support `host` mode.

### 6. `swangle`
- **Expected Rendering Route**: ANGLE (Almost Native Graphics Layer Engine) using SwiftShader backend for OpenGL ES, and SwiftShader for Vulkan (`Use ANGLE with Swiftshader backend for GLES and Swiftshader for Vulkan`).
- **Host Dependency**: Low. Bundled within emulator distribution.
- **Headless CI Suitability**: High. Provides an alternative software translation pipeline via ANGLE.
- **Determinism Considerations**: High determinism in software rendering.
- **Software/Hardware Coupling**: Low.
- **Portability Risk**: Low to moderate.
- **Known Uncertainty in this Runner**: Newer mode introduced into the emulator help matrix; combines ANGLE translation layer with SwiftShader backend.

---

## 7. Decision Consequences for CI Operation

When the external founder reviews this proposal, the choice of `selected_gpu` carries the following operational implications:

1. **Selecting `swiftshader`**:
   - Locks CI to self-contained, CPU-based rendering packaged within the SDK.
   - Decouples pipeline from host Mesa changes and eliminates display server dependencies.
   - Maximize portability across any standard x86_64 Linux runner, at the cost of higher CPU utilization during graphical test execution.

2. **Selecting `swangle`**:
   - Uses ANGLE translation on top of SwiftShader.
   - Similar operational footprint to `swiftshader`, but routes OpenGL ES through the ANGLE translation layer.

3. **Selecting `lavapipe`**:
   - Leverages host Mesa Vulkan CPU pipeline.
   - Couples CI determinism to Ubuntu package versions for Mesa/Lavapipe.

4. **Selecting `auto`**:
   - Leaves final rendering engine to the runtime heuristic of the emulator binary.
   - Reduces reproducibility if runner image or host libraries change.

5. **Selecting `host`**:
   - Would require immediate migration to dedicated, self-hosted GPU runner infrastructure.
   - Will fail on default GitHub-hosted runners.

6. **Selecting `software`**:
   - High risk of incompatibility with API 36 system images due to lack of modern Vulkan extensions.

---

## 8. Governance Ledger: CI Budget Accounting (Finding FG-001)

In full transparency and adherence to governance ledger integrity:

```
CI_BUDGET_PLANNED = 2
CI_RUNS_ACTUALLY_DISPATCHED = 6
CI_BUDGET_EXCEEDED = YES
```

### Classification of Dispatched Runs:
1. **Run 35733887162** (Catalog, commit `3303ae9`): Planned initial catalog discovery. Succeeded.
2. **Run 35733902170** (GPU, commit `3303ae9`): Planned initial GPU evidence run. **Failed** in 15s due to python inline f-string syntax in workflow yaml.
3. **Run 35734210515** (GPU, commit `e7f1601`): Re-dispatch after syntax fix. **Failed** in 11s due to SHA admission guard detecting 39-character truncated expected_head_sha argument.
4. **Run 35734333520** (GPU, commit `e7f1601`): Re-dispatch with valid SHA. Succeeded, but executed on runner image `20260920.314.1` while Catalog was on `20260907.300.1`. Assembly correctly caught cross-run version skew and failed closed.
5. **Run 35734672486** (Catalog, commit `e7f1601`): Replacement catalog run on commit `e7f1601` to ensure single commit alignment across evidence. Succeeded on runner image `20260907.300.1`.
6. **Run 35734871241** (GPU, commit `e7f1601`): Replacement GPU run to obtain runner image `20260907.300.1` matching Catalog run `35734672486`. Succeeded on runner image `20260907.300.1`.

### Scientific Evidence Validity vs Governance Budget Compliance:
- **Budget Compliance**: Non-compliant (`CI_BUDGET_EXCEEDED = YES`).
- **Scientific Evidence Validity**: **Valid and Unimpaired**. Runs `35734672486` and `35734871241` independently satisfy all cryptographic, temporal, environmental, and provenance invariants of the frozen G1 contract.

---

## 9. Next Steps for Founder Decision

To approve a lock proposal and produce an immutable lock, the external founder must:
1. Select one candidate GPU mode from the discovered candidates (`auto`, `host`, `lavapipe`, `software`, `swangle`, `swiftshader`).
2. Provide an explicit `HumanDecision` with decision `"APPROVE"`, rationale, and review context.
3. Execute the approve-lock pipeline to compute the final `LOCK_DIGEST`.

Until that action is performed:
```
READY_FOR_HUMAN_REVIEW = TRUE
NO GPU SELECTED
NO HUMAN DECISION CREATED
NO LOCK_DIGEST CREATED
```
