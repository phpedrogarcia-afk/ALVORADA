package org.alvorada.reliability;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.time.LocalDate;
import java.time.LocalTime;
import java.time.ZoneId;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Random;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Dependency-free E0 runner. Every test is deterministic and fail-fast at suite exit. */
public final class E0TestRunner {
    private static final Instant BASE_T = Instant.parse("2026-01-15T07:30:00Z");
    private static final LocalDate BASE_DATE = LocalDate.of(2026, 1, 15);
    private static final String BOOT = "boot-e0";
    private static final String BUILD = "harness-0.1.0";
    private static final String CELL = "JVM-E0";
    private static final long[] PROPERTY_SEEDS = {
            104729L, 130363L, 155921L, 196613L, 249439L,
            314159L, 524287L, 786433L, 999983L, 15485863L
    };
    private static final int SEQUENCES_PER_SEED = 10_000;

    private final List<TestResult> results = new ArrayList<>();
    private long assertions;

    public static void main(String[] args) {
        String suite = "all";
        for (String argument : args) {
            if (argument.startsWith("--suite=")) suite = argument.substring("--suite=".length());
            else {
                System.err.println("unknown argument: " + argument);
                System.exit(64);
            }
        }
        if (!Set.of("all", "deterministic", "property").contains(suite)) {
            System.err.println("suite must be all, deterministic, or property");
            System.exit(64);
        }

        E0TestRunner runner = new E0TestRunner();
        long started = System.nanoTime();
        if (!suite.equals("property")) runner.registerDeterministicTests();
        if (!suite.equals("deterministic")) runner.registerPropertyTests();
        long durationMillis = (System.nanoTime() - started) / 1_000_000L;
        runner.report(suite, durationMillis);
    }

