package org.alvorada.reliability.wakecore;

import android.content.Context;
import android.util.Log;

import org.json.JSONException;
import org.json.JSONObject;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;

public final class WakeDeviceProtectedStore {
    private static final String TAG = "WakeDeviceProtectedStore";

    // Whitelist state fields strictly compliant with G1 privacy contract
    public String alarmId = "";
    public long generation = 0L;
    public String occurrenceId = "";
    public String parentOccurrenceId = "";
    public String civilSchedule = "";
    public String timezoneId = "";
    public long targetEpochMs = 0L;
    public String route = "";
    public String state = WakeConstants.STATE_IDLE;

    // Checkpoints
    public long configuredAtEpochMs = 0L;
    public long armedAtEpochMs = 0L;
    public long triggeredAtEpochMs = 0L;
    public long triggeredAtMonotonicMs = 0L;
    public long softwareAudioRequestedAtEpochMs = 0L;
    public long softwareAudioStartedAtEpochMs = 0L;
    public long snoozedAtEpochMs = 0L;
    public long dismissedAtEpochMs = 0L;
    public long recoveredLateAtEpochMs = 0L;

    // Deltas
    public long deliveryDeltaMs = 0L;
    public long triggerToSoftwareAudioMs = 0L;

    // Counters & observations
    public int duplicateTriggerCount = 0;
    public int staleGenerationRejectionCount = 0;
    public int futureGenerationRejectionCount = 0;
    public int invalidGenerationRejectionCount = 0;
    public int wrongAlarmIdRejectionCount = 0;
    public int wrongOccurrenceIdRejectionCount = 0;
    public int invalidIdentityRejectionCount = 0;

    public int reconciliationCount = 0;
    public String reconciliationResult = "NONE";
    public String fallbackSoundId = "synthetic_wav_marker";
    public String audioMarkerSha256 = "";

    // F-02 Software audio checkpoints & failure injection
    public boolean softwareAudioStarted = false;
    public boolean softwareAudioFailed = false;
    public String softwareAudioCheckpoint = WakeConstants.CHECKPOINT_NONE;
    public String audioFaultInjection = "NONE";

    // F-03 Boot receiver evidence fields
    public long bootReceiverInvocationEpochMs = 0L;
    public String bootReceivedAction = "";
    public long reconciliationStartEpochMs = 0L;
    public long reconciliationEndEpochMs = 0L;
    public String preReconciliationState = "";
    public String postReconciliationResult = "";

    private final Context deviceProtectedContext;

    public WakeDeviceProtectedStore(Context context) {
        // Enforce Direct Boot safe storage context
        this.deviceProtectedContext = context.isDeviceProtectedStorage()
                ? context
                : context.createDeviceProtectedStorageContext();
        load();
    }

    private File getStateFile() {
        File filesDir = deviceProtectedContext.getFilesDir();
        if (!filesDir.exists()) {
            filesDir.mkdirs();
        }
        return new File(filesDir, WakeConstants.STATE_FILE_NAME);
    }

    public synchronized void save() {
        File targetFile = getStateFile();
        File tempFile = new File(targetFile.getParentFile(), targetFile.getName() + ".tmp");
        try {
            String jsonStr = toJsonString();
            try (FileOutputStream fos = new FileOutputStream(tempFile)) {
                fos.write(jsonStr.getBytes(StandardCharsets.UTF_8));
                fos.flush();
            }
            if (tempFile.renameTo(targetFile) || (targetFile.delete() && tempFile.renameTo(targetFile))) {
                Log.d(TAG, "State saved to " + targetFile.getAbsolutePath());
            } else {
                Log.e(TAG, "Failed to atomically rename state file");
            }
        } catch (Exception e) {
            Log.e(TAG, "Error saving state to device protected storage", e);
        }
    }

    public synchronized void load() {
        File targetFile = getStateFile();
        if (!targetFile.exists() || targetFile.length() == 0) {
            return;
        }
        try (FileInputStream fis = new FileInputStream(targetFile)) {
            byte[] buf = new byte[(int) targetFile.length()];
            int read = fis.read(buf);
            if (read > 0) {
                String jsonStr = new String(buf, 0, read, StandardCharsets.UTF_8);
                fromJsonString(jsonStr);
                Log.d(TAG, "State loaded: " + state + ", alarmId=" + alarmId + ", occurrenceId=" + occurrenceId);
            }
        } catch (Exception e) {
            Log.e(TAG, "Error loading state from " + targetFile.getAbsolutePath(), e);
        }
    }

