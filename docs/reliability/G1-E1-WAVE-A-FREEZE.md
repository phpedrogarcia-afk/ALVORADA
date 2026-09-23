# ALVORADA G1 E1 WAVE A — AUDITED RELIABILITY FREEZE RECORD

**Classification**: `G1_E1_CORE_RELIABILITY_WAVE_A = PASS`  
**Evidence Scope**: `E1_EMULATOR_REFERENCE_ENVIRONMENT_ONLY`  
**Freeze Date**: 2026-09-23  
**Working Branch**: `fio/g1-autonomy-recovery`  
**Canonical Main**: `43018b1f9b14cb9e580d2157e6cb623ee18de0d1` (READ ONLY)  
**Approved Reference Lock Digest**: `ac243a03caca0333eec85721cbd27f828a001c3b19ed80d7994e33589f065f05`  

---

## 1. Executive Summary & Authoritative Run Provenance

This document permanently freezes the audited empirical baseline of ALVORADA G1 E1 Wave A core reliability proof, executed on the approved API 36 reference emulator environment (`system-images;android-36;default;x86_64 revision 2`, swiftshader, emulator `37.1.11`).

| Attribute | Authoritative Value |
|:---|:---|
| **Authoritative Empirical Run ID** | `35802637509` |
| **Run Commit SHA** | `890cd119093c8b31ecd46ec8f28194451348757b` |
| **GitHub Artifact ID** | `10726798128` |
| **Artifact SHA-256 Digest** | `sha256:18ca71515307ce59b5ae2ae6e7ad2c3407855759af943464418248313010e8c3` |
| **Local Preserved Evidence Path** | `experiments/reliability-harness/evidence/execution-35802637509/` |
| **Android Scenario Execution Step** | `PASS` (`ALL PASS`, 100% scenarios completed cleanly) |
| **Workflow Step Conclusion** | `FAILURE` (Post-execution assert step looked for key `software_audio_playback_head_advanced` omitted from run 35802637509 report) |
| **Scientific Evidence Status** | `USABLE_WITH_EXPLICIT_BOUNDARY` |

---

## 2. Statistical Corrections & Authoritative Values

### Correction A — Scenario A1 Baseline Delivery Deltas
Observed 10 empirical delivery deltas (ms) from Run 35802637509:
`[3433, 2001, 2001, 2001, 2001, 2001, 2001, 2001, 2001, 2002]`

Sorted order:
`[2001, 2001, 2001, 2001, 2001, 2001, 2001, 2001, 2002, 3433]`

Using frozen nearest-rank method $\text{rank} = \lceil 0.95 \times 10 \rceil = 10$:
- **`WAVE_A_A1_MEDIAN`**: `2001.0 ms`
- **`WAVE_A_A1_P95`**: `3433 ms` (superseding ad-hoc `2002 ms` calculation)

### Correction B — Scenario A2 Process Death
Observed 10 empirical delivery deltas (ms) from Run 35802637509:
- **`WAVE_A_A2_MEDIAN`**: `1002.0 ms`
- **`WAVE_A_A2_P95`**: `1002 ms`
- **`A2_TARGET_COUNT`**: `10` ($0 \le \delta \le 2000\text{ ms}$)
- **`A2_ACCEPTABLE_COUNT`**: `0`
- **`A2_FAIL_COUNT`**: `0`

### Correction C — Combined Timing Bands
- **`COMBINED_MEDIAN`**: `1501.5 ms`
- **`COMBINED_P95`**: `2002 ms`
- **`TARGET`**: `10` (A2 occurrences in $[0, 2000\text{ ms}]$)
- **`ACCEPTABLE`**: `10` (A1 occurrences in $(2000, 5000\text{ ms}]$)
- **`FAIL`**: `0`

---

## 3. Epistemic Boundaries & Corrections D & E

### Correction D — Exact-Alarm Readiness Decay
- **Observed**: In Run 35802637509 Phase 12, `appops set org.alvorada.reliability.wakecore SCHEDULE_EXACT_ALARM ignore` returned `canScheduleExactAlarms() == True` because the test manifest simultaneously declared `USE_EXACT_ALARM`.
- **Classification**: `READINESS_DECAY = UNPROVEN_IN_CURRENT_PROFILE`.
- **Action**: Do NOT claim readiness decay was enforced in Wave A. This is deferred to Wave B where permission profiles are isolated.

