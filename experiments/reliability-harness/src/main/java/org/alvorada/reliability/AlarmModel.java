package org.alvorada.reliability;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Duration;
import java.time.Instant;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.LocalTime;
import java.time.ZoneId;
import java.time.ZoneOffset;
import java.time.zone.ZoneOffsetTransition;
import java.time.zone.ZoneRules;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.EnumSet;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;

/** Pure-JVM executable model of the G1.1 alarm semantics. */
public final class AlarmModel {
    public static final String HARNESS_VERSION = "0.1.0";
    public static final long DELIVERY_EARLY_LIMIT_MS = -500L;
    public static final long DELIVERY_TARGET_LIMIT_MS = 2_000L;
    public static final long DELIVERY_ACCEPTABLE_LIMIT_MS = 5_000L;
    public static final long AUDIO_TARGET_LIMIT_MS = 1_000L;
    public static final long AUDIO_ACCEPTABLE_LIMIT_MS = 3_000L;
    public static final long LATE_RECOVERY_LIMIT_MS = Duration.ofMinutes(10).toMillis();
    public static final long SNOOZE_MS = Duration.ofMinutes(5).toMillis();
    public static final long SESSION_LIMIT_MS = Duration.ofMinutes(30).toMillis();

    private AlarmModel() {}

    public enum IntentStatus { ENABLED, DISABLED }

    public enum SchedulingObservation {
        UNKNOWN, REQUESTING, REGISTERED, BLOCKED, INVALIDATED, CONSUMED
    }

    public enum OccurrenceState {
        CONFIGURED,
        READINESS_CHECK_REQUIRED,
        ARMABLE,
        ARMING,
        ARMED_VERIFIED,
        READINESS_STALE,
        BLOCKED,
        INVALIDATED,
        TRIGGERING,
        OUTPUT_WAITING,
        RINGING,
        SNOOZE_PENDING,
        SNOOZED,
        DISMISSED,
        DISABLED,
        INTERRUPTED,
        RECOVERY_REQUIRED,
        RECOVERED_LATE,
        MISSED,
        OUTCOME_UNKNOWN,
        UNANSWERED
    }

    public enum ReadinessState { UNASSESSED, CHECKING, FULL, LIMITED, BLOCKED, UNKNOWN, STALE }
    public enum DeliveryBand { EARLY_TOLERANCE, TARGET, ACCEPTABLE_LATE, FAILURE }
    public enum AudioBand { TARGET, ACCEPTABLE, FAILURE, UNKNOWN }
    public enum RecoveryDecision { NOT_DUE, RECOVER_NOW, MISSED, OUTCOME_UNKNOWN, SKIP_TERMINAL }
    public enum ReconciliationResult { PENDING, RECONCILED, NOOP, BLOCKED, PARTIAL, FAILED, UNKNOWN }
    public enum TriggerDisposition { ACCEPTED, DUPLICATE_SUPPRESSED, STALE_GENERATION, TOMBSTONED, TERMINAL, INVALID_STATE, TOO_LATE, UNKNOWN_OCCURRENCE }
    public enum OutputDisposition { STARTED, WAITING, DUPLICATE_SUPPRESSED, REJECTED }
    public enum SchedulingStrategy { ALARM_CLOCK, EXACT_ALLOW_IDLE }
    public enum ScheduleCrashPoint { AFTER_INTENT_PERSISTED, AFTER_SCHEDULING_ACCEPTED, AFTER_CHECKPOINT_PERSISTED }
    public enum StorageClass { DEVICE_PROTECTED, CREDENTIAL_PROTECTED, FORBIDDEN }
    public enum ClockDomain { WALL_CLOCK, MONOTONIC }

    public record AlarmIntent(
            String alarmId,
            long generation,
            IntentStatus status,
            LocalTime localTime,
            ZoneId zoneId) {
        public AlarmIntent {
            requireText(alarmId, "alarmId");
            if (generation < 1) throw new IllegalArgumentException("generation must be >= 1");
            Objects.requireNonNull(status, "status");
            Objects.requireNonNull(localTime, "localTime");
            Objects.requireNonNull(zoneId, "zoneId");
        }

        AlarmIntent withGenerationAndZone(long nextGeneration, ZoneId nextZone) {
            return new AlarmIntent(alarmId, nextGeneration, status, localTime, nextZone);
        }

        AlarmIntent disabledAt(long nextGeneration) {
            return new AlarmIntent(alarmId, nextGeneration, IntentStatus.DISABLED, localTime, zoneId);
        }
    }

    public record CivilResolution(
            LocalDate requestedDate,
            LocalTime requestedTime,
            ZoneId zoneId,
            LocalDateTime resolvedLocal,
            ZoneOffset selectedOffset,
            Instant instant,
            String dstAdjustment,
            int foldOrdinal) {}

    public record ReadinessCheckpoint(
            String bootId,
            String buildId,
            String cellId,
            long generation,
            long wallClockMillis,
            long monotonicMillis,
            ReadinessState readinessState,
            SchedulingStrategy strategy) {
        public ReadinessCheckpoint {
            requireText(bootId, "bootId");
            requireText(buildId, "buildId");
            requireText(cellId, "cellId");
            Objects.requireNonNull(readinessState, "readinessState");
            Objects.requireNonNull(strategy, "strategy");
        }

        public boolean isCurrentFor(String boot, String build, String cell, long gen) {
            return generation == gen
                    && bootId.equals(boot)
                    && buildId.equals(build)
                    && cellId.equals(cell)
                    && readinessState == ReadinessState.FULL;
        }
    }

    public record TriggerResult(TriggerDisposition disposition, DeliveryBand deliveryBand) {}
    public record SnoozeResult(String childOccurrenceId, boolean created) {}
    public record ReconciliationRecord(String eventId, String eventType, ReconciliationResult result) {}
    public record ScheduleCrashObservation(
            ScheduleCrashPoint point,
            SchedulingObservation schedulingObservation,
            OccurrenceState occurrenceState,
            boolean armedVerifiedClaimAllowed) {}

    public record EvidenceProjection(
            boolean configured,
            boolean armedVerified,
            boolean triggered,
            boolean softwareAudioStarted,
            boolean physicalAudioObserved,
            boolean humanAwake) {}