    private void registerDeterministicTests() {
        test("occurrence identity is deterministic", "I-02", () -> {
            String first = AlarmModel.occurrenceId("alarm-a", 1, BASE_DATE, LocalTime.of(7, 30), 0, null);
            String second = AlarmModel.occurrenceId("alarm-a", 1, BASE_DATE, LocalTime.of(7, 30), 0, null);
            equal(first, second);
            check(first.startsWith("occ-"));
            equal(68, first.length());
        });

        test("generation changes occurrence identity", "I-01,I-02", () -> {
            String first = AlarmModel.occurrenceId("alarm-a", 1, BASE_DATE, LocalTime.of(7, 30), 0, null);
            String next = AlarmModel.occurrenceId("alarm-a", 2, BASE_DATE, LocalTime.of(7, 30), 0, null);
            notEqual(first, next);
        });

        test("civil date changes occurrence identity", "I-02", () -> {
            String first = AlarmModel.occurrenceId("alarm-a", 1, BASE_DATE, LocalTime.of(7, 30), 0, null);
            String next = AlarmModel.occurrenceId("alarm-a", 1, BASE_DATE.plusDays(1), LocalTime.of(7, 30), 0, null);
            notEqual(first, next);
        });

        test("same materialization is idempotent", "I-02,I-04", () -> {
            AlarmModel.Engine engine = baseEngine("alarm-idempotent");
            AlarmModel.Occurrence first = engine.materialize("alarm-idempotent", BASE_DATE, BOOT);
            AlarmModel.Occurrence second = engine.materialize("alarm-idempotent", BASE_DATE, BOOT);
            equal(first.occurrenceId(), second.occurrenceId());
            equal(1, engine.occurrences().size());
        });

        test("adversarial duplicate ID with different semantics fails closed", "I-02", () -> {
            AlarmModel.Engine engine = baseEngine("alarm-collision");
            AlarmModel.Occurrence occurrence = engine.materialize("alarm-collision", BASE_DATE, BOOT);
            AlarmModel.OccurrenceSnapshot source = engine.snapshot().occurrences().get(occurrence.occurrenceId());
            AlarmModel.OccurrenceSnapshot conflict = new AlarmModel.OccurrenceSnapshot(
                    source.occurrenceId(), "different-alarm", source.generation(), source.civilDate(),
                    source.civilTime(), source.zoneId(), source.scheduledInstant(), source.selectedOffset(),
                    source.parentOccurrenceId(), source.snoozeDeadlineMonotonicMillis(),
                    source.originatingBootId(), source.state(), source.schedulingObservation(),
                    source.tombstone(), source.checkpoint(), source.triggerWallMillis(),
                    source.softwareAudioMonotonicMillis(), source.physicalAudioObserved(), source.humanAwake());
            expectThrows(IllegalStateException.class, () -> engine.importOccurrence(conflict));
            equal(1, engine.occurrences().size());
        });

        test("configured is not armed verified", "I-03,I-14", () -> {
            ArmedFixture fixture = configuredFixture("alarm-configured");
            equal(AlarmModel.OccurrenceState.CONFIGURED, fixture.occurrence().state());
            AlarmModel.EvidenceProjection evidence = fixture.engine().evidence(fixture.occurrence().occurrenceId());
            check(evidence.configured());
            check(!evidence.armedVerified());
            check(!evidence.triggered());
            check(!evidence.softwareAudioStarted());
            check(!evidence.physicalAudioObserved());
            check(!evidence.humanAwake());
        });

        test("armed verified requires register and durable checkpoint", "I-03", () -> {
            ArmedFixture fixture = configuredFixture("alarm-arm");
            String id = fixture.occurrence().occurrenceId();
            fixture.engine().requireReadiness(id);
            fixture.engine().markArmable(id);
            fixture.engine().requestScheduling(id);
            check(!fixture.engine().evidence(id).armedVerified());
            fixture.engine().acknowledgeScheduling(id, checkpoint(1, BOOT));
            equal(AlarmModel.OccurrenceState.ARMED_VERIFIED, fixture.occurrence().state());
            equal(AlarmModel.SchedulingObservation.REGISTERED, fixture.occurrence().schedulingObservation());
            check(fixture.engine().evidence(id).armedVerified());
        });

        test("mismatched readiness checkpoint cannot arm", "I-03,I-11", () -> {
            ArmedFixture fixture = configuredFixture("alarm-bad-checkpoint");
            String id = fixture.occurrence().occurrenceId();
            fixture.engine().requireReadiness(id);
            fixture.engine().markArmable(id);
            fixture.engine().requestScheduling(id);
            expectThrows(IllegalArgumentException.class,
                    () -> fixture.engine().acknowledgeScheduling(id, checkpoint(2, BOOT)));
            equal(AlarmModel.OccurrenceState.RECOVERY_REQUIRED, fixture.occurrence().state());
            check(!fixture.engine().evidence(id).armedVerified());
        });

        test("checkpoint identity binds boot build cell and generation", "I-11", () -> {
            AlarmModel.ReadinessCheckpoint checkpoint = checkpoint(1, BOOT);
            check(checkpoint.isCurrentFor(BOOT, BUILD, CELL, 1));
            check(!checkpoint.isCurrentFor("other-boot", BUILD, CELL, 1));
            check(!checkpoint.isCurrentFor(BOOT, "other-build", CELL, 1));
            check(!checkpoint.isCurrentFor(BOOT, BUILD, "other-cell", 1));
            check(!checkpoint.isCurrentFor(BOOT, BUILD, CELL, 2));
        });

        test("crash after intent persistence has no armed claim", "I-03", () -> {
            ArmedFixture fixture = configuredFixture("alarm-crash-intent");
            AlarmModel.ScheduleCrashObservation result = fixture.engine().simulateSchedulingCrash(
                    fixture.occurrence().occurrenceId(),
                    AlarmModel.ScheduleCrashPoint.AFTER_INTENT_PERSISTED, checkpoint(1, BOOT));
            check(!result.armedVerifiedClaimAllowed());
            equal(AlarmModel.OccurrenceState.CONFIGURED, result.occurrenceState());
        });

        test("crash after scheduling before checkpoint requires recovery", "I-03,I-08", () -> {
            ArmedFixture fixture = configuredFixture("alarm-crash-schedule");
            String id = fixture.occurrence().occurrenceId();
            fixture.engine().requireReadiness(id);
            fixture.engine().markArmable(id);
            fixture.engine().requestScheduling(id);
            AlarmModel.ScheduleCrashObservation result = fixture.engine().simulateSchedulingCrash(
                    id, AlarmModel.ScheduleCrashPoint.AFTER_SCHEDULING_ACCEPTED, checkpoint(1, BOOT));
            equal(AlarmModel.SchedulingObservation.REGISTERED, result.schedulingObservation());
            equal(AlarmModel.OccurrenceState.RECOVERY_REQUIRED, result.occurrenceState());
            check(!result.armedVerifiedClaimAllowed());
        });

        test("checkpoint persisted permits historical armed claim", "I-03", () -> {
            ArmedFixture fixture = configuredFixture("alarm-crash-checkpoint");
            String id = fixture.occurrence().occurrenceId();
            fixture.engine().requireReadiness(id);
            fixture.engine().markArmable(id);
            fixture.engine().requestScheduling(id);
            AlarmModel.ScheduleCrashObservation result = fixture.engine().simulateSchedulingCrash(
                    id, AlarmModel.ScheduleCrashPoint.AFTER_CHECKPOINT_PERSISTED, checkpoint(1, BOOT));
            equal(AlarmModel.OccurrenceState.ARMED_VERIFIED, result.occurrenceState());
            check(result.armedVerifiedClaimAllowed());
        });

        test("relevant event makes readiness stale", "I-11", () -> {
            ArmedFixture fixture = armedFixture("alarm-stale");
            fixture.engine().markReadinessStale(fixture.occurrence().occurrenceId(), "TIME_CHANGED");
            equal(AlarmModel.OccurrenceState.READINESS_STALE, fixture.occurrence().state());
            equal(AlarmModel.SchedulingObservation.INVALIDATED, fixture.occurrence().schedulingObservation());
            check(!fixture.engine().evidence(fixture.occurrence().occurrenceId()).armedVerified());
        });

        test("old generation trigger is rejected", "I-01,I-05", () -> {
            ArmedFixture fixture = armedFixture("alarm-old-generation");
            fixture.engine().editZone("alarm-old-generation", ZoneId.of("Europe/Lisbon"));
            AlarmModel.TriggerResult result = fixture.engine().receiveTrigger(
                    fixture.occurrence().occurrenceId(), "callback-old", 1, BASE_T);
            equal(AlarmModel.TriggerDisposition.STALE_GENERATION, result.disposition());
            check(fixture.occurrence().tombstone());
            check(fixture.occurrence().state() != AlarmModel.OccurrenceState.RINGING);
        });

        test("disabled intent rejects old trigger", "I-01,I-05", () -> {
            ArmedFixture fixture = armedFixture("alarm-disabled");
            fixture.engine().disable("alarm-disabled");
            AlarmModel.TriggerResult result = fixture.engine().receiveTrigger(
                    fixture.occurrence().occurrenceId(), "callback-disabled", 1, BASE_T);
            equal(AlarmModel.TriggerDisposition.STALE_GENERATION, result.disposition());
            equal(AlarmModel.OccurrenceState.DISABLED, fixture.occurrence().state());
        });

        test("duplicate callback is suppressed", "I-04", () -> {
            ArmedFixture fixture = armedFixture("alarm-duplicate-trigger");
            String id = fixture.occurrence().occurrenceId();
            equal(AlarmModel.TriggerDisposition.ACCEPTED,
                    fixture.engine().receiveTrigger(id, "callback-1", 1, BASE_T).disposition());
            equal(AlarmModel.TriggerDisposition.DUPLICATE_SUPPRESSED,
                    fixture.engine().receiveTrigger(id, "callback-1", 1, BASE_T).disposition());
            equal(AlarmModel.OutputDisposition.STARTED,
                    fixture.engine().recordSoftwareAudioStart(id, 10_000L));
            equal(AlarmModel.OutputDisposition.DUPLICATE_SUPPRESSED,
                    fixture.engine().recordSoftwareAudioStart(id, 10_001L));
        });

        test("trigger from merely configured state is rejected", "I-01,I-03,I-14", () -> {
            ArmedFixture fixture = configuredFixture("alarm-invalid-trigger-state");
            AlarmModel.TriggerResult result = fixture.engine().receiveTrigger(
                    fixture.occurrence().occurrenceId(), "orphan-callback", 1, BASE_T);
            equal(AlarmModel.TriggerDisposition.INVALID_STATE, result.disposition());
            equal(AlarmModel.OccurrenceState.CONFIGURED, fixture.occurrence().state());
            check(!fixture.engine().evidence(fixture.occurrence().occurrenceId()).triggered());
        });

        test("T minus 500ms is early tolerance", "F-03-06", () ->
                equal(AlarmModel.DeliveryBand.EARLY_TOLERANCE,
                        AlarmModel.classifyDeliveryDelta(-500L)));

        test("earlier than T minus 500ms fails", "F-03-06", () ->
                equal(AlarmModel.DeliveryBand.FAILURE,
                        AlarmModel.classifyDeliveryDelta(-501L)));

        test("T is target", "F-03-06", () ->
                equal(AlarmModel.DeliveryBand.TARGET,
                        AlarmModel.classifyDeliveryDelta(0L)));

        test("T plus 2s is target", "F-03-06", () ->
                equal(AlarmModel.DeliveryBand.TARGET,
                        AlarmModel.classifyDeliveryDelta(2_000L)));

        test("after 2s is acceptable late", "F-03-06", () ->
                equal(AlarmModel.DeliveryBand.ACCEPTABLE_LATE,
                        AlarmModel.classifyDeliveryDelta(2_001L)));

        test("T plus 5s is acceptable late", "F-03-06", () ->
                equal(AlarmModel.DeliveryBand.ACCEPTABLE_LATE,
                        AlarmModel.classifyDeliveryDelta(5_000L)));

        test("after T plus 5s fails delivery band", "F-03-06", () ->
                equal(AlarmModel.DeliveryBand.FAILURE,
                        AlarmModel.classifyDeliveryDelta(5_001L)));

        test("software audio boundaries preserve unknown", "F-03-07,I-08,I-14", () -> {
            equal(AlarmModel.AudioBand.UNKNOWN, AlarmModel.classifyAudioDelta(null));
            equal(AlarmModel.AudioBand.TARGET, AlarmModel.classifyAudioDelta(1_000L));
            equal(AlarmModel.AudioBand.ACCEPTABLE, AlarmModel.classifyAudioDelta(1_001L));
            equal(AlarmModel.AudioBand.ACCEPTABLE, AlarmModel.classifyAudioDelta(3_000L));
            equal(AlarmModel.AudioBand.FAILURE, AlarmModel.classifyAudioDelta(3_001L));
            equal(AlarmModel.AudioBand.FAILURE, AlarmModel.classifyAudioDelta(-1L));
        });

        test("late recovery includes T plus 10 minutes", "F-03-05", () ->
                equal(AlarmModel.RecoveryDecision.RECOVER_NOW,
                        AlarmModel.lateRecoveryDecision(BASE_T, BASE_T.plusMillis(600_000L), false, true)));

        test("after 10 minutes confirmed delivery failure is missed", "F-03-05", () ->
                equal(AlarmModel.RecoveryDecision.MISSED,
                        AlarmModel.lateRecoveryDecision(BASE_T, BASE_T.plusMillis(600_001L), false, true)));

        test("after 10 minutes without oracle is outcome unknown", "F-03-05,I-08", () ->
                equal(AlarmModel.RecoveryDecision.OUTCOME_UNKNOWN,
                        AlarmModel.lateRecoveryDecision(BASE_T, BASE_T.plusMillis(600_001L), false, false)));

        test("before T is not due", "F-03-05", () ->
                equal(AlarmModel.RecoveryDecision.NOT_DUE,
                        AlarmModel.lateRecoveryDecision(BASE_T, BASE_T.minusMillis(1L), false, true)));

        test("terminal occurrence skips late recovery", "I-05", () ->
                equal(AlarmModel.RecoveryDecision.SKIP_TERMINAL,
                        AlarmModel.lateRecoveryDecision(BASE_T, BASE_T.plusMillis(1L), true, true)));

        test("time forward performs one late recovery", "I-04,F-03-05", () -> {
            ArmedFixture fixture = armedFixture("alarm-forward");
            AlarmModel.RecoveryDecision first = fixture.engine().reconcileLate(
                    fixture.occurrence().occurrenceId(), BASE_T.plusSeconds(120), true,
                    "event-forward", "TIME_CHANGED");
            AlarmModel.RecoveryDecision duplicate = fixture.engine().reconcileLate(
                    fixture.occurrence().occurrenceId(), BASE_T.plusSeconds(120), true,
                    "event-forward", "TIME_CHANGED");
            equal(AlarmModel.RecoveryDecision.RECOVER_NOW, first);
            equal(first, duplicate);
            equal(1, fixture.engine().reconciliations().size());
        });

        test("time backward never reopens dismissed occurrence", "I-05", () -> {
            ArmedFixture fixture = ringingFixture("alarm-backward");
            String id = fixture.occurrence().occurrenceId();
            check(fixture.engine().dismiss(id));
            AlarmModel.RecoveryDecision result = fixture.engine().reconcileLate(
                    id, BASE_T.minusSeconds(3_600), false, "event-backward", "TIME_CHANGED");
            equal(AlarmModel.RecoveryDecision.SKIP_TERMINAL, result);
            equal(AlarmModel.OccurrenceState.DISMISSED, fixture.occurrence().state());
        });

        test("timezone change preserves civil time and increments generation", "F-03-02,I-01", () -> {
            AlarmModel.Engine engine = baseEngine("alarm-zone");
            AlarmModel.Occurrence utc = engine.materialize("alarm-zone", BASE_DATE, BOOT);
            AlarmModel.AlarmIntent changed = engine.editZone("alarm-zone", ZoneId.of("America/Sao_Paulo"));
            AlarmModel.Occurrence saoPaulo = engine.materialize("alarm-zone", BASE_DATE, BOOT);
            equal(LocalTime.of(7, 30), utc.civilTime());
            equal(LocalTime.of(7, 30), saoPaulo.civilTime());
            equal(2L, changed.generation());
            notEqual(utc.scheduledInstant(), saoPaulo.scheduledInstant());
            check(utc.tombstone());
        });

        test("repeated timezone changes produce monotonic generations", "I-01", () -> {
            AlarmModel.Engine engine = baseEngine("alarm-zones");
            engine.materialize("alarm-zones", BASE_DATE, BOOT);
            equal(2L, engine.editZone("alarm-zones", ZoneId.of("Europe/Lisbon")).generation());
            equal(3L, engine.editZone("alarm-zones", ZoneId.of("Asia/Tokyo")).generation());
            equal(4L, engine.editZone("alarm-zones", ZoneId.of("UTC")).generation());
        });

        test("DST gap resolves to first valid local time", "F-03-03", () -> {
            AlarmModel.CivilResolution result = AlarmModel.resolveCivil(
                    LocalDate.of(2024, 3, 10), LocalTime.of(2, 30), ZoneId.of("America/New_York"));
            equal(LocalTime.of(3, 0), result.resolvedLocal().toLocalTime());
            equal("GAP_FORWARD", result.dstAdjustment());
            equal(ZoneOffset.ofHours(-4), result.selectedOffset());
        });

        test("DST fold selects first offset exactly once", "F-03-04", () -> {
            AlarmModel.CivilResolution first = AlarmModel.resolveCivil(
                    LocalDate.of(2024, 11, 3), LocalTime.of(1, 30), ZoneId.of("America/New_York"));
            AlarmModel.CivilResolution again = AlarmModel.resolveCivil(
                    LocalDate.of(2024, 11, 3), LocalTime.of(1, 30), ZoneId.of("America/New_York"));
            equal("FOLD_FIRST", first.dstAdjustment());
            equal(ZoneOffset.ofHours(-4), first.selectedOffset());
            equal(first.instant(), again.instant());
            equal(0, first.foldOrdinal());
        });

        test("fold callback cannot create a second session", "F-03-04,I-04", () -> {
            AlarmModel.Engine engine = new AlarmModel.Engine();
            engine.configure("alarm-fold", LocalTime.of(1, 30), ZoneId.of("America/New_York"));
            AlarmModel.Occurrence occurrence = engine.materialize(
                    "alarm-fold", LocalDate.of(2024, 11, 3), BOOT);
            arm(engine, occurrence);
            Instant firstOffset = occurrence.scheduledInstant();
            equal(AlarmModel.TriggerDisposition.ACCEPTED,
                    engine.receiveTrigger(occurrence.occurrenceId(), "fold-os-token", 1, firstOffset).disposition());
            equal(AlarmModel.TriggerDisposition.DUPLICATE_SUPPRESSED,
                    engine.receiveTrigger(occurrence.occurrenceId(), "fold-os-token", 1,
                            firstOffset.plusSeconds(3_600)).disposition());
        });

        test("dismiss is idempotent and terminal", "I-04,I-05", () -> {
            ArmedFixture fixture = ringingFixture("alarm-dismiss");
            String id = fixture.occurrence().occurrenceId();
            check(fixture.engine().dismiss(id));
            check(!fixture.engine().dismiss(id));
            equal(AlarmModel.OccurrenceState.DISMISSED, fixture.occurrence().state());
            check(fixture.occurrence().tombstone());
            equal(AlarmModel.OutputDisposition.DUPLICATE_SUPPRESSED,
                    fixture.engine().recordSoftwareAudioStart(id, 20_000L));
        });

        test("first software callback after terminal is rejected", "I-04,I-05,I-14", () -> {
            ArmedFixture fixture = armedFixture("alarm-terminal-callback");
            String id = fixture.occurrence().occurrenceId();
            fixture.engine().receiveTrigger(id, "callback", 1, BASE_T);
            check(fixture.engine().dismiss(id));
            equal(AlarmModel.OutputDisposition.REJECTED,
                    fixture.engine().recordSoftwareAudioStart(id, 20_000L));
            equal(AlarmModel.OccurrenceState.DISMISSED, fixture.occurrence().state());
            check(!fixture.engine().evidence(id).softwareAudioStarted());
        });

        test("recurrence materializes after occurrence dismiss", "I-05", () -> {
            ArmedFixture fixture = ringingFixture("alarm-recurring");
            fixture.engine().dismiss(fixture.occurrence().occurrenceId());
            AlarmModel.Occurrence next = fixture.engine().materialize(
                    "alarm-recurring", BASE_DATE.plusDays(1), BOOT);
            notEqual(fixture.occurrence().occurrenceId(), next.occurrenceId());
            equal(AlarmModel.OccurrenceState.CONFIGURED, next.state());
            equal(AlarmModel.IntentStatus.ENABLED, fixture.engine().intent("alarm-recurring").status());
        });

        test("snooze creates five-minute child", "F-03-08", () -> {
            ArmedFixture fixture = ringingFixture("alarm-snooze");
            AlarmModel.SnoozeResult snooze = fixture.engine().requestSnooze(
                    fixture.occurrence().occurrenceId(), BASE_T.plusSeconds(10), 20_000L, BOOT);
            AlarmModel.Occurrence child = fixture.engine().occurrence(snooze.childOccurrenceId());
            check(snooze.created());
            equal(fixture.occurrence().occurrenceId(), child.parentOccurrenceId());
            equal(BASE_T.plusSeconds(310), child.scheduledInstant());
            equal(320_000L, child.snoozeDeadlineMonotonicMillis());
            notEqual(fixture.occurrence().occurrenceId(), child.occurrenceId());
        });

        test("duplicate snooze returns one child", "I-04,F-03-08", () -> {
            ArmedFixture fixture = ringingFixture("alarm-snooze-duplicate");
            AlarmModel.SnoozeResult first = fixture.engine().requestSnooze(
                    fixture.occurrence().occurrenceId(), BASE_T, 100L, BOOT);
            AlarmModel.SnoozeResult duplicate = fixture.engine().requestSnooze(
                    fixture.occurrence().occurrenceId(), BASE_T.plusSeconds(1), 1_100L, BOOT);
            equal(first.childOccurrenceId(), duplicate.childOccurrenceId());
            check(first.created());
            check(!duplicate.created());
            equal(2, fixture.engine().occurrences().size());
        });

        test("parent snoozes only after child scheduling confirmation", "F-03-08,I-03", () -> {
            ArmedFixture fixture = ringingFixture("alarm-snooze-confirm");
            AlarmModel.SnoozeResult result = fixture.engine().requestSnooze(
                    fixture.occurrence().occurrenceId(), BASE_T, 100L, BOOT);
            equal(AlarmModel.OccurrenceState.SNOOZE_PENDING, fixture.occurrence().state());
            check(!fixture.occurrence().tombstone());
            fixture.engine().confirmSnooze(fixture.occurrence().occurrenceId(), checkpoint(1, BOOT));
            equal(AlarmModel.OccurrenceState.SNOOZED, fixture.occurrence().state());
            check(fixture.occurrence().tombstone());
            equal(AlarmModel.OccurrenceState.ARMED_VERIFIED,
                    fixture.engine().occurrence(result.childOccurrenceId()).state());
        });

        test("two close alarms have one owner and one waiting", "I-10,I-13", () -> {
            TwoAlarmFixture fixture = twoArmedAlarms();
            fixture.engine().receiveTrigger(fixture.first().occurrenceId(), "a", 1, BASE_T);
            fixture.engine().recordSoftwareAudioStart(fixture.first().occurrenceId(), 100L);
            fixture.engine().receiveTrigger(fixture.second().occurrenceId(), "b", 1, BASE_T.plusSeconds(1));
            equal(AlarmModel.OutputDisposition.WAITING,
                    fixture.engine().recordSoftwareAudioStart(fixture.second().occurrenceId(), 101L));
            equal(fixture.first().occurrenceId(), fixture.engine().outputOwner().orElseThrow());
            equal(AlarmModel.OccurrenceState.OUTPUT_WAITING, fixture.second().state());
            fixture.engine().verifyInternalInvariants();
        });

        test("dismiss owner does not dismiss waiting alarm", "I-10,I-13,F-03-09", () -> {
            TwoAlarmFixture fixture = twoArmedAlarms();
            fixture.engine().receiveTrigger(fixture.first().occurrenceId(), "a", 1, BASE_T);
            fixture.engine().recordSoftwareAudioStart(fixture.first().occurrenceId(), 100L);
            fixture.engine().receiveTrigger(fixture.second().occurrenceId(), "b", 1, BASE_T.plusSeconds(1));
            fixture.engine().recordSoftwareAudioStart(fixture.second().occurrenceId(), 101L);
            fixture.engine().dismiss(fixture.first().occurrenceId());
            equal(AlarmModel.OccurrenceState.DISMISSED, fixture.first().state());
            equal(AlarmModel.OccurrenceState.OUTPUT_WAITING, fixture.second().state());
            check(fixture.engine().outputOwner().isEmpty());
            equal(AlarmModel.OutputDisposition.STARTED,
                    fixture.engine().promoteWaiting(fixture.second().occurrenceId(), 102L));
        });

        test("failure of one occurrence is not success from another", "I-10", () -> {
            TwoAlarmFixture fixture = twoArmedAlarms();
            fixture.engine().reconcileLate(fixture.first().occurrenceId(),
                    BASE_T.plusSeconds(601), true, "miss-a", "TIME_CHANGED");
            fixture.engine().receiveTrigger(fixture.second().occurrenceId(), "b", 1, BASE_T.plusSeconds(1));
            fixture.engine().recordSoftwareAudioStart(fixture.second().occurrenceId(), 1_000L);
            equal(AlarmModel.OccurrenceState.MISSED, fixture.first().state());
            equal(AlarmModel.OccurrenceState.RINGING, fixture.second().state());
        });

        test("session stops at 30-minute boundary", "I-09,F-03-10", () -> {
            ArmedFixture fixture = ringingFixture("alarm-timeout");
            Long started = fixture.occurrence().softwareAudioMonotonicMillis();
            check(!fixture.engine().applySessionTimeout(
                    fixture.occurrence().occurrenceId(), started + AlarmModel.SESSION_LIMIT_MS - 1));
            check(fixture.engine().applySessionTimeout(
                    fixture.occurrence().occurrenceId(), started + AlarmModel.SESSION_LIMIT_MS));
            equal(AlarmModel.OccurrenceState.UNANSWERED, fixture.occurrence().state());
            check(fixture.engine().outputOwner().isEmpty());
        });

        test("local persistence preserves generation tombstone and dedupe", "I-01,I-04,I-05", () -> {
            ArmedFixture fixture = ringingFixture("alarm-persist");
            String id = fixture.occurrence().occurrenceId();
            fixture.engine().dismiss(id);
            Path directory = Files.createTempDirectory("alvorada-e0-state-");
            Path state = directory.resolve("state.bin");
            try {
                StateStore.saveAtomic(state, fixture.engine());
                AlarmModel.Engine loaded = StateStore.loadLocal(state);
                equal(1L, loaded.intent("alarm-persist").generation());
                equal(AlarmModel.OccurrenceState.DISMISSED, loaded.occurrence(id).state());
                check(loaded.occurrence(id).tombstone());
                equal(AlarmModel.TriggerDisposition.DUPLICATE_SUPPRESSED,
                        loaded.receiveTrigger(id, "callback", 1, BASE_T).disposition());
                loaded.verifyInternalInvariants();
            } finally {
                Files.deleteIfExists(state);
                Files.deleteIfExists(directory);
            }
        });

        test("state codec is deterministic for unchanged state", "REPRODUCIBILITY", () -> {
            ArmedFixture fixture = armedFixture("alarm-codec");
            Path directory = Files.createTempDirectory("alvorada-e0-codec-");
            Path first = directory.resolve("first.bin");
            Path second = directory.resolve("second.bin");
            try {
                StateStore.saveAtomic(first, fixture.engine());
                StateStore.saveAtomic(second, fixture.engine());
                byte[] a = Files.readAllBytes(first);
                byte[] b = Files.readAllBytes(second);
                check(Arrays.equals(a, b));
                check(a.length > 32);
            } finally {
                Files.deleteIfExists(first);
                Files.deleteIfExists(second);
                Files.deleteIfExists(directory);
            }
        });

        test("process crash during ringing clears output ownership and requires recovery", "I-08,I-13", () -> {
            ArmedFixture fixture = ringingFixture("alarm-crash-ringing");
            Path directory = Files.createTempDirectory("alvorada-e0-ringing-crash-");
            Path state = directory.resolve("state.bin");
            try {
                StateStore.saveAtomic(state, fixture.engine());
                AlarmModel.Engine resumed = StateStore.loadLocal(state);
                AlarmModel.Occurrence occurrence = resumed.occurrence(fixture.occurrence().occurrenceId());
                equal(AlarmModel.OccurrenceState.RECOVERY_REQUIRED, occurrence.state());
                check(resumed.outputOwner().isEmpty());
                check(resumed.evidence(occurrence.occurrenceId()).softwareAudioStarted());
                check(!resumed.evidence(occurrence.occurrenceId()).physicalAudioObserved());
                resumed.verifyInternalInvariants();
            } finally {
                Files.deleteIfExists(state);
                Files.deleteIfExists(directory);
            }
        });

        test("disable during ringing stops ownership and tombstones occurrence", "I-01,I-05,I-13", () -> {
            ArmedFixture fixture = ringingFixture("alarm-disable-ringing");
            fixture.engine().disable("alarm-disable-ringing");
            equal(AlarmModel.OccurrenceState.DISABLED, fixture.occurrence().state());
            check(fixture.occurrence().tombstone());
            check(fixture.engine().outputOwner().isEmpty());
            fixture.engine().verifyInternalInvariants();
        });

        test("disable during snooze pending closes parent and child", "I-01,I-05", () -> {
            ArmedFixture fixture = ringingFixture("alarm-disable-snooze");
            AlarmModel.SnoozeResult result = fixture.engine().requestSnooze(
                    fixture.occurrence().occurrenceId(), BASE_T, 100L, BOOT);
            fixture.engine().disable("alarm-disable-snooze");
            equal(AlarmModel.OccurrenceState.DISABLED, fixture.occurrence().state());
            equal(AlarmModel.OccurrenceState.DISABLED,
                    fixture.engine().occurrence(result.childOccurrenceId()).state());
            check(fixture.engine().outputOwner().isEmpty());
            fixture.engine().verifyInternalInvariants();
        });

        test("edit during ringing invalidates old generation and releases output", "I-01,I-05,I-13", () -> {
            ArmedFixture fixture = ringingFixture("alarm-edit-ringing");
            fixture.engine().editZone("alarm-edit-ringing", ZoneId.of("Europe/Lisbon"));
            equal(AlarmModel.OccurrenceState.INVALIDATED, fixture.occurrence().state());
            check(fixture.occurrence().tombstone());
            check(fixture.engine().outputOwner().isEmpty());
            fixture.engine().verifyInternalInvariants();
        });

        test("backup restore never restores armed state", "F-03-13,I-03,I-11", () -> {
            ArmedFixture fixture = armedFixture("alarm-restore");
            AlarmModel.Engine restored = AlarmModel.Engine.restoreFromBackup(
                    fixture.engine().snapshot(), "boot-after-restore");
            AlarmModel.Occurrence occurrence = restored.occurrence(fixture.occurrence().occurrenceId());
            equal(AlarmModel.OccurrenceState.READINESS_CHECK_REQUIRED, occurrence.state());
            equal(AlarmModel.SchedulingObservation.UNKNOWN, occurrence.schedulingObservation());
            check(occurrence.checkpoint() == null);
            check(!restored.evidence(occurrence.occurrenceId()).armedVerified());
        });

        test("terminal occurrence is omitted from backup restore", "F-03-13,I-05", () -> {
            ArmedFixture fixture = ringingFixture("alarm-restore-terminal");
            fixture.engine().dismiss(fixture.occurrence().occurrenceId());
            AlarmModel.Engine restored = AlarmModel.Engine.restoreFromBackup(
                    fixture.engine().snapshot(), "boot-after-restore");
            equal(0, restored.occurrences().size());
            equal(AlarmModel.IntentStatus.ENABLED, restored.intent("alarm-restore-terminal").status());
        });

        test("monotonic deadline is never reused across boot", "I-07", () -> {
            check(AlarmModel.mayReuseMonotonicDeadline("boot-a", "boot-a"));
            check(!AlarmModel.mayReuseMonotonicDeadline("boot-a", "boot-b"));
        });

        test("event received is not reconciliation complete", "I-12", () -> {
            AlarmModel.Engine engine = new AlarmModel.Engine();
            check(engine.receiveReconciliationEvent("event-1", "BOOT_COMPLETED"));
            equal(AlarmModel.ReconciliationResult.PENDING,
                    engine.reconciliations().get("event-1").result());
            engine.completeReconciliation("event-1", AlarmModel.ReconciliationResult.RECONCILED);
            equal(AlarmModel.ReconciliationResult.RECONCILED,
                    engine.reconciliations().get("event-1").result());
        });

        test("repeated reconciliation is idempotent", "I-04,I-12", () -> {
            AlarmModel.Engine engine = new AlarmModel.Engine();
            check(engine.receiveReconciliationEvent("event-repeat", "BOOT_COMPLETED"));
            check(!engine.receiveReconciliationEvent("event-repeat", "BOOT_COMPLETED"));
            engine.completeReconciliation("event-repeat", AlarmModel.ReconciliationResult.NOOP);
            engine.completeReconciliation("event-repeat", AlarmModel.ReconciliationResult.NOOP);
            equal(1, engine.reconciliations().size());
        });

        test("reconciliation event ID collision fails closed", "I-04,I-12", () -> {
            AlarmModel.Engine engine = new AlarmModel.Engine();
            check(engine.receiveReconciliationEvent("event-collision", "BOOT_COMPLETED"));
            expectThrows(IllegalStateException.class,
                    () -> engine.receiveReconciliationEvent("event-collision", "TIME_CHANGED"));
            equal("BOOT_COMPLETED", engine.reconciliations().get("event-collision").eventType());
        });

        test("out-of-order reconciliation completion is rejected", "I-12", () -> {
            AlarmModel.Engine engine = new AlarmModel.Engine();
            expectThrows(IllegalStateException.class,
                    () -> engine.completeReconciliation("not-received", AlarmModel.ReconciliationResult.RECONCILED));
        });

        test("conflicting replay result is rejected", "I-12", () -> {
            AlarmModel.Engine engine = new AlarmModel.Engine();
            engine.receiveReconciliationEvent("event-conflict", "BOOT_COMPLETED");
            engine.completeReconciliation("event-conflict", AlarmModel.ReconciliationResult.NOOP);
            expectThrows(IllegalStateException.class,
                    () -> engine.completeReconciliation("event-conflict", AlarmModel.ReconciliationResult.FAILED));
        });

        test("reboot reconciliation applied twice stays stale not duplicated", "I-04,I-11,I-12", () -> {
            ArmedFixture fixture = armedFixture("alarm-reboot-repeat");
            fixture.engine().markReadinessStale(fixture.occurrence().occurrenceId(), "LOCKED_BOOT_COMPLETED");
            fixture.engine().markReadinessStale(fixture.occurrence().occurrenceId(), "LOCKED_BOOT_COMPLETED");
            check(fixture.engine().receiveReconciliationEvent("locked-boot-1", "LOCKED_BOOT_COMPLETED"));
            check(!fixture.engine().receiveReconciliationEvent("locked-boot-1", "LOCKED_BOOT_COMPLETED"));
            equal(AlarmModel.OccurrenceState.READINESS_STALE, fixture.occurrence().state());
            equal(1, fixture.engine().reconciliations().size());
        });

        test("optional service absence does not change scheduling", "HI-01,HI-02,HI-03,I-06", () -> {
            ArmedFixture fixture = armedFixture("alarm-optional-absent");
            AlarmModel.OccurrenceState before = fixture.occurrence().state();
            AlarmModel.SchedulingObservation scheduling = fixture.occurrence().schedulingObservation();
            fixture.engine().observeOptionalLayer("calendar", false);
            fixture.engine().observeOptionalLayer("weather", false);
            fixture.engine().observeOptionalLayer("network", false);
            equal(before, fixture.occurrence().state());
            equal(scheduling, fixture.occurrence().schedulingObservation());
            equal(3, fixture.engine().optionalObservationCount());
        });

        test("optional service failure does not block local trigger", "HI-01,HI-02,HI-03,I-06", () -> {
            ArmedFixture fixture = armedFixture("alarm-optional-failure");
            fixture.engine().observeOptionalLayer("morning-intelligence", false);
            AlarmModel.TriggerResult result = fixture.engine().receiveTrigger(
                    fixture.occurrence().occurrenceId(), "callback", 1, BASE_T);
            equal(AlarmModel.TriggerDisposition.ACCEPTED, result.disposition());
            equal(AlarmModel.OutputDisposition.STARTED,
                    fixture.engine().recordSoftwareAudioStart(fixture.occurrence().occurrenceId(), 100L));
        });

        test("software start never infers physical audio or human awake", "I-08,I-14", () -> {
            ArmedFixture fixture = ringingFixture("alarm-evidence-chain");
            AlarmModel.EvidenceProjection evidence = fixture.engine().evidence(fixture.occurrence().occurrenceId());
            check(evidence.configured());
            check(evidence.triggered());
            check(evidence.softwareAudioStarted());
            check(!evidence.physicalAudioObserved());
            check(!evidence.humanAwake());
        });

        test("device-protected field set excludes personal data", "HI-06", () -> {
            for (String field : AlarmModel.fallbackWakePlanFields()) {
                equal(AlarmModel.StorageClass.DEVICE_PROTECTED, AlarmModel.storageClassFor(field));
            }
            equal(AlarmModel.StorageClass.CREDENTIAL_PROTECTED, AlarmModel.storageClassFor("name"));
            equal(AlarmModel.StorageClass.CREDENTIAL_PROTECTED, AlarmModel.storageClassFor("calendar"));
            equal(AlarmModel.StorageClass.CREDENTIAL_PROTECTED, AlarmModel.storageClassFor("location"));
            equal(AlarmModel.StorageClass.FORBIDDEN, AlarmModel.storageClassFor("unknown_field"));
        });

        test("structured event uses exact technical whitelist", "HI-06", () -> {
            StructuredEvent event = new StructuredEvent(
                    "event-1", "EVID-G1-0002", "alarm-synthetic", "occ-synthetic", 1,
                    "SOFTWARE_AUDIO_STARTED", 123L, 456L, null,
                    AlarmModel.ReadinessState.FULL, AlarmModel.SchedulingStrategy.ALARM_CLOCK, "PASS");
            String json = event.toJsonLine();
            Set<String> actualKeys = new HashSet<>();
            Matcher matcher = Pattern.compile("\\\"([a-z_]+)\\\":").matcher(json);
            while (matcher.find()) actualKeys.add(matcher.group(1));
            Set<String> expectedKeys = Set.of(
                    "event_id", "evidence_id", "alarm_id", "occurrence_id", "generation",
                    "event_type", "monotonic_timestamp_ms", "wall_clock_timestamp_ms",
                    "api_level", "readiness_state", "scheduling_strategy", "result");
            equal(expectedKeys, actualKeys);
            check(!json.contains("name"));
            check(!json.contains("calendar"));
            check(!json.contains("location"));
            check(!json.contains("reminder"));
        });

        test("event export appends valid separate records", "OBSERVABILITY", () -> {
            Path directory = Files.createTempDirectory("alvorada-e0-events-");
            Path log = directory.resolve("events.ndjson");
            try {
                StructuredEvent first = syntheticEvent("event-1", "TRIGGERED");
                StructuredEvent second = syntheticEvent("event-2", "SOFTWARE_AUDIO_STARTED");
                first.appendTo(log);
                second.appendTo(log);
                List<String> lines = Files.readAllLines(log, StandardCharsets.UTF_8);
                equal(2, lines.size());
                check(lines.get(0).contains("\"event_id\":\"event-1\""));
                check(lines.get(1).contains("\"event_id\":\"event-2\""));
            } finally {
                Files.deleteIfExists(log);
                Files.deleteIfExists(directory);
            }
        });

        test("audio marker is deterministic and structurally valid", "AUDIO-MARKER", () -> {
            byte[] first = AudioMarker.wavBytes();
            byte[] second = AudioMarker.wavBytes();
            check(Arrays.equals(first, second));
            equal(12_044, first.length);
            equal("RIFF", new String(first, 0, 4, StandardCharsets.US_ASCII));
            equal("WAVE", new String(first, 8, 4, StandardCharsets.US_ASCII));
            equal(AudioMarker.sha256(), AlarmModel.sha256Hex(first));
            equal("b523254e10e300f6e556a2081b2623a13c10ec05cf0a8230282535f49be62477",
                    AudioMarker.sha256());
        });

        test("scheduling strategies remain distinct experimental labels", "G1-STRATEGY", () -> {
            notEqual(AlarmModel.SchedulingStrategy.ALARM_CLOCK,
                    AlarmModel.SchedulingStrategy.EXACT_ALLOW_IDLE);
            equal("ALARM_CLOCK", AlarmModel.SchedulingStrategy.ALARM_CLOCK.name());
            equal("EXACT_ALLOW_IDLE", AlarmModel.SchedulingStrategy.EXACT_ALLOW_IDLE.name());
        });

        test("frozen threshold constants have not drifted", "HI-09,F-03-05,F-03-06,F-03-07,F-03-08,F-03-10", () -> {
            equal(-500L, AlarmModel.DELIVERY_EARLY_LIMIT_MS);
            equal(2_000L, AlarmModel.DELIVERY_TARGET_LIMIT_MS);
            equal(5_000L, AlarmModel.DELIVERY_ACCEPTABLE_LIMIT_MS);
            equal(1_000L, AlarmModel.AUDIO_TARGET_LIMIT_MS);
            equal(3_000L, AlarmModel.AUDIO_ACCEPTABLE_LIMIT_MS);
            equal(600_000L, AlarmModel.LATE_RECOVERY_LIMIT_MS);
            equal(300_000L, AlarmModel.SNOOZE_MS);
            equal(1_800_000L, AlarmModel.SESSION_LIMIT_MS);
        });

        test("engine-level invariants hold for representative terminal states", "I-01-I-14", () -> {
            ArmedFixture fixture = ringingFixture("alarm-invariant-scan");
            fixture.engine().verifyInternalInvariants();
            fixture.engine().dismiss(fixture.occurrence().occurrenceId());
            fixture.engine().verifyInternalInvariants();
        });
    }

