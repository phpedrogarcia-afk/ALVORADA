# HOST RUNTIME PREREQUISITES & CAUSAL EVIDENCE

**Status:** RECOVERY-G1-001 RECOVERY CANDIDATE SPECIFICATION<br>
**Contract Version:** `ALVORADA_HOST_PREREQUISITES_V1`<br>
**Classification:** `OBSERVED_HOST_RUNTIME_PREREQUISITE`

---

## 1. Context and Observed Causal Fact

During G1 baseline probing on Linux runners (Ubuntu 24.04 LTS on GitHub Actions runner `ubuntu-24.04`), execution of the Android Emulator binary (`emulator -version`) failed with exit code 127:

```
emulator: error while loading shared libraries: libpulse.so.0: cannot open shared object file: No such file or directory
```

Dynamic linker inspection demonstrated that the 64-bit ELF binary `emulator` links against `libpulse.so.0` (PulseAudio client library), which is not pre-installed in minimal Ubuntu 24.04 runner images.

Following an ephemeral host-level provisioning of package `libpulse0`:
```bash
sudo apt-get update && sudo apt-get install -y --no-install-recommends libpulse0
```
the experimental probe demonstrated immediate resolution:
1. `emulator -version` executed successfully, returning `Android emulator version 37.1.11.0 (build_id 13028291)`.
2. `emulator -accel-check` executed successfully, returning `accel: 0` (confirming KVM hardware acceleration availability).

Within the observed runner image and Emulator revision, libpulse0 was the missing runtime dependency that blocked CLI initialization; this does not establish completeness for other images or revisions.

---

## 2. Formal Architectural Classification

`libpulse0` is formally classified as:

$$\mathbf{OBSERVED\_HOST\_RUNTIME\_PREREQUISITE}$$

It is **STRICTLY NOT** an Android SDK package, and it is **NEVER** part of the Android SDK `HARD_LOCK` package matrix (`emulator`, `platform-tools`, `platforms;android-36`, `build-tools;36.0.0`, `system-images;android-36;default;x86_64`).

### Distinction Matrix

| Dimension | Android SDK Hard Lock Packages | Host Runtime Prerequisite (`libpulse0`) |
| :--- | :--- | :--- |
| **Domain** | Android SDK cmdline-tools (`sdkmanager`) | Host Linux OS (`apt` / shared library system) |
| **Catalog** | Google Android Repository XML | Canonical Ubuntu 24.04 APT repository |
| **Discovery** | `sdkmanager --list --verbose` | `ldd` dynamic linker audit / package query |
| **Immutability** | Cryptographically pinned in Catalog Lock | Managed by host OS environment specification |
| **Mutability Lane** | Wave 1 SDK provisioning (sandboxed) | Ephemeral host runner preparation |

---

## 3. Mandatory Governance & Execution Envelope

If any future provisioning or execution probe requires `libpulse0`, the following operational constraints are binding and must be strictly enforced:

1. **Ephemeral Runners Only:** Installation is permitted solely inside isolated, disposable CI virtual machines (e.g. GitHub Actions cloud runners). It is forbidden to attempt host package mutations on developer workstations or persistent production infrastructure without operator intent.
2. **Empirical Proof of Absence Before Mutation:** Installation must be conditional. A pre-flight inspection (e.g. `ldconfig -p | grep libpulse.so.0` or dynamic link verification on the `emulator` binary) must empirically prove absence before invoking package management.
3. **Explicit Mutation Declaration:** The host package installation cannot be hidden, aliased, or bundled inside SDK management scripts. It must be an explicitly named step in the CI workflow (e.g. `step: "Host OS: Provision ephemeral libpulse0 prerequisite"`).
4. **Before/After Evidence Capture:** Execution must log evidence verifying the linker state immediately before the installation and immediately after, proving causal resolution.
5. **No Conflation with Read-Only Catalog Discovery:** Read-Only Catalog Discovery is strictly non-mutating (`CatalogReadOnlyPolicy`). Installing `libpulse0` is a host environment preparation step and must **NEVER** be executed during or labeled as Catalog Discovery.
