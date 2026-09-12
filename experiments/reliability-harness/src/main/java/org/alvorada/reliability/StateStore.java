package org.alvorada.reliability;

import static org.alvorada.reliability.AlarmModel.EngineSnapshot;

import java.io.BufferedInputStream;
import java.io.BufferedOutputStream;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.EOFException;
import java.io.IOException;
import java.nio.file.AtomicMoveNotSupportedException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.time.Instant;
import java.time.LocalDate;
import java.time.LocalTime;
import java.time.ZoneId;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

/** Versioned, test-only durable codec. This is deliberately not a product schema. */
public final class StateStore {
    private static final int MAGIC = 0x41564F52; // AVOR
    private static final int FORMAT_VERSION = 1;

    private StateStore() {}

    public static void saveAtomic(Path target, AlarmModel.Engine engine) throws IOException {
        Path absolute = target.toAbsolutePath();
        Path parent = absolute.getParent();
        if (parent == null) throw new IOException("state path has no parent");
        Files.createDirectories(parent);
        Path temporary = parent.resolve(absolute.getFileName() + ".tmp");
        try (DataOutputStream output = new DataOutputStream(
                new BufferedOutputStream(Files.newOutputStream(temporary)))) {
            writeSnapshot(output, engine.snapshot());
        }
        try {
            Files.move(temporary, absolute, StandardCopyOption.ATOMIC_MOVE,
                    StandardCopyOption.REPLACE_EXISTING);
        } catch (AtomicMoveNotSupportedException unsupported) {
            Files.move(temporary, absolute, StandardCopyOption.REPLACE_EXISTING);
        }
    }

    public static AlarmModel.Engine loadLocal(Path source) throws IOException {
        try (DataInputStream input = new DataInputStream(
                new BufferedInputStream(Files.newInputStream(source)))) {
            return AlarmModel.Engine.resumeLocal(readSnapshot(input));
        } catch (EOFException truncated) {
            throw new IOException("truncated harness state", truncated);
        }
    }

    public static EngineSnapshot readSnapshot(Path source) throws IOException {
        try (DataInputStream input = new DataInputStream(
                new BufferedInputStream(Files.newInputStream(source)))) {
            return readSnapshot(input);
        } catch (EOFException truncated) {
            throw new IOException("truncated harness state", truncated);
        }
    }

    private static void writeSnapshot(DataOutputStream output, EngineSnapshot snapshot) throws IOException {
        output.writeInt(MAGIC);
        output.writeInt(FORMAT_VERSION);

        List<AlarmModel.AlarmIntent> intents = new ArrayList<>(snapshot.intents().values());
        intents.sort(Comparator.comparing(AlarmModel.AlarmIntent::alarmId));
        output.writeInt(intents.size());
        for (AlarmModel.AlarmIntent intent : intents) {
            output.writeUTF(intent.alarmId());
            output.writeLong(intent.generation());
            output.writeUTF(intent.status().name());
            output.writeUTF(intent.localTime().toString());
            output.writeUTF(intent.zoneId().getId());
        }

        List<AlarmModel.OccurrenceSnapshot> occurrences = new ArrayList<>(snapshot.occurrences().values());
        occurrences.sort(Comparator.comparing(AlarmModel.OccurrenceSnapshot::occurrenceId));
        output.writeInt(occurrences.size());
        for (AlarmModel.OccurrenceSnapshot occurrence : occurrences) {
            output.writeUTF(occurrence.occurrenceId());
            output.writeUTF(occurrence.alarmId());
            output.writeLong(occurrence.generation());
            output.writeUTF(occurrence.civilDate().toString());
            output.writeUTF(occurrence.civilTime().toString());
            output.writeUTF(occurrence.zoneId().getId());
            output.writeLong(occurrence.scheduledInstant().toEpochMilli());
            output.writeInt(occurrence.selectedOffset().getTotalSeconds());
            writeNullableString(output, occurrence.parentOccurrenceId());
            output.writeLong(occurrence.snoozeDeadlineMonotonicMillis());
            output.writeUTF(occurrence.originatingBootId());
            output.writeUTF(occurrence.state().name());
            output.writeUTF(occurrence.schedulingObservation().name());
            output.writeBoolean(occurrence.tombstone());
            writeCheckpoint(output, occurrence.checkpoint());
            writeNullableLong(output, occurrence.triggerWallMillis());
            writeNullableLong(output, occurrence.softwareAudioMonotonicMillis());
            output.writeBoolean(occurrence.physicalAudioObserved());
            output.writeBoolean(occurrence.humanAwake());
        }

        writeSortedStrings(output, snapshot.triggerTokens());
        writeSortedMap(output, snapshot.snoozeChildren());

        List<AlarmModel.ReconciliationRecord> reconciliations =
                new ArrayList<>(snapshot.reconciliations().values());
        reconciliations.sort(Comparator.comparing(AlarmModel.ReconciliationRecord::eventId));
        output.writeInt(reconciliations.size());
        for (AlarmModel.ReconciliationRecord record : reconciliations) {
            output.writeUTF(record.eventId());
            output.writeUTF(record.eventType());
            output.writeUTF(record.result().name());
        }
        writeNullableString(output, snapshot.outputOwner());
    }

