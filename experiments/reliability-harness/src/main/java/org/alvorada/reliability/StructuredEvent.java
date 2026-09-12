package org.alvorada.reliability;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.Objects;

/** Whitelisted technical event. No arbitrary metadata field is accepted. */
public record StructuredEvent(
        String eventId,
        String evidenceId,
        String alarmId,
        String occurrenceId,
        long generation,
        String eventType,
        long monotonicTimestampMillis,
        long wallClockTimestampMillis,
        Integer apiLevel,
        AlarmModel.ReadinessState readinessState,
        AlarmModel.SchedulingStrategy schedulingStrategy,
        String result) {

    public StructuredEvent {
        requireText(eventId, "eventId");
        requireText(evidenceId, "evidenceId");
        requireText(alarmId, "alarmId");
        requireText(occurrenceId, "occurrenceId");
        requireText(eventType, "eventType");
        Objects.requireNonNull(readinessState, "readinessState");
        Objects.requireNonNull(schedulingStrategy, "schedulingStrategy");
        requireText(result, "result");
    }

    public String toJsonLine() {
        return "{" +
                "\"event_id\":\"" + escape(eventId) + "\"," +
                "\"evidence_id\":\"" + escape(evidenceId) + "\"," +
                "\"alarm_id\":\"" + escape(alarmId) + "\"," +
                "\"occurrence_id\":\"" + escape(occurrenceId) + "\"," +
                "\"generation\":" + generation + "," +
                "\"event_type\":\"" + escape(eventType) + "\"," +
                "\"monotonic_timestamp_ms\":" + monotonicTimestampMillis + "," +
                "\"wall_clock_timestamp_ms\":" + wallClockTimestampMillis + "," +
                "\"api_level\":" + (apiLevel == null ? "null" : apiLevel) + "," +
                "\"readiness_state\":\"" + readinessState.name() + "\"," +
                "\"scheduling_strategy\":\"" + schedulingStrategy.name() + "\"," +
                "\"result\":\"" + escape(result) + "\"}";
    }

    public void appendTo(Path ndjson) throws IOException {
        Path absolute = ndjson.toAbsolutePath();
        Files.createDirectories(absolute.getParent());
        Files.writeString(absolute, toJsonLine() + System.lineSeparator(),
                StandardCharsets.UTF_8, StandardOpenOption.CREATE, StandardOpenOption.APPEND);
    }

    private static String escape(String value) {
        StringBuilder escaped = new StringBuilder(value.length() + 8);
        for (int index = 0; index < value.length(); index++) {
            char character = value.charAt(index);
            switch (character) {
                case '"' -> escaped.append("\\\"");
                case '\\' -> escaped.append("\\\\");
                case '\n' -> escaped.append("\\n");
                case '\r' -> escaped.append("\\r");
                case '\t' -> escaped.append("\\t");
                default -> {
                    if (character < 0x20) escaped.append(String.format("\\u%04x", (int) character));
                    else escaped.append(character);
                }
            }
        }
        return escaped.toString();
    }

    private static void requireText(String value, String name) {
        if (value == null || value.isBlank()) throw new IllegalArgumentException(name + " is blank");
    }
}