    private void registerPropertyTests() {
        for (long seed : PROPERTY_SEEDS) {
            test("property sequence seed " + seed, "PROPERTY,I-01-I-14", () -> propertySequence(seed));
        }
    }

    private void propertySequence(long seed) {
        Random random = new Random(seed);
        long[] deltas = {-501L, -500L, -1L, 0L, 1L, 2_000L, 2_001L,
                5_000L, 5_001L, 599_999L, 600_000L, 600_001L};
        for (int sequence = 0; sequence < SEQUENCES_PER_SEED; sequence++) {
            String alarmId = "p-" + seed + "-" + sequence;
            AlarmModel.Engine engine = new AlarmModel.Engine();
            engine.configure(alarmId, LocalTime.of(7, 30), ZoneId.of("UTC"));
            LocalDate date = BASE_DATE.plusDays(sequence % 28);
            AlarmModel.Occurrence occurrence = engine.materialize(alarmId, date, "boot-property");
            String expectedId = AlarmModel.occurrenceId(alarmId, 1, date, LocalTime.of(7, 30), 0, null);
            equal(expectedId, occurrence.occurrenceId());
            equal(occurrence.occurrenceId(), engine.materialize(alarmId, date, "boot-property").occurrenceId());

            if (random.nextInt(8) == 0) {
                engine.editZone(alarmId, ZoneId.of(random.nextBoolean() ? "Europe/Lisbon" : "Asia/Tokyo"));
                AlarmModel.TriggerResult old = engine.receiveTrigger(
                        occurrence.occurrenceId(), "old", 1, occurrence.scheduledInstant());
                equal(AlarmModel.TriggerDisposition.STALE_GENERATION, old.disposition());
                check(occurrence.tombstone());
            } else {
                arm(engine, occurrence, "boot-property");
                long delta = deltas[random.nextInt(deltas.length)];
                Instant received = occurrence.scheduledInstant().plusMillis(delta);
                AlarmModel.TriggerResult first = engine.receiveTrigger(
                        occurrence.occurrenceId(), "callback", 1, received);
                equal(AlarmModel.classifyDeliveryDelta(delta), first.deliveryBand());
                equal(AlarmModel.TriggerDisposition.DUPLICATE_SUPPRESSED,
                        engine.receiveTrigger(occurrence.occurrenceId(), "callback", 1, received).disposition());
                if (delta <= AlarmModel.LATE_RECOVERY_LIMIT_MS) {
                    equal(AlarmModel.TriggerDisposition.ACCEPTED, first.disposition());
                    AlarmModel.OutputDisposition audio = engine.recordSoftwareAudioStart(
                            occurrence.occurrenceId(), 10_000L + sequence);
                    equal(AlarmModel.OutputDisposition.STARTED, audio);
                    if (random.nextBoolean()) {
                        engine.dismiss(occurrence.occurrenceId());
                        check(occurrence.tombstone());
                        equal(AlarmModel.OccurrenceState.DISMISSED, occurrence.state());
                    } else {
                        AlarmModel.SnoozeResult snooze = engine.requestSnooze(
                                occurrence.occurrenceId(), received, 10_000L + sequence, "boot-property");
                        AlarmModel.SnoozeResult duplicate = engine.requestSnooze(
                                occurrence.occurrenceId(), received.plusMillis(1), 10_001L + sequence,
                                "boot-property");
                        equal(snooze.childOccurrenceId(), duplicate.childOccurrenceId());
                        engine.confirmSnooze(occurrence.occurrenceId(), checkpoint(1, "boot-property"));
                        equal(AlarmModel.OccurrenceState.SNOOZED, occurrence.state());
                    }
                } else {
                    equal(AlarmModel.TriggerDisposition.TOO_LATE, first.disposition());
                    equal(AlarmModel.OccurrenceState.MISSED, occurrence.state());
                }
            }

            String reconciliationId = "reconcile-" + sequence;
            check(engine.receiveReconciliationEvent(reconciliationId, "APP_STARTUP"));
            check(!engine.receiveReconciliationEvent(reconciliationId, "APP_STARTUP"));
            engine.completeReconciliation(reconciliationId, AlarmModel.ReconciliationResult.NOOP);
            engine.verifyInternalInvariants();
        }
    }

