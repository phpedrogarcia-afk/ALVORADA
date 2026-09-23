package org.alvorada.reliability.wakecore;

import java.time.Instant;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.LocalTime;
import java.time.ZoneId;
import java.time.ZoneOffset;
import java.time.ZonedDateTime;
import java.time.format.DateTimeFormatter;
import java.time.zone.ZoneOffsetTransition;
import java.time.zone.ZoneRules;
import java.util.List;

/**
 * Authoritative civil scheduling resolver for ALVORADA G1.
 *
 * Implements frozen policies:
 * 1. Timezone change preserves civil local clock time (e.g. 07:00 remains 07:00 in new zone).
 * 2. DST gap forwards to the first valid local time after the gap (DST_GAP_FORWARD).
 * 3. DST fold selects the first valid occurrence only (DST_FOLD_FIRST_OCCURRENCE).
 */
public final class CivilScheduleResolver {

    public static final String REASON_STANDARD = "STANDARD";
    public static final String REASON_DST_GAP_FORWARD = "DST_GAP_FORWARD";
    public static final String REASON_DST_FOLD_FIRST_OCCURRENCE = "DST_FOLD_FIRST_OCCURRENCE";

    public static final class ResolutionResult {
        public final String requestedLocal;
        public final String resolvedLocal;
        public final String resolvedOffset;
        public final long resolvedInstantEpochMs;
        public final String resolutionReason;
        public final String selectedOffset;
        public final String discardedSecondOffset;
        public final String timezoneId;

        public ResolutionResult(
                String requestedLocal,
                String resolvedLocal,
                String resolvedOffset,
                long resolvedInstantEpochMs,
                String resolutionReason,
                String selectedOffset,
                String discardedSecondOffset,
                String timezoneId) {
            this.requestedLocal = requestedLocal;
            this.resolvedLocal = resolvedLocal;
            this.resolvedOffset = resolvedOffset;
            this.resolvedInstantEpochMs = resolvedInstantEpochMs;
            this.resolutionReason = resolutionReason;
            this.selectedOffset = selectedOffset;
            this.discardedSecondOffset = discardedSecondOffset;
            this.timezoneId = timezoneId;
        }

        public String toJsonString() {
            StringBuilder sb = new StringBuilder();
            sb.append("{\n");
            sb.append("  \"requested_local\": \"").append(requestedLocal).append("\",\n");
            sb.append("  \"resolved_local\": \"").append(resolvedLocal).append("\",\n");
            sb.append("  \"resolved_offset\": \"").append(resolvedOffset).append("\",\n");
            sb.append("  \"resolved_instant\": \"").append(Instant.ofEpochMilli(resolvedInstantEpochMs).toString()).append("\",\n");
            sb.append("  \"resolved_instant_epoch_ms\": ").append(resolvedInstantEpochMs).append(",\n");
            sb.append("  \"resolution_reason\": \"").append(resolutionReason).append("\",\n");
            sb.append("  \"selected_offset\": \"").append(selectedOffset != null ? selectedOffset : resolvedOffset).append("\",\n");
            if (discardedSecondOffset != null) {
                sb.append("  \"discarded_second_offset\": \"").append(discardedSecondOffset).append("\",\n");
            }
            sb.append("  \"timezone_id\": \"").append(timezoneId).append("\"\n");
            sb.append("}");
            return sb.toString();
        }
    }