    public synchronized void reset() {
        alarmId = "";
        generation = 0L;
        occurrenceId = "";
        parentOccurrenceId = "";
        civilSchedule = "";
        timezoneId = "";
        targetEpochMs = 0L;
        route = "";
        state = WakeConstants.STATE_IDLE;
        configuredAtEpochMs = 0L;
        armedAtEpochMs = 0L;
        triggeredAtEpochMs = 0L;
        triggeredAtMonotonicMs = 0L;
        softwareAudioRequestedAtEpochMs = 0L;
        softwareAudioStartedAtEpochMs = 0L;
        snoozedAtEpochMs = 0L;
        dismissedAtEpochMs = 0L;
        recoveredLateAtEpochMs = 0L;
        deliveryDeltaMs = 0L;
        triggerToSoftwareAudioMs = 0L;
        duplicateTriggerCount = 0;
        staleGenerationRejectionCount = 0;
        futureGenerationRejectionCount = 0;
        invalidGenerationRejectionCount = 0;
        wrongAlarmIdRejectionCount = 0;
        wrongOccurrenceIdRejectionCount = 0;
        invalidIdentityRejectionCount = 0;

        reconciliationCount = 0;
        reconciliationResult = "NONE";
        softwareAudioStarted = false;
        softwareAudioFailed = false;
        softwareAudioCheckpoint = WakeConstants.CHECKPOINT_NONE;
        audioFaultInjection = "NONE";
        audioMarkerSha256 = "";

        bootReceiverInvocationEpochMs = 0L;
        bootReceivedAction = "";
        reconciliationStartEpochMs = 0L;
        reconciliationEndEpochMs = 0L;
        preReconciliationState = "";
        postReconciliationResult = "";
        save();
    }

    public synchronized String toJsonString() {
        try {
            JSONObject obj = new JSONObject();
            obj.put("contract", WakeConstants.CONTRACT_VERSION);
            obj.put("alarm_id", alarmId);
            obj.put("generation", generation);
            obj.put("occurrence_id", occurrenceId);
            obj.put("parent_occurrence_id", parentOccurrenceId);
            obj.put("civil_schedule", civilSchedule);
            obj.put("timezone_id", timezoneId);
            obj.put("target_epoch_ms", targetEpochMs);
            obj.put("route", route);
            obj.put("state", state);

            obj.put("configured_at_epoch_ms", configuredAtEpochMs);
            obj.put("armed_at_epoch_ms", armedAtEpochMs);
            obj.put("triggered_at_epoch_ms", triggeredAtEpochMs);
            obj.put("triggered_at_monotonic_ms", triggeredAtMonotonicMs);
            obj.put("software_audio_requested_at_epoch_ms", softwareAudioRequestedAtEpochMs);
            obj.put("software_audio_started_at_epoch_ms", softwareAudioStartedAtEpochMs);
            obj.put("snoozed_at_epoch_ms", snoozedAtEpochMs);
            obj.put("dismissed_at_epoch_ms", dismissedAtEpochMs);
            obj.put("recovered_late_at_epoch_ms", recoveredLateAtEpochMs);

            obj.put("delivery_delta_ms", deliveryDeltaMs);
            obj.put("trigger_to_software_audio_ms", triggerToSoftwareAudioMs);

            obj.put("duplicate_trigger_count", duplicateTriggerCount);
            obj.put("stale_generation_rejection_count", staleGenerationRejectionCount);
            obj.put("future_generation_rejection_count", futureGenerationRejectionCount);
            obj.put("invalid_generation_rejection_count", invalidGenerationRejectionCount);
            obj.put("wrong_alarm_id_rejection_count", wrongAlarmIdRejectionCount);
            obj.put("wrong_occurrence_id_rejection_count", wrongOccurrenceIdRejectionCount);
            obj.put("invalid_identity_rejection_count", invalidIdentityRejectionCount);

            obj.put("reconciliation_count", reconciliationCount);
            obj.put("reconciliation_result", reconciliationResult);
            obj.put("fallback_sound_id", fallbackSoundId);
            obj.put("audio_marker_sha256", audioMarkerSha256);

            obj.put("software_audio_started", softwareAudioStarted);
            obj.put("software_audio_failed", softwareAudioFailed);
            obj.put("software_audio_checkpoint", softwareAudioCheckpoint);
            obj.put("audio_fault_injection", audioFaultInjection);

            obj.put("boot_receiver_invocation_epoch_ms", bootReceiverInvocationEpochMs);
            obj.put("boot_received_action", bootReceivedAction);
            obj.put("reconciliation_start_epoch_ms", reconciliationStartEpochMs);
            obj.put("reconciliation_end_epoch_ms", reconciliationEndEpochMs);
            obj.put("pre_reconciliation_state", preReconciliationState);
            obj.put("post_reconciliation_result", postReconciliationResult);

            // Invariant note: audible is NEVER true in software adapter
            obj.put("audible_claimed", false);
            obj.put("human_awake_claimed", false);

            return obj.toString(2);
        } catch (JSONException e) {
            return "{}";
        }
    }