    private AlarmModel.Engine baseEngine(String alarmId) {
        AlarmModel.Engine engine = new AlarmModel.Engine();
        engine.configure(alarmId, LocalTime.of(7, 30), ZoneId.of("UTC"));
        return engine;
    }

    private ArmedFixture configuredFixture(String alarmId) {
        AlarmModel.Engine engine = baseEngine(alarmId);
        return new ArmedFixture(engine, engine.materialize(alarmId, BASE_DATE, BOOT));
    }

    private ArmedFixture armedFixture(String alarmId) {
        ArmedFixture fixture = configuredFixture(alarmId);
        arm(fixture.engine(), fixture.occurrence());
        return fixture;
    }

    private ArmedFixture ringingFixture(String alarmId) {
        ArmedFixture fixture = armedFixture(alarmId);
        fixture.engine().receiveTrigger(fixture.occurrence().occurrenceId(), "callback", 1, BASE_T);
        fixture.engine().recordSoftwareAudioStart(fixture.occurrence().occurrenceId(), 10_000L);
        return fixture;
    }

    private void arm(AlarmModel.Engine engine, AlarmModel.Occurrence occurrence) {
        arm(engine, occurrence, BOOT);
    }

    private void arm(AlarmModel.Engine engine, AlarmModel.Occurrence occurrence, String bootId) {
        engine.requireReadiness(occurrence.occurrenceId());
        engine.markArmable(occurrence.occurrenceId());
        engine.requestScheduling(occurrence.occurrenceId());
        engine.acknowledgeScheduling(occurrence.occurrenceId(), checkpoint(occurrence.generation(), bootId));
    }