    public static final class Occurrence {
        private final String occurrenceId;
        private final String alarmId;
        private final long generation;
        private final LocalDate civilDate;
        private final LocalTime civilTime;
        private final ZoneId zoneId;
        private final Instant scheduledInstant;
        private final ZoneOffset selectedOffset;
        private final String parentOccurrenceId;
        private final long snoozeDeadlineMonotonicMillis;
        private final String originatingBootId;
        private OccurrenceState state;
        private SchedulingObservation schedulingObservation;
        private boolean tombstone;
        private ReadinessCheckpoint checkpoint;
        private Long triggerWallMillis;
        private Long softwareAudioMonotonicMillis;
        private boolean physicalAudioObserved;
        private boolean humanAwake;

        private Occurrence(
                String occurrenceId,
                String alarmId,
                long generation,
                LocalDate civilDate,
                LocalTime civilTime,
                ZoneId zoneId,
                Instant scheduledInstant,
                ZoneOffset selectedOffset,
                String parentOccurrenceId,
                long snoozeDeadlineMonotonicMillis,
                String originatingBootId,
                OccurrenceState state,
                SchedulingObservation schedulingObservation,
                boolean tombstone,
                ReadinessCheckpoint checkpoint,
                Long triggerWallMillis,
                Long softwareAudioMonotonicMillis,
                boolean physicalAudioObserved,
                boolean humanAwake) {
            this.occurrenceId = requireText(occurrenceId, "occurrenceId");
            this.alarmId = requireText(alarmId, "alarmId");
            this.generation = generation;
            this.civilDate = Objects.requireNonNull(civilDate, "civilDate");
            this.civilTime = Objects.requireNonNull(civilTime, "civilTime");
            this.zoneId = Objects.requireNonNull(zoneId, "zoneId");
            this.scheduledInstant = Objects.requireNonNull(scheduledInstant, "scheduledInstant");
            this.selectedOffset = Objects.requireNonNull(selectedOffset, "selectedOffset");
            this.parentOccurrenceId = parentOccurrenceId;
            this.snoozeDeadlineMonotonicMillis = snoozeDeadlineMonotonicMillis;
            this.originatingBootId = requireText(originatingBootId, "originatingBootId");
            this.state = Objects.requireNonNull(state, "state");
            this.schedulingObservation = Objects.requireNonNull(schedulingObservation, "schedulingObservation");
            this.tombstone = tombstone;
            this.checkpoint = checkpoint;
            this.triggerWallMillis = triggerWallMillis;
            this.softwareAudioMonotonicMillis = softwareAudioMonotonicMillis;
            this.physicalAudioObserved = physicalAudioObserved;
            this.humanAwake = humanAwake;
        }

        private static Occurrence materialized(
                AlarmIntent intent, CivilResolution resolution, String bootId) {
            String id = AlarmModel.occurrenceId(
                    intent.alarmId(), intent.generation(), resolution.requestedDate(),
                    intent.localTime(), resolution.foldOrdinal(), null);
            return new Occurrence(
                    id, intent.alarmId(), intent.generation(), resolution.requestedDate(),
                    intent.localTime(), intent.zoneId(), resolution.instant(),
                    resolution.selectedOffset(), null, -1L, bootId,
                    OccurrenceState.CONFIGURED, SchedulingObservation.UNKNOWN,
                    false, null, null, null, false, false);
        }

        private Occurrence copy() {
            return new Occurrence(
                    occurrenceId, alarmId, generation, civilDate, civilTime, zoneId,
                    scheduledInstant, selectedOffset, parentOccurrenceId,
                    snoozeDeadlineMonotonicMillis, originatingBootId, state,
                    schedulingObservation, tombstone, checkpoint, triggerWallMillis,
                    softwareAudioMonotonicMillis, physicalAudioObserved, humanAwake);
        }

        public String occurrenceId() { return occurrenceId; }
        public String alarmId() { return alarmId; }
        public long generation() { return generation; }
        public LocalDate civilDate() { return civilDate; }
        public LocalTime civilTime() { return civilTime; }
        public ZoneId zoneId() { return zoneId; }
        public Instant scheduledInstant() { return scheduledInstant; }
        public ZoneOffset selectedOffset() { return selectedOffset; }
        public String parentOccurrenceId() { return parentOccurrenceId; }
        public long snoozeDeadlineMonotonicMillis() { return snoozeDeadlineMonotonicMillis; }
        public String originatingBootId() { return originatingBootId; }
        public OccurrenceState state() { return state; }
        public SchedulingObservation schedulingObservation() { return schedulingObservation; }
        public boolean tombstone() { return tombstone; }
        public ReadinessCheckpoint checkpoint() { return checkpoint; }
        public Long triggerWallMillis() { return triggerWallMillis; }
        public Long softwareAudioMonotonicMillis() { return softwareAudioMonotonicMillis; }
        public boolean physicalAudioObserved() { return physicalAudioObserved; }
        public boolean humanAwake() { return humanAwake; }

        private boolean semanticallyEquals(Occurrence other) {
            return alarmId.equals(other.alarmId)
                    && generation == other.generation
                    && civilDate.equals(other.civilDate)
                    && civilTime.equals(other.civilTime)
                    && zoneId.equals(other.zoneId)
                    && scheduledInstant.equals(other.scheduledInstant)
                    && Objects.equals(parentOccurrenceId, other.parentOccurrenceId);
        }
    }

    public record OccurrenceSnapshot(
            String occurrenceId,
            String alarmId,
            long generation,
            LocalDate civilDate,
            LocalTime civilTime,
            ZoneId zoneId,
            Instant scheduledInstant,
            ZoneOffset selectedOffset,
            String parentOccurrenceId,
            long snoozeDeadlineMonotonicMillis,
            String originatingBootId,
            OccurrenceState state,
            SchedulingObservation schedulingObservation,
            boolean tombstone,
            ReadinessCheckpoint checkpoint,
            Long triggerWallMillis,
            Long softwareAudioMonotonicMillis,
            boolean physicalAudioObserved,
            boolean humanAwake) {}

    public record EngineSnapshot(
            Map<String, AlarmIntent> intents,
            Map<String, OccurrenceSnapshot> occurrences,
            Set<String> triggerTokens,
            Map<String, String> snoozeChildren,
            Map<String, ReconciliationRecord> reconciliations,
            String outputOwner) {}