    public synchronized void fromJsonString(String jsonStr) {
        try {
            JSONObject obj = new JSONObject(jsonStr);
            alarmId = obj.optString("alarm_id", "");
            generation = obj.optLong("generation", 0L);
            occurrenceId = obj.optString("occurrence_id", "");
            parentOccurrenceId = obj.optString("parent_occurrence_id", "");
            civilSchedule = obj.optString("civil_schedule", "");
            timezoneId = obj.optString("timezone_id", "");
            targetEpochMs = obj.optLong("target_epoch_ms", 0L);
            route = obj.optString("route", "");
            state = obj.optString("state", WakeConstants.STATE_IDLE);

            configuredAtEpochMs = obj.optLong("configured_at_epoch_ms", 0L);
            armedAtEpochMs = obj.optLong("armed_at_epoch_ms", 0L);
            triggeredAtEpochMs = obj.optLong("triggered_at_epoch_ms", 0L);
            triggeredAtMonotonicMs = obj.optLong("triggered_at_monotonic_ms", 0L);
            softwareAudioRequestedAtEpochMs = obj.optLong("software_audio_requested_at_epoch_ms", 0L);
            softwareAudioStartedAtEpochMs = obj.optLong("software_audio_started_at_epoch_ms", 0L);
            snoozedAtEpochMs = obj.optLong("snoozed_at_epoch_ms", 0L);
            dismissedAtEpochMs = obj.optLong("dismissed_at_epoch_ms", 0L);
            recoveredLateAtEpochMs = obj.optLong("recovered_late_at_epoch_ms", 0L);

            deliveryDeltaMs = obj.optLong("delivery_delta_ms", 0L);
            triggerToSoftwareAudioMs = obj.optLong("trigger_to_software_audio_ms", 0L);

            duplicateTriggerCount = obj.optInt("duplicate_trigger_count", 0);
            staleGenerationRejectionCount = obj.optInt("stale_generation_rejection_count", 0);
            futureGenerationRejectionCount = obj.optInt("future_generation_rejection_count", 0);
            invalidGenerationRejectionCount = obj.optInt("invalid_generation_rejection_count", 0);
            wrongAlarmIdRejectionCount = obj.optInt("wrong_alarm_id_rejection_count", 0);
            wrongOccurrenceIdRejectionCount = obj.optInt("wrong_occurrence_id_rejection_count", 0);
            invalidIdentityRejectionCount = obj.optInt("invalid_identity_rejection_count", 0);

            reconciliationCount = obj.optInt("reconciliation_count", 0);
            reconciliationResult = obj.optString("reconciliation_result", "NONE");
            fallbackSoundId = obj.optString("fallback_sound_id", "synthetic_wav_marker");
            audioMarkerSha256 = obj.optString("audio_marker_sha256", "");
            softwareAudioStarted = obj.optBoolean("software_audio_started", false);
            softwareAudioFailed = obj.optBoolean("software_audio_failed", false);
            softwareAudioCheckpoint = obj.optString("software_audio_checkpoint", WakeConstants.CHECKPOINT_NONE);
            audioFaultInjection = obj.optString("audio_fault_injection", "NONE");

            bootReceiverInvocationEpochMs = obj.optLong("boot_receiver_invocation_epoch_ms", 0L);
            bootReceivedAction = obj.optString("boot_received_action", "");
            reconciliationStartEpochMs = obj.optLong("reconciliation_start_epoch_ms", 0L);
            reconciliationEndEpochMs = obj.optLong("reconciliation_end_epoch_ms", 0L);
            preReconciliationState = obj.optString("pre_reconciliation_state", "");
            postReconciliationResult = obj.optString("post_reconciliation_result", "");
        } catch (JSONException e) {
            Log.e(TAG, "Error parsing state JSON", e);
        }
    }
}