    private AlarmModel.ReadinessCheckpoint checkpoint(long generation, String bootId) {
        return new AlarmModel.ReadinessCheckpoint(
                bootId, BUILD, CELL, generation, BASE_T.toEpochMilli(), 1_000L,
                AlarmModel.ReadinessState.FULL, AlarmModel.SchedulingStrategy.ALARM_CLOCK);
    }

    private TwoAlarmFixture twoArmedAlarms() {
        AlarmModel.Engine engine = new AlarmModel.Engine();
        engine.configure("alarm-a", LocalTime.of(7, 30), ZoneId.of("UTC"));
        engine.configure("alarm-b", LocalTime.of(7, 30, 1), ZoneId.of("UTC"));
        AlarmModel.Occurrence first = engine.materialize("alarm-a", BASE_DATE, BOOT);
        AlarmModel.Occurrence second = engine.materialize("alarm-b", BASE_DATE, BOOT);
        arm(engine, first);
        arm(engine, second);
        return new TwoAlarmFixture(engine, first, second);
    }

    private StructuredEvent syntheticEvent(String eventId, String eventType) {
        return new StructuredEvent(
                eventId, "EVID-G1-0002", "alarm-synthetic", "occ-synthetic", 1,
                eventType, 100L, BASE_T.toEpochMilli(), null,
                AlarmModel.ReadinessState.FULL,
                AlarmModel.SchedulingStrategy.ALARM_CLOCK, "PASS");
    }