### Correction E — Audio Playback Head Advancement
- **Observed**: In Run 35802637509, `software_audio_playback_head_advanced` was set in app device-protected storage but was omitted from the serialized top-level report.
- **Classification**: `PLAYBACK_HEAD_ADVANCED = UNPROVEN_FOR_RUN_35802637509`.
- **Rule**: Fabricated post-hoc assignments (`report["software_audio_playback_head_advanced"] = True`) are removed. Future derivations must strictly reflect per-occurrence observations.

### Immutable Epistemic Invariants
- **`AUDIBLE = UNPROVEN`**: Emulator audio track execution does not prove acoustic sound waves reached human ears.
- **`HUMAN_AWAKE = UNPROVEN`**: Alarm trigger and software audio execution do not prove human neurological awakening.

---

## 4. Capability Matrix: Proven vs. Unproven

### Explicitly Proven Capabilities (Scope: E1 Emulator Only)
1. **Baseline Exact Alarm**: Reliable scheduling and delivery via `AlarmManager.setAlarmClock`.
2. **Process Death**: Clean survival of process termination (`am kill`) with verified PID absence and new PID recreation upon trigger.
3. **New Process Recreation**: Cold start by platform alarm trigger without manual invocation.
4. **Duplicate Defense**: Strict rejection of duplicate intents and duplicate callbacks (`duplicate_trigger_count == 0`).
5. **Authority Identity**: Strict validation of `alarm_id`, `occurrence_id`, and `generation` prior to state mutation.
6. **Generation Defense**: Stale and future generation tampering rejected fail-closed.
7. **Snooze Child**: Parent occurrence snooze creates authoritative child occurrence that triggers cleanly.
8. **Dismiss**: Active session dismissed cleanly while preserving recurring civil rule.
9. **Guest Reboot**: Device reboot (`adb reboot`) survived across 3 independent guest reboot cycles.
10. **Automatic Boot Reconciliation**: Tripartite observation:
    - *Surface A (Logcat)*: `WakeBootReceiver` logged `BOOT_COMPLETED` without manual app invocation.
    - *Surface B (AlarmManager)*: Platform rescheduled PendingIntent bound to authoritative occurrence.
    - *Surface C (Read Observer)*: Read-only `DUMP_STATE` verified internal store reconciliation.
11. **AlarmManager Reschedule**: Occurrence correctly scheduled into platform AlarmManager post-reboot.
12. **Reconciliation Idempotence**: 10 sequential reconciliation invocations produced zero duplicate occurrences or spurious triggers.
13. **Late Recovery Policy**: Overdue $\le 10\text{ min}$ marks `RECOVERED_LATE`; overdue $> 10\text{ min}$ rejects late surprise firing (`OUTCOME_UNKNOWN`).
14. **Force-Stop Behavior**: App force-stop halts alarms and suppresses delivery as expected by Android platform semantics.
15. **Software-Audio Engine Start**: `AudioTrack` initialized in `MODE_STATIC` with valid synthetic PCM buffer and playback initiated.
16. **Audio Fail-Closed Behavior**: Simulated audio init, write, and play failures transition cleanly to `SOFTWARE_AUDIO_FAILED` without crash or silent corruption.

### Explicitly NOT Proven (Epistemic Boundaries)
1. **Physical Audibility**: Not proven without calibrated microphone telemetry.
2. **Human Awake**: Not proven without biological sensor or interaction verification.
3. **Pre-Unlock Direct Boot**: Not proven until credential-encrypted storage remains locked during boot.
4. **Real Permission Revocation**: Not proven due to dual permission declaration confounding appops.
5. **Timezone / DST End-to-End**: Not proven across civil time transitions and IANA zone boundaries.
6. **Physical Device Reliability**: Not proven on real hardware with battery managers and OEM custom power frameworks.
7. **OEM Behavior**: Not proven on non-AOSP OEM Android skins (Samsung, Xiaomi, etc.).

---

## 5. Campaign Closure Sign-Off

Campaign `ALVORADA_G1_E1_WAVE_A_CLOSURE_002` is formally **CLOSED**:
- `status`: `CLOSED_PASS_WITH_POST_ASSERTION_FAILURE`
- `verification_result`: `EMPIRICAL_WAVE_A_PASS`
- `ci_runs_dispatched`: `2`
- `ci_budget`: `2`
- `ci_budget_remaining`: `0`
- `ci_budget_exhausted`: `YES`

Wave A evidence is permanently frozen. Wave B Platform Semantics begins immediately under Campaign 003.