    public static final class Engine {
        private final Map<String, AlarmIntent> intents = new LinkedHashMap<>();
        private final Map<String, Occurrence> occurrences = new LinkedHashMap<>();
        private final Set<String> triggerTokens = new HashSet<>();
        private final Map<String, String> snoozeChildren = new HashMap<>();
        private final Map<String, ReconciliationRecord> reconciliations = new LinkedHashMap<>();
        private final List<String> optionalLayerObservations = new ArrayList<>();
        private String outputOwner;

        public AlarmIntent configure(String alarmId, LocalTime localTime, ZoneId zoneId) {
            if (intents.containsKey(alarmId)) {
                throw new IllegalStateException("alarm already exists; edit explicitly");
            }
            AlarmIntent intent = new AlarmIntent(alarmId, 1L, IntentStatus.ENABLED, localTime, zoneId);
            intents.put(alarmId, intent);
            return intent;
        }

        public AlarmIntent editZone(String alarmId, ZoneId newZone) {
            AlarmIntent current = requireIntent(alarmId);
            AlarmIntent edited = current.withGenerationAndZone(current.generation() + 1L, newZone);
            intents.put(alarmId, edited);
            invalidateOldGenerations(alarmId, edited.generation());
            return edited;
        }

        public AlarmIntent disable(String alarmId) {
            AlarmIntent current = requireIntent(alarmId);
            AlarmIntent disabled = current.disabledAt(current.generation() + 1L);
            intents.put(alarmId, disabled);
            for (Occurrence occurrence : occurrences.values()) {
                if (occurrence.alarmId.equals(alarmId) && !isTerminal(occurrence.state)) {
                    occurrence.tombstone = true;
                    occurrence.schedulingObservation = SchedulingObservation.INVALIDATED;
                    transition(occurrence, OccurrenceState.DISABLED);
                    releaseOutput(occurrence.occurrenceId);
                }
            }
            return disabled;
        }

        public Occurrence materialize(String alarmId, LocalDate civilDate, String bootId) {
            AlarmIntent intent = requireIntent(alarmId);
            if (intent.status() != IntentStatus.ENABLED) {
                throw new IllegalStateException("disabled intent cannot materialize");
            }
            CivilResolution resolution = resolveCivil(civilDate, intent.localTime(), intent.zoneId());
            Occurrence candidate = Occurrence.materialized(intent, resolution, bootId);
            Occurrence existing = occurrences.get(candidate.occurrenceId);
            if (existing != null) {
                if (!existing.semanticallyEquals(candidate)) {
                    throw new IllegalStateException("occurrence ID collision with different semantics");
                }
                return existing;
            }
            occurrences.put(candidate.occurrenceId, candidate);
            return candidate;
        }

        /** Test/import boundary that fails closed on an adversarial duplicate ID. */
        public void importOccurrence(OccurrenceSnapshot snapshot) {
            Occurrence candidate = fromSnapshot(snapshot);
            Occurrence existing = occurrences.get(candidate.occurrenceId);
            if (existing != null && !existing.semanticallyEquals(candidate)) {
                throw new IllegalStateException("occurrence ID collision with different semantics");
            }
            occurrences.putIfAbsent(candidate.occurrenceId, candidate);
        }

        public void requireReadiness(String occurrenceId) {
            transition(requireOccurrence(occurrenceId), OccurrenceState.READINESS_CHECK_REQUIRED);
        }

        public void markArmable(String occurrenceId) {
            transition(requireOccurrence(occurrenceId), OccurrenceState.ARMABLE);
        }

        public void requestScheduling(String occurrenceId) {
            Occurrence occurrence = requireOccurrence(occurrenceId);
            transition(occurrence, OccurrenceState.ARMING);
            occurrence.schedulingObservation = SchedulingObservation.REQUESTING;
        }

        public void acknowledgeScheduling(String occurrenceId, ReadinessCheckpoint checkpoint) {
            Occurrence occurrence = requireOccurrence(occurrenceId);
            if (occurrence.state != OccurrenceState.ARMING) {
                throw new IllegalStateException("scheduling ACK requires ARMING");
            }
            if (!checkpoint.isCurrentFor(
                    occurrence.originatingBootId, checkpoint.buildId(), checkpoint.cellId(), occurrence.generation)) {
                occurrence.schedulingObservation = SchedulingObservation.BLOCKED;
                transition(occurrence, OccurrenceState.RECOVERY_REQUIRED);
                throw new IllegalArgumentException("checkpoint does not match occurrence");
            }
            occurrence.checkpoint = checkpoint;
            occurrence.schedulingObservation = SchedulingObservation.REGISTERED;
            transition(occurrence, OccurrenceState.ARMED_VERIFIED);
        }

        public ScheduleCrashObservation simulateSchedulingCrash(
                String occurrenceId, ScheduleCrashPoint point, ReadinessCheckpoint checkpoint) {
            Occurrence occurrence = requireOccurrence(occurrenceId);
            return switch (point) {
                case AFTER_INTENT_PERSISTED -> new ScheduleCrashObservation(
                        point, occurrence.schedulingObservation, occurrence.state, false);
                case AFTER_SCHEDULING_ACCEPTED -> {
                    occurrence.schedulingObservation = SchedulingObservation.REGISTERED;
                    if (!isTerminal(occurrence.state)) occurrence.state = OccurrenceState.RECOVERY_REQUIRED;
                    yield new ScheduleCrashObservation(point, occurrence.schedulingObservation, occurrence.state, false);
                }
                case AFTER_CHECKPOINT_PERSISTED -> {
                    if (occurrence.state != OccurrenceState.ARMING) {
                        throw new IllegalStateException("checkpoint crash fixture requires ARMING");
                    }
                    occurrence.checkpoint = checkpoint;
                    occurrence.schedulingObservation = SchedulingObservation.REGISTERED;
                    transition(occurrence, OccurrenceState.ARMED_VERIFIED);
                    yield new ScheduleCrashObservation(point, occurrence.schedulingObservation, occurrence.state, true);
                }
            };
        }

        public void markReadinessStale(String occurrenceId, String reason) {
            requireText(reason, "reason");
            Occurrence occurrence = requireOccurrence(occurrenceId);
            if (isTerminal(occurrence.state)) return;
            occurrence.schedulingObservation = SchedulingObservation.INVALIDATED;
            transition(occurrence, OccurrenceState.READINESS_STALE);
        }