    private void test(String name, String coverage, ThrowingRunnable body) {
        long beforeAssertions = assertions;
        long started = System.nanoTime();
        try {
            body.run();
            long durationMicros = (System.nanoTime() - started) / 1_000L;
            results.add(new TestResult(name, coverage, true, assertions - beforeAssertions,
                    durationMicros, null));
        } catch (Throwable failure) {
            long durationMicros = (System.nanoTime() - started) / 1_000L;
            results.add(new TestResult(name, coverage, false, assertions - beforeAssertions,
                    durationMicros, failure.toString()));
            System.err.println("FAIL " + name + ": " + failure);
            failure.printStackTrace(System.err);
        }
    }

    private void check(boolean condition) {
        assertions++;
        if (!condition) throw new AssertionError("condition was false");
    }

    private void equal(Object expected, Object actual) {
        assertions++;
        if (!java.util.Objects.equals(expected, actual)) {
            throw new AssertionError("expected <" + expected + "> but was <" + actual + ">");
        }
    }

    private void notEqual(Object first, Object second) {
        assertions++;
        if (java.util.Objects.equals(first, second)) {
            throw new AssertionError("values unexpectedly equal: " + first);
        }
    }

    private <T extends Throwable> void expectThrows(Class<T> type, ThrowingRunnable body) throws Exception {
        assertions++;
        try {
            body.run();
        } catch (Throwable failure) {
            if (type.isInstance(failure)) return;
            throw new AssertionError("expected " + type.getName() + " but saw " + failure, failure);
        }
        throw new AssertionError("expected " + type.getName() + " but no exception was thrown");
    }