    /**
     * Resolves a target civil local time on a given local date in a timezone,
     * applying frozen policies:
     * 1. If gap: resolve to first valid local time after the gap (DST_GAP_FORWARD).
     * 2. If fold: use the first valid occurrence only (DST_FOLD_FIRST_OCCURRENCE).
     * 3. Otherwise: standard time (STANDARD).
     */
    public static ResolutionResult resolve(LocalDate targetDate, LocalTime targetTime, ZoneId zone) {
        LocalDateTime requestedLdt = LocalDateTime.of(targetDate, targetTime);
        ZoneRules rules = zone.getRules();
        List<ZoneOffset> validOffsets = rules.getValidOffsets(requestedLdt);

        if (validOffsets.size() == 1) {
            // Standard unambiguous resolution
            ZoneOffset offset = validOffsets.get(0);
            ZonedDateTime zdt = requestedLdt.atZone(zone);
            return new ResolutionResult(
                    requestedLdt.toString(),
                    requestedLdt.toString(),
                    offset.getId(),
                    zdt.toInstant().toEpochMilli(),
                    REASON_STANDARD,
                    offset.getId(),
                    null,
                    zone.getId()
            );
        } else if (validOffsets.isEmpty()) {
            // DST Gap: the requested local time does not exist.
            // Policy: resolve to FIRST VALID LOCAL TIME AFTER THE GAP.
            ZoneOffsetTransition trans = rules.getTransition(requestedLdt);
            LocalDateTime resolvedLdt;
            ZoneOffset resolvedOffset;
            if (trans != null && trans.isGap()) {
                resolvedLdt = trans.getDateTimeAfter();
                resolvedOffset = trans.getOffsetAfter();
            } else {
                // Fallback for non-standard zone transitions
                resolvedLdt = requestedLdt.plusHours(1);
                resolvedOffset = zone.getRules().getOffset(resolvedLdt);
            }
            long epochMs = resolvedLdt.toInstant(resolvedOffset).toEpochMilli();
            return new ResolutionResult(
                    requestedLdt.toString(),
                    resolvedLdt.toString(),
                    resolvedOffset.getId(),
                    epochMs,
                    REASON_DST_GAP_FORWARD,
                    resolvedOffset.getId(),
                    null,
                    zone.getId()
            );
        } else {
            // DST Fold / Overlap: the local time occurs twice.
            // Policy: use the FIRST valid occurrence only.
            // The earlier absolute occurrence corresponds to getOffsetBefore().
            ZoneOffsetTransition trans = rules.getTransition(requestedLdt);
            ZoneOffset selectedOffset;
            ZoneOffset discardedOffset;
            if (trans != null && trans.isOverlap()) {
                selectedOffset = trans.getOffsetBefore();
                discardedOffset = trans.getOffsetAfter();
            } else {
                selectedOffset = validOffsets.get(0);
                discardedOffset = validOffsets.size() > 1 ? validOffsets.get(1) : null;
            }
            long epochMs = requestedLdt.toInstant(selectedOffset).toEpochMilli();
            return new ResolutionResult(
                    requestedLdt.toString(),
                    requestedLdt.toString(),
                    selectedOffset.getId(),
                    epochMs,
                    REASON_DST_FOLD_FIRST_OCCURRENCE,
                    selectedOffset.getId(),
                    discardedOffset != null ? discardedOffset.getId() : null,
                    zone.getId()
            );
        }
    }

    /**
     * Resolves next occurrence given a civil recurrence rule (e.g. "07:00"),
     * timezone ID, and current instant.
     * Policy: Civil local clock time is preserved across timezone changes!
     */
    public static ResolutionResult resolveNextOccurrence(
            String civilTimeStr,
            String timezoneId,
            long nowEpochMs) {
        ZoneId zone = ZoneId.of(timezoneId);
        LocalTime civilTime = LocalTime.parse(civilTimeStr, DateTimeFormatter.ISO_LOCAL_TIME);
        Instant now = Instant.ofEpochMilli(nowEpochMs);
        ZonedDateTime nowZdt = now.atZone(zone);

        LocalDate candidateDate = nowZdt.toLocalDate();
        ResolutionResult result = resolve(candidateDate, civilTime, zone);

        // If resolved occurrence is in the past, schedule for tomorrow
        if (result.resolvedInstantEpochMs <= nowEpochMs) {
            candidateDate = candidateDate.plusDays(1);
            result = resolve(candidateDate, civilTime, zone);
        }

        return result;
    }

    public static void main(String[] args) {
        if (args.length < 3) {
            System.err.println("Usage: CivilScheduleResolver <date YYYY-MM-DD> <time HH:MM:SS> <timezone_id>");
            System.exit(1);
        }
        LocalDate date = LocalDate.parse(args[0]);
        LocalTime time = LocalTime.parse(args[1]);
        ZoneId zone = ZoneId.of(args[2]);
        ResolutionResult res = resolve(date, time, zone);
        System.out.println(res.toJsonString());
    }
}