        public TriggerResult receiveTrigger(
                String occurrenceId, String callbackToken, long callbackGeneration, Instant receivedAt) {
            requireText(callbackToken, "callbackToken");
            Objects.requireNonNull(receivedAt, "receivedAt");
            String token = occurrenceId + "\u001f" + callbackToken;
            if (!triggerTokens.add(token)) {
                return new TriggerResult(TriggerDisposition.DUPLICATE_SUPPRESSED, null);
            }
            Occurrence occurrence = occurrences.get(occurrenceId);
            if (occurrence == null) {
                return new TriggerResult(TriggerDisposition.UNKNOWN_OCCURRENCE, null);
            }
            AlarmIntent intent = intents.get(occurrence.alarmId);
            if (intent == null || intent.status() != IntentStatus.ENABLED
                    || callbackGeneration != intent.generation()
                    || callbackGeneration != occurrence.generation) {
                return new TriggerResult(TriggerDisposition.STALE_GENERATION, null);
            }
            if (occurrence.tombstone) {
                return new TriggerResult(TriggerDisposition.TOMBSTONED, null);
            }
            if (isTerminal(occurrence.state)) {
                return new TriggerResult(TriggerDisposition.TERMINAL, null);
            }
            if (!EnumSet.of(
                    OccurrenceState.ARMED_VERIFIED,
                    OccurrenceState.READINESS_STALE,
                    OccurrenceState.BLOCKED,
                    OccurrenceState.RECOVERY_REQUIRED).contains(occurrence.state)) {
                return new TriggerResult(TriggerDisposition.INVALID_STATE, null);
            }
            long delta = receivedAt.toEpochMilli() - occurrence.scheduledInstant.toEpochMilli();
            DeliveryBand band = classifyDeliveryDelta(delta);
            if (delta > LATE_RECOVERY_LIMIT_MS) {
                transition(occurrence, OccurrenceState.MISSED);
                return new TriggerResult(TriggerDisposition.TOO_LATE, band);
            }
            occurrence.triggerWallMillis = receivedAt.toEpochMilli();
            occurrence.schedulingObservation = SchedulingObservation.CONSUMED;
            transition(occurrence, delta > DELIVERY_ACCEPTABLE_LIMIT_MS
                    ? OccurrenceState.RECOVERED_LATE
                    : OccurrenceState.TRIGGERING);
            return new TriggerResult(TriggerDisposition.ACCEPTED, band);
        }

        public OutputDisposition recordSoftwareAudioStart(String occurrenceId, long monotonicMillis) {
            Occurrence occurrence = requireOccurrence(occurrenceId);
            if (occurrence.softwareAudioMonotonicMillis != null) {
                return OutputDisposition.DUPLICATE_SUPPRESSED;
            }
            if (!EnumSet.of(OccurrenceState.TRIGGERING, OccurrenceState.RECOVERED_LATE).contains(occurrence.state)) {
                return OutputDisposition.REJECTED;
            }
            if (outputOwner != null && !outputOwner.equals(occurrenceId)) {
                transition(occurrence, OccurrenceState.OUTPUT_WAITING);
                return OutputDisposition.WAITING;
            }
            outputOwner = occurrenceId;
            occurrence.softwareAudioMonotonicMillis = monotonicMillis;
            transition(occurrence, OccurrenceState.RINGING);
            return OutputDisposition.STARTED;
        }

        public OutputDisposition promoteWaiting(String occurrenceId, long monotonicMillis) {
            Occurrence occurrence = requireOccurrence(occurrenceId);
            if (occurrence.state != OccurrenceState.OUTPUT_WAITING || outputOwner != null) {
                return OutputDisposition.REJECTED;
            }
            outputOwner = occurrenceId;
            occurrence.softwareAudioMonotonicMillis = monotonicMillis;
            transition(occurrence, OccurrenceState.RINGING);
            return OutputDisposition.STARTED;
        }

        public boolean dismiss(String occurrenceId) {
            Occurrence occurrence = requireOccurrence(occurrenceId);
            if (occurrence.state == OccurrenceState.DISMISSED && occurrence.tombstone) return false;
            if (isTerminal(occurrence.state)) return false;
            occurrence.tombstone = true;
            transition(occurrence, OccurrenceState.DISMISSED);
            releaseOutput(occurrenceId);
            return true;
        }

        public SnoozeResult requestSnooze(
                String parentOccurrenceId,
                Instant requestedAtWall,
                long requestedAtMonotonic,
                String currentBootId) {
            Occurrence parent = requireOccurrence(parentOccurrenceId);
            String existingId = snoozeChildren.get(parentOccurrenceId);
            if (existingId != null) return new SnoozeResult(existingId, false);
            if (parent.state != OccurrenceState.RINGING) {
                throw new IllegalStateException("snooze requires RINGING parent");
            }
            Instant childInstant = requestedAtWall.plusMillis(SNOOZE_MS);
            LocalDateTime local = LocalDateTime.ofInstant(childInstant, parent.zoneId);
            ZoneOffset offset = parent.zoneId.getRules().getOffset(childInstant);
            String childId = snoozeOccurrenceId(parentOccurrenceId, parent.generation, childInstant);
            Occurrence child = new Occurrence(
                    childId, parent.alarmId, parent.generation, local.toLocalDate(),
                    local.toLocalTime(), parent.zoneId, childInstant, offset,
                    parentOccurrenceId, requestedAtMonotonic + SNOOZE_MS,
                    currentBootId, OccurrenceState.CONFIGURED,
                    SchedulingObservation.UNKNOWN, false, null, null, null, false, false);
            occurrences.put(childId, child);
            snoozeChildren.put(parentOccurrenceId, childId);
            transition(parent, OccurrenceState.SNOOZE_PENDING);
            return new SnoozeResult(childId, true);
        }