    private void report(String suite, long durationMillis) {
        long passed = results.stream().filter(TestResult::passed).count();
        List<TestResult> failures = results.stream().filter(result -> !result.passed()).toList();
        long sequenceCount = suite.equals("deterministic") ? 0L
                : (long) PROPERTY_SEEDS.length * SEQUENCES_PER_SEED;
        StringBuilder json = new StringBuilder();
        json.append('{')
                .append("\"schema_version\":1,")
                .append("\"harness_version\":\"").append(AlarmModel.HARNESS_VERSION).append("\",")
                .append("\"suite\":\"").append(suite).append("\",")
                .append("\"result\":\"").append(failures.isEmpty() ? "PASS" : "FAIL").append("\",")
                .append("\"tests\":").append(results.size()).append(',')
                .append("\"passed\":").append(passed).append(',')
                .append("\"failed\":").append(failures.size()).append(',')
                .append("\"assertions\":").append(assertions).append(',')
                .append("\"property_seeds\":").append(longArrayJson(PROPERTY_SEEDS)).append(',')
                .append("\"sequences_per_seed\":").append(suite.equals("deterministic") ? 0 : SEQUENCES_PER_SEED).append(',')
                .append("\"property_sequence_count\":").append(sequenceCount).append(',')
                .append("\"duration_ms\":").append(durationMillis).append(',')
                .append("\"audio_marker_sha256\":\"").append(AudioMarker.sha256()).append("\",")
                .append("\"failure_names\":[");
        for (int index = 0; index < failures.size(); index++) {
            if (index > 0) json.append(',');
            json.append('\"').append(jsonEscape(failures.get(index).name())).append('\"');
        }
        json.append("]}");
        System.out.println("E0_SUMMARY=" + json);
        if (!failures.isEmpty()) System.exit(1);
    }

    private static String longArrayJson(long[] values) {
        StringBuilder json = new StringBuilder("[");
        for (int index = 0; index < values.length; index++) {
            if (index > 0) json.append(',');
            json.append(values[index]);
        }
        return json.append(']').toString();
    }

    private static String jsonEscape(String value) {
        return value.replace("\\", "\\\\").replace("\"", "\\\"");
    }

    @FunctionalInterface
    private interface ThrowingRunnable { void run() throws Exception; }
    private record TestResult(String name, String coverage, boolean passed, long assertions,
                              long durationMicros, String failure) {}
    private record ArmedFixture(AlarmModel.Engine engine, AlarmModel.Occurrence occurrence) {}
    private record TwoAlarmFixture(AlarmModel.Engine engine, AlarmModel.Occurrence first,
                                   AlarmModel.Occurrence second) {}
}