    private static EngineSnapshot readSnapshot(DataInputStream input) throws IOException {
        if (input.readInt() != MAGIC) throw new IOException("invalid harness state magic");
        int version = input.readInt();
        if (version != FORMAT_VERSION) throw new IOException("unsupported harness state version: " + version);

        int intentCount = readCount(input, "intent");
        Map<String, AlarmModel.AlarmIntent> intents = new LinkedHashMap<>();
        for (int index = 0; index < intentCount; index++) {
            AlarmModel.AlarmIntent intent = new AlarmModel.AlarmIntent(
                    input.readUTF(), input.readLong(),
                    AlarmModel.IntentStatus.valueOf(input.readUTF()),
                    LocalTime.parse(input.readUTF()), ZoneId.of(input.readUTF()));
            intents.put(intent.alarmId(), intent);
        }

        int occurrenceCount = readCount(input, "occurrence");
        Map<String, AlarmModel.OccurrenceSnapshot> occurrences = new LinkedHashMap<>();
        for (int index = 0; index < occurrenceCount; index++) {
            AlarmModel.OccurrenceSnapshot occurrence = new AlarmModel.OccurrenceSnapshot(
                    input.readUTF(), input.readUTF(), input.readLong(),
                    LocalDate.parse(input.readUTF()), LocalTime.parse(input.readUTF()),
                    ZoneId.of(input.readUTF()), Instant.ofEpochMilli(input.readLong()),
                    ZoneOffset.ofTotalSeconds(input.readInt()), readNullableString(input),
                    input.readLong(), input.readUTF(),
                    AlarmModel.OccurrenceState.valueOf(input.readUTF()),
                    AlarmModel.SchedulingObservation.valueOf(input.readUTF()),
                    input.readBoolean(), readCheckpoint(input),
                    readNullableLong(input), readNullableLong(input),
                    input.readBoolean(), input.readBoolean());
            occurrences.put(occurrence.occurrenceId(), occurrence);
        }

        Set<String> triggerTokens = readStringSet(input);
        Map<String, String> snoozeChildren = readStringMap(input);
        int reconciliationCount = readCount(input, "reconciliation");
        Map<String, AlarmModel.ReconciliationRecord> reconciliations = new LinkedHashMap<>();
        for (int index = 0; index < reconciliationCount; index++) {
            AlarmModel.ReconciliationRecord record = new AlarmModel.ReconciliationRecord(
                    input.readUTF(), input.readUTF(),
                    AlarmModel.ReconciliationResult.valueOf(input.readUTF()));
            reconciliations.put(record.eventId(), record);
        }
        String outputOwner = readNullableString(input);
        return new EngineSnapshot(intents, occurrences, triggerTokens, snoozeChildren,
                reconciliations, outputOwner);
    }

    private static void writeCheckpoint(
            DataOutputStream output, AlarmModel.ReadinessCheckpoint checkpoint) throws IOException {
        output.writeBoolean(checkpoint != null);
        if (checkpoint == null) return;
        output.writeUTF(checkpoint.bootId());
        output.writeUTF(checkpoint.buildId());
        output.writeUTF(checkpoint.cellId());
        output.writeLong(checkpoint.generation());
        output.writeLong(checkpoint.wallClockMillis());
        output.writeLong(checkpoint.monotonicMillis());
        output.writeUTF(checkpoint.readinessState().name());
        output.writeUTF(checkpoint.strategy().name());
    }

    private static AlarmModel.ReadinessCheckpoint readCheckpoint(DataInputStream input) throws IOException {
        if (!input.readBoolean()) return null;
        return new AlarmModel.ReadinessCheckpoint(
                input.readUTF(), input.readUTF(), input.readUTF(), input.readLong(),
                input.readLong(), input.readLong(),
                AlarmModel.ReadinessState.valueOf(input.readUTF()),
                AlarmModel.SchedulingStrategy.valueOf(input.readUTF()));
    }

    private static void writeNullableString(DataOutputStream output, String value) throws IOException {
        output.writeBoolean(value != null);
        if (value != null) output.writeUTF(value);
    }

    private static String readNullableString(DataInputStream input) throws IOException {
        return input.readBoolean() ? input.readUTF() : null;
    }

    private static void writeNullableLong(DataOutputStream output, Long value) throws IOException {
        output.writeBoolean(value != null);
        if (value != null) output.writeLong(value);
    }

    private static Long readNullableLong(DataInputStream input) throws IOException {
        return input.readBoolean() ? input.readLong() : null;
    }

    private static void writeSortedStrings(DataOutputStream output, Set<String> values) throws IOException {
        List<String> sorted = new ArrayList<>(values);
        sorted.sort(String::compareTo);
        output.writeInt(sorted.size());
        for (String value : sorted) output.writeUTF(value);
    }

    private static Set<String> readStringSet(DataInputStream input) throws IOException {
        int count = readCount(input, "set");
        Set<String> result = new HashSet<>();
        for (int index = 0; index < count; index++) result.add(input.readUTF());
        return result;
    }

    private static void writeSortedMap(DataOutputStream output, Map<String, String> values) throws IOException {
        List<Map.Entry<String, String>> sorted = new ArrayList<>(values.entrySet());
        sorted.sort(Map.Entry.comparingByKey());
        output.writeInt(sorted.size());
        for (Map.Entry<String, String> entry : sorted) {
            output.writeUTF(entry.getKey());
            output.writeUTF(entry.getValue());
        }
    }

    private static Map<String, String> readStringMap(DataInputStream input) throws IOException {
        int count = readCount(input, "map");
        Map<String, String> result = new HashMap<>();
        for (int index = 0; index < count; index++) result.put(input.readUTF(), input.readUTF());
        return result;
    }

    private static int readCount(DataInputStream input, String label) throws IOException {
        int count = input.readInt();
        if (count < 0 || count > 1_000_000) throw new IOException("invalid " + label + " count: " + count);
        return count;
    }
}