        public void confirmSnooze(String parentOccurrenceId, ReadinessCheckpoint childCheckpoint) {
            Occurrence parent = requireOccurrence(parentOccurrenceId);
            String childId = snoozeChildren.get(parentOccurrenceId);
            if (childId == null) throw new IllegalStateException("snooze child missing");
            Occurrence child = requireOccurrence(childId);
            if (child.state == OccurrenceState.CONFIGURED) requireReadiness(childId);
            if (child.state == OccurrenceState.READINESS_CHECK_REQUIRED) markArmable(childId);
            if (child.state == OccurrenceState.ARMABLE) requestScheduling(childId);
            if (child.state == OccurrenceState.ARMING) acknowledgeScheduling(childId, childCheckpoint);
            if (parent.state == OccurrenceState.SNOOZE_PENDING) {
                transition(parent, OccurrenceState.SNOOZED);
                parent.tombstone = true;
                releaseOutput(parentOccurrenceId);
            }
        }

        public boolean applySessionTimeout(String occurrenceId, long nowMonotonicMillis) {
            Occurrence occurrence = requireOccurrence(occurrenceId);
            if (occurrence.state != OccurrenceState.RINGING
                    || occurrence.softwareAudioMonotonicMillis == null) return false;
            if (nowMonotonicMillis - occurrence.softwareAudioMonotonicMillis < SESSION_LIMIT_MS) return false;
            transition(occurrence, OccurrenceState.UNANSWERED);
            releaseOutput(occurrenceId);
            return true;
        }

        public RecoveryDecision reconcileLate(
                String occurrenceId, Instant now, boolean deliveryFailureConfirmed,
                String eventId, String eventType) {
            Occurrence occurrence = requireOccurrence(occurrenceId);
            ReconciliationRecord existing = reconciliations.get(eventId);
            if (existing != null) {
                if (!existing.eventType().equals(eventType)) {
                    throw new IllegalStateException("reconciliation event ID collision");
                }
                if (existing.result() != ReconciliationResult.PENDING) {
                    return stateToRecoveryDecision(occurrence.state);
                }
            }
            receiveReconciliationEvent(eventId, eventType);
            RecoveryDecision decision = lateRecoveryDecision(
                    occurrence.scheduledInstant, now, isTerminal(occurrence.state) || occurrence.tombstone,
                    deliveryFailureConfirmed);
            switch (decision) {
                case RECOVER_NOW -> {
                    if (occurrence.state != OccurrenceState.RECOVERED_LATE) {
                        occurrence.state = OccurrenceState.RECOVERED_LATE;
                    }
                    completeReconciliation(eventId, ReconciliationResult.RECONCILED);
                }
                case MISSED -> {
                    if (!isTerminal(occurrence.state)) occurrence.state = OccurrenceState.MISSED;
                    completeReconciliation(eventId, ReconciliationResult.RECONCILED);
                }
                case OUTCOME_UNKNOWN -> {
                    if (!isTerminal(occurrence.state)) occurrence.state = OccurrenceState.OUTCOME_UNKNOWN;
                    completeReconciliation(eventId, ReconciliationResult.UNKNOWN);
                }
                case SKIP_TERMINAL, NOT_DUE -> completeReconciliation(eventId, ReconciliationResult.NOOP);
            }
            return decision;
        }

        public boolean receiveReconciliationEvent(String eventId, String eventType) {
            requireText(eventId, "eventId");
            requireText(eventType, "eventType");
            ReconciliationRecord existing = reconciliations.get(eventId);
            if (existing != null) {
                if (!existing.eventType().equals(eventType)) {
                    throw new IllegalStateException("reconciliation event ID collision");
                }
                return false;
            }
            reconciliations.put(eventId,
                    new ReconciliationRecord(eventId, eventType, ReconciliationResult.PENDING));
            return true;
        }

        public void completeReconciliation(String eventId, ReconciliationResult result) {
            ReconciliationRecord current = reconciliations.get(eventId);
            if (current == null) throw new IllegalStateException("EVENT_RECEIVED missing");
            if (current.result() != ReconciliationResult.PENDING) {
                if (current.result() != result) {
                    throw new IllegalStateException("reconciliation result is immutable");
                }
                return;
            }
            if (result == ReconciliationResult.PENDING) {
                throw new IllegalArgumentException("completion cannot remain PENDING");
            }
            reconciliations.put(eventId, new ReconciliationRecord(eventId, current.eventType(), result));
        }

        public void observeOptionalLayer(String layer, boolean available) {
            optionalLayerObservations.add(requireText(layer, "layer") + "=" + available);
        }

        public EvidenceProjection evidence(String occurrenceId) {
            Occurrence occurrence = requireOccurrence(occurrenceId);
            return new EvidenceProjection(
                    true,
                    occurrence.state == OccurrenceState.ARMED_VERIFIED,
                    occurrence.triggerWallMillis != null,
                    occurrence.softwareAudioMonotonicMillis != null,
                    occurrence.physicalAudioObserved,
                    occurrence.humanAwake);
        }

        public EngineSnapshot snapshot() {
            Map<String, AlarmIntent> intentCopies = new LinkedHashMap<>(intents);
            Map<String, OccurrenceSnapshot> occurrenceCopies = new LinkedHashMap<>();
            occurrences.forEach((id, occurrence) -> occurrenceCopies.put(id, snapshotOf(occurrence)));
            return new EngineSnapshot(
                    Collections.unmodifiableMap(intentCopies),
                    Collections.unmodifiableMap(occurrenceCopies),
                    Collections.unmodifiableSet(new HashSet<>(triggerTokens)),
                    Collections.unmodifiableMap(new HashMap<>(snoozeChildren)),
                    Collections.unmodifiableMap(new LinkedHashMap<>(reconciliations)),
                    outputOwner);
        }

        public static Engine resumeLocal(EngineSnapshot snapshot) {
            Engine engine = new Engine();
            engine.intents.putAll(snapshot.intents());
            snapshot.occurrences().forEach((id, value) -> {
                Occurrence occurrence = fromSnapshot(value);
                if (EnumSet.of(
                        OccurrenceState.ARMING,
                        OccurrenceState.TRIGGERING,
                        OccurrenceState.OUTPUT_WAITING,
                        OccurrenceState.RINGING,
                        OccurrenceState.SNOOZE_PENDING,
                        OccurrenceState.RECOVERED_LATE).contains(occurrence.state)) {
                    occurrence.state = OccurrenceState.RECOVERY_REQUIRED;
                }
                engine.occurrences.put(id, occurrence);
            });
            engine.triggerTokens.addAll(snapshot.triggerTokens());
            engine.snoozeChildren.putAll(snapshot.snoozeChildren());
            engine.reconciliations.putAll(snapshot.reconciliations());
            // Physical output is process-owned and never survives a local process restart.
            engine.outputOwner = null;
            return engine;
        }

        public static Engine restoreFromBackup(EngineSnapshot backup, String newBootId) {
            Engine restored = new Engine();
            restored.intents.putAll(backup.intents());
            for (OccurrenceSnapshot source : backup.occurrences().values()) {
                if (isTerminal(source.state()) || source.tombstone()) continue;
                Occurrence candidate = new Occurrence(
                        source.occurrenceId(), source.alarmId(), source.generation(),
                        source.civilDate(), source.civilTime(), source.zoneId(),
                        source.scheduledInstant(), source.selectedOffset(),
                        source.parentOccurrenceId(), -1L, newBootId,
                        OccurrenceState.READINESS_CHECK_REQUIRED,
                        SchedulingObservation.UNKNOWN, false, null, null, null, false, false);
                restored.occurrences.put(candidate.occurrenceId, candidate);
            }
            return restored;
        }

        public AlarmIntent intent(String alarmId) { return requireIntent(alarmId); }
        public Occurrence occurrence(String occurrenceId) { return requireOccurrence(occurrenceId); }
        public List<Occurrence> occurrences() { return List.copyOf(occurrences.values()); }
        public Optional<String> outputOwner() { return Optional.ofNullable(outputOwner); }
        public Map<String, ReconciliationRecord> reconciliations() { return Map.copyOf(reconciliations); }
        public int optionalObservationCount() { return optionalLayerObservations.size(); }

        public void verifyInternalInvariants() {
            int owners = outputOwner == null ? 0 : 1;
            if (owners > 1) throw new IllegalStateException("multiple output owners");
            if (outputOwner != null) {
                Occurrence owner = occurrences.get(outputOwner);
                if (owner == null || owner.state != OccurrenceState.RINGING) {
                    throw new IllegalStateException("output owner is not RINGING");
                }
            }
            Set<String> ids = new HashSet<>();
            for (Occurrence occurrence : occurrences.values()) {
                if (!ids.add(occurrence.occurrenceId)) {
                    throw new IllegalStateException("duplicate occurrence ID");
                }
                AlarmIntent intent = intents.get(occurrence.alarmId);
                if (occurrence.state == OccurrenceState.RINGING
                        && (intent == null || intent.status() != IntentStatus.ENABLED
                        || intent.generation() != occurrence.generation || occurrence.tombstone)) {
                    throw new IllegalStateException("invalid occurrence is ringing");
                }
                if (occurrence.state == OccurrenceState.DISMISSED && !occurrence.tombstone) {
                    throw new IllegalStateException("dismissed occurrence lacks tombstone");
                }
                if (occurrence.state == OccurrenceState.ARMED_VERIFIED
                        && (occurrence.checkpoint == null
                        || occurrence.schedulingObservation != SchedulingObservation.REGISTERED)) {
                    throw new IllegalStateException("false ARMED_VERIFIED");
                }
            }
        }

        private AlarmIntent requireIntent(String alarmId) {
            AlarmIntent intent = intents.get(alarmId);
            if (intent == null) throw new IllegalArgumentException("unknown alarm: " + alarmId);
            return intent;
        }

        private Occurrence requireOccurrence(String occurrenceId) {
            Occurrence occurrence = occurrences.get(occurrenceId);
            if (occurrence == null) throw new IllegalArgumentException("unknown occurrence: " + occurrenceId);
            return occurrence;
        }

        private void invalidateOldGenerations(String alarmId, long activeGeneration) {
            for (Occurrence occurrence : occurrences.values()) {
                if (occurrence.alarmId.equals(alarmId)
                        && occurrence.generation != activeGeneration
                        && !isTerminal(occurrence.state)) {
                    occurrence.tombstone = true;
                    occurrence.schedulingObservation = SchedulingObservation.INVALIDATED;
                    if (allowedTargets(occurrence.state).contains(OccurrenceState.INVALIDATED)) {
                        transition(occurrence, OccurrenceState.INVALIDATED);
                    }
                    releaseOutput(occurrence.occurrenceId);
                }
            }
        }

        private void releaseOutput(String occurrenceId) {
            if (occurrenceId.equals(outputOwner)) outputOwner = null;
        }
    }

    public static CivilResolution resolveCivil(LocalDate date, LocalTime time, ZoneId zoneId) {
        Objects.requireNonNull(date, "date");
        Objects.requireNonNull(time, "time");
        Objects.requireNonNull(zoneId, "zoneId");
        LocalDateTime requested = LocalDateTime.of(date, time);
        ZoneRules rules = zoneId.getRules();
        List<ZoneOffset> offsets = rules.getValidOffsets(requested);
        if (offsets.size() == 1) {
            ZoneOffset offset = offsets.get(0);
            return new CivilResolution(date, time, zoneId, requested, offset,
                    requested.toInstant(offset), "NONE", 0);
        }
        if (offsets.isEmpty()) {
            ZoneOffsetTransition transition = rules.getTransition(requested);
            if (transition == null || !transition.isGap()) {
                throw new IllegalStateException("zone rules returned no offset and no gap transition");
            }
            LocalDateTime resolved = transition.getDateTimeAfter();
            ZoneOffset offset = transition.getOffsetAfter();
            return new CivilResolution(date, time, zoneId, resolved, offset,
                    resolved.toInstant(offset), "GAP_FORWARD", 0);
        }
        ZoneOffset firstOffset = offsets.get(0);
        return new CivilResolution(date, time, zoneId, requested, firstOffset,
                requested.toInstant(firstOffset), "FOLD_FIRST", 0);
    }

    public static String occurrenceId(
            String alarmId, long generation, LocalDate date, LocalTime time,
            int foldOrdinal, String parentOccurrenceId) {
        String canonical = String.join("\u001f",
                requireText(alarmId, "alarmId"), Long.toString(generation),
                date.toString(), time.toString(), Integer.toString(foldOrdinal),
                parentOccurrenceId == null ? "-" : parentOccurrenceId);
        return "occ-" + sha256Hex(canonical.getBytes(StandardCharsets.UTF_8));
    }

    public static String snoozeOccurrenceId(String parentOccurrenceId, long generation, Instant dueAt) {
        String canonical = "snooze\u001f" + requireText(parentOccurrenceId, "parentOccurrenceId")
                + "\u001f" + generation + "\u001f" + dueAt.toEpochMilli();
        return "occ-" + sha256Hex(canonical.getBytes(StandardCharsets.UTF_8));
    }

    public static DeliveryBand classifyDeliveryDelta(long deltaMillis) {
        if (deltaMillis < DELIVERY_EARLY_LIMIT_MS || deltaMillis > DELIVERY_ACCEPTABLE_LIMIT_MS) {
            return DeliveryBand.FAILURE;
        }
        if (deltaMillis < 0L) return DeliveryBand.EARLY_TOLERANCE;
        if (deltaMillis <= DELIVERY_TARGET_LIMIT_MS) return DeliveryBand.TARGET;
        return DeliveryBand.ACCEPTABLE_LATE;
    }

    public static AudioBand classifyAudioDelta(Long deltaMillis) {
        if (deltaMillis == null) return AudioBand.UNKNOWN;
        if (deltaMillis < 0L || deltaMillis > AUDIO_ACCEPTABLE_LIMIT_MS) return AudioBand.FAILURE;
        if (deltaMillis <= AUDIO_TARGET_LIMIT_MS) return AudioBand.TARGET;
        return AudioBand.ACCEPTABLE;
    }

    public static RecoveryDecision lateRecoveryDecision(
            Instant scheduled, Instant now, boolean terminalOrTombstoned,
            boolean deliveryFailureConfirmed) {
        if (terminalOrTombstoned) return RecoveryDecision.SKIP_TERMINAL;
        long lateBy = now.toEpochMilli() - scheduled.toEpochMilli();
        if (lateBy < 0L) return RecoveryDecision.NOT_DUE;
        if (lateBy <= LATE_RECOVERY_LIMIT_MS) return RecoveryDecision.RECOVER_NOW;
        return deliveryFailureConfirmed ? RecoveryDecision.MISSED : RecoveryDecision.OUTCOME_UNKNOWN;
    }

    public static boolean mayReuseMonotonicDeadline(String originalBootId, String currentBootId) {
        return Objects.equals(originalBootId, currentBootId);
    }

    public static StorageClass storageClassFor(String field) {
        Objects.requireNonNull(field, "field");
        Set<String> deviceProtected = Set.of(
                "alarm_id", "generation", "occurrence_id", "parent_occurrence_id",
                "civil_rule", "scheduled_instant", "zone_offset", "operational_state",
                "tombstone", "readiness_checkpoint", "fallback_audio_marker_id",
                "session_deadline", "snooze_deadline");
        Set<String> credentialProtected = Set.of(
                "name", "reminder", "calendar", "location", "reflection_text",
                "quote", "voice_profile", "wake_plan", "message_history");
        if (deviceProtected.contains(field)) return StorageClass.DEVICE_PROTECTED;
        if (credentialProtected.contains(field)) return StorageClass.CREDENTIAL_PROTECTED;
        return StorageClass.FORBIDDEN;
    }

    public static Set<String> fallbackWakePlanFields() {
        return Set.of("occurrence_id", "generation", "scheduled_instant", "fallback_audio_marker_id");
    }

    public static boolean isTerminal(OccurrenceState state) {
        return EnumSet.of(
                OccurrenceState.SNOOZED,
                OccurrenceState.DISMISSED,
                OccurrenceState.DISABLED,
                OccurrenceState.MISSED,
                OccurrenceState.UNANSWERED).contains(state);
    }

    private static RecoveryDecision stateToRecoveryDecision(OccurrenceState state) {
        return switch (state) {
            case RECOVERED_LATE, RINGING, TRIGGERING, OUTPUT_WAITING -> RecoveryDecision.RECOVER_NOW;
            case MISSED -> RecoveryDecision.MISSED;
            case OUTCOME_UNKNOWN -> RecoveryDecision.OUTCOME_UNKNOWN;
            case SNOOZED, DISMISSED, DISABLED, UNANSWERED -> RecoveryDecision.SKIP_TERMINAL;
            default -> RecoveryDecision.NOT_DUE;
        };
    }

    private static void transition(Occurrence occurrence, OccurrenceState next) {
        if (occurrence.state == next) return;
        if (isTerminal(occurrence.state)) {
            throw new IllegalStateException("terminal occurrence cannot reopen: " + occurrence.state + " -> " + next);
        }
        if (!allowedTargets(occurrence.state).contains(next)) {
            throw new IllegalStateException("invalid transition: " + occurrence.state + " -> " + next);
        }
        occurrence.state = next;
    }

    private static Set<OccurrenceState> allowedTargets(OccurrenceState state) {
        return switch (state) {
            case CONFIGURED -> EnumSet.of(OccurrenceState.READINESS_CHECK_REQUIRED,
                    OccurrenceState.DISABLED, OccurrenceState.INVALIDATED,
                    OccurrenceState.RECOVERY_REQUIRED, OccurrenceState.MISSED,
                    OccurrenceState.OUTCOME_UNKNOWN);
            case READINESS_CHECK_REQUIRED -> EnumSet.of(OccurrenceState.ARMABLE,
                    OccurrenceState.BLOCKED, OccurrenceState.RECOVERY_REQUIRED,
                    OccurrenceState.DISABLED, OccurrenceState.INVALIDATED,
                    OccurrenceState.MISSED, OccurrenceState.OUTCOME_UNKNOWN);
            case ARMABLE -> EnumSet.of(OccurrenceState.ARMING, OccurrenceState.BLOCKED,
                    OccurrenceState.DISABLED, OccurrenceState.INVALIDATED,
                    OccurrenceState.MISSED, OccurrenceState.OUTCOME_UNKNOWN);
            case ARMING -> EnumSet.of(OccurrenceState.ARMED_VERIFIED,
                    OccurrenceState.BLOCKED, OccurrenceState.RECOVERY_REQUIRED,
                    OccurrenceState.DISABLED, OccurrenceState.INVALIDATED,
                    OccurrenceState.MISSED, OccurrenceState.OUTCOME_UNKNOWN);
            case ARMED_VERIFIED -> EnumSet.of(OccurrenceState.TRIGGERING,
                    OccurrenceState.RECOVERED_LATE, OccurrenceState.READINESS_STALE,
                    OccurrenceState.INVALIDATED, OccurrenceState.DISABLED,
                    OccurrenceState.MISSED, OccurrenceState.OUTCOME_UNKNOWN);
            case READINESS_STALE -> EnumSet.of(OccurrenceState.READINESS_CHECK_REQUIRED,
                    OccurrenceState.BLOCKED, OccurrenceState.RECOVERY_REQUIRED,
                    OccurrenceState.DISABLED, OccurrenceState.INVALIDATED,
                    OccurrenceState.TRIGGERING, OccurrenceState.RECOVERED_LATE,
                    OccurrenceState.MISSED, OccurrenceState.OUTCOME_UNKNOWN);
            case BLOCKED -> EnumSet.of(OccurrenceState.READINESS_CHECK_REQUIRED,
                    OccurrenceState.DISABLED, OccurrenceState.TRIGGERING,
                    OccurrenceState.RECOVERY_REQUIRED, OccurrenceState.MISSED,
                    OccurrenceState.OUTCOME_UNKNOWN);
            case INVALIDATED -> EnumSet.of(OccurrenceState.RECOVERY_REQUIRED,
                    OccurrenceState.DISABLED, OccurrenceState.MISSED,
                    OccurrenceState.OUTCOME_UNKNOWN);
            case TRIGGERING -> EnumSet.of(OccurrenceState.RINGING,
                    OccurrenceState.OUTPUT_WAITING, OccurrenceState.RECOVERY_REQUIRED,
                    OccurrenceState.MISSED, OccurrenceState.OUTCOME_UNKNOWN,
                    OccurrenceState.DISMISSED, OccurrenceState.DISABLED,
                    OccurrenceState.INVALIDATED);
            case OUTPUT_WAITING -> EnumSet.of(OccurrenceState.RINGING,
                    OccurrenceState.RECOVERED_LATE, OccurrenceState.MISSED,
                    OccurrenceState.OUTCOME_UNKNOWN, OccurrenceState.DISMISSED,
                    OccurrenceState.DISABLED, OccurrenceState.INVALIDATED);
            case RINGING -> EnumSet.of(OccurrenceState.SNOOZE_PENDING,
                    OccurrenceState.DISMISSED, OccurrenceState.INTERRUPTED,
                    OccurrenceState.UNANSWERED, OccurrenceState.DISABLED,
                    OccurrenceState.RECOVERY_REQUIRED, OccurrenceState.INVALIDATED);
            case SNOOZE_PENDING -> EnumSet.of(OccurrenceState.SNOOZED,
                    OccurrenceState.BLOCKED, OccurrenceState.RECOVERY_REQUIRED,
                    OccurrenceState.DISMISSED, OccurrenceState.DISABLED,
                    OccurrenceState.INVALIDATED);
            case INTERRUPTED -> EnumSet.of(OccurrenceState.RECOVERY_REQUIRED,
                    OccurrenceState.DISMISSED, OccurrenceState.OUTCOME_UNKNOWN,
                    OccurrenceState.DISABLED, OccurrenceState.INVALIDATED);
            case RECOVERY_REQUIRED -> EnumSet.of(OccurrenceState.READINESS_CHECK_REQUIRED,
                    OccurrenceState.RECOVERED_LATE, OccurrenceState.MISSED,
                    OccurrenceState.OUTCOME_UNKNOWN, OccurrenceState.DISABLED,
                    OccurrenceState.INVALIDATED);
            case RECOVERED_LATE -> EnumSet.of(OccurrenceState.RINGING,
                    OccurrenceState.OUTPUT_WAITING, OccurrenceState.INTERRUPTED,
                    OccurrenceState.DISMISSED, OccurrenceState.UNANSWERED,
                    OccurrenceState.RECOVERY_REQUIRED, OccurrenceState.DISABLED,
                    OccurrenceState.INVALIDATED);
            case OUTCOME_UNKNOWN -> EnumSet.of(OccurrenceState.MISSED,
                    OccurrenceState.DISMISSED, OccurrenceState.DISABLED);
            case SNOOZED, DISMISSED, DISABLED, MISSED, UNANSWERED -> EnumSet.noneOf(OccurrenceState.class);
        };
    }

    private static OccurrenceSnapshot snapshotOf(Occurrence occurrence) {
        return new OccurrenceSnapshot(
                occurrence.occurrenceId, occurrence.alarmId, occurrence.generation,
                occurrence.civilDate, occurrence.civilTime, occurrence.zoneId,
                occurrence.scheduledInstant, occurrence.selectedOffset,
                occurrence.parentOccurrenceId, occurrence.snoozeDeadlineMonotonicMillis,
                occurrence.originatingBootId, occurrence.state,
                occurrence.schedulingObservation, occurrence.tombstone,
                occurrence.checkpoint, occurrence.triggerWallMillis,
                occurrence.softwareAudioMonotonicMillis,
                occurrence.physicalAudioObserved, occurrence.humanAwake);
    }

    private static Occurrence fromSnapshot(OccurrenceSnapshot snapshot) {
        return new Occurrence(
                snapshot.occurrenceId(), snapshot.alarmId(), snapshot.generation(),
                snapshot.civilDate(), snapshot.civilTime(), snapshot.zoneId(),
                snapshot.scheduledInstant(), snapshot.selectedOffset(),
                snapshot.parentOccurrenceId(), snapshot.snoozeDeadlineMonotonicMillis(),
                snapshot.originatingBootId(), snapshot.state(),
                snapshot.schedulingObservation(), snapshot.tombstone(),
                snapshot.checkpoint(), snapshot.triggerWallMillis(),
                snapshot.softwareAudioMonotonicMillis(),
                snapshot.physicalAudioObserved(), snapshot.humanAwake());
    }

    static String sha256Hex(byte[] bytes) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256").digest(bytes);
            StringBuilder hex = new StringBuilder(digest.length * 2);
            for (byte value : digest) hex.append(String.format("%02x", value));
            return hex.toString();
        } catch (NoSuchAlgorithmException impossible) {
            throw new IllegalStateException("SHA-256 unavailable", impossible);
        }
    }

    private static String requireText(String value, String name) {
        if (value == null || value.isBlank()) throw new IllegalArgumentException(name + " is blank");
        return value;
    }
}
