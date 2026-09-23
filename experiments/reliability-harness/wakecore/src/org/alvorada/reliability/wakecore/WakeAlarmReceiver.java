package org.alvorada.reliability.wakecore;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.os.PowerManager;
import android.os.SystemClock;
import android.util.Log;

public final class WakeAlarmReceiver extends BroadcastReceiver {
    private static final String TAG = "WakeAlarmReceiver";

    @Override
    public void onReceive(Context context, Intent intent) {
        long triggerWallMs = System.currentTimeMillis();
        long triggerMonotonicMs = SystemClock.elapsedRealtime();

        Log.i(TAG, "ALARM_TRIGGER received at " + triggerWallMs + " (monotonic=" + triggerMonotonicMs + ")");

        if (intent == null) {
            Log.e(TAG, "Received null intent");
            return;
        }

        String alarmId = intent.getStringExtra("alarm_id");
        long generation = intent.getLongExtra("generation", 0L);
        String occurrenceId = intent.getStringExtra("occurrence_id");
        long targetEpochMs = intent.getLongExtra("target_epoch_ms", 0L);

        // Acquire temporary WakeLock to guarantee software execution completes
        PowerManager pm = (PowerManager) context.getSystemService(Context.POWER_SERVICE);
        PowerManager.WakeLock wakeLock = null;
        if (pm != null) {
            wakeLock = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "AlvoradaWakeCore:AlarmTrigger");
            wakeLock.acquire(10_000L); // 10 seconds timeout
        }

        try {
            WakeDeviceProtectedStore store = new WakeDeviceProtectedStore(context);

            // 1. Mandatory Identity Non-Empty Validation
            if (alarmId == null || alarmId.trim().isEmpty() || occurrenceId == null || occurrenceId.trim().isEmpty()) {
                store.invalidIdentityRejectionCount++;
                Log.w(TAG, "INVALID_IDENTITY_REJECTED: null or empty alarm_id/occurrence_id [alarm_id="
                        + alarmId + ", occurrence_id=" + occurrenceId + "]");
                store.save();
                return;
            }

            // 2. Generation Authority Validation
            if (generation <= 0) {
                store.invalidGenerationRejectionCount++;
                Log.w(TAG, "INVALID_GENERATION_REJECTED: generation=" + generation + " <= 0");
                store.save();
                return;
            }

            if (generation < store.generation) {
                store.staleGenerationRejectionCount++;
                Log.w(TAG, "STALE_GENERATION_REJECTED: received gen " + generation
                        + " < active gen " + store.generation
                        + ", rejection count=" + store.staleGenerationRejectionCount);
                store.save();
                return;
            }

            if (generation > store.generation) {
                store.futureGenerationRejectionCount++;
                Log.w(TAG, "FUTURE_GENERATION_REJECTED: received gen " + generation
                        + " > active gen " + store.generation
                        + ", rejection count=" + store.futureGenerationRejectionCount);
                store.save();
                return;
            }

            // 3. Alarm ID Authority Validation
            if (!alarmId.equals(store.alarmId)) {
                store.wrongAlarmIdRejectionCount++;
                Log.w(TAG, "WRONG_ALARM_ID_REJECTED: received alarm_id " + alarmId
                        + " != authoritative " + store.alarmId);
                store.save();
                return;
            }

            // 4. Duplicate / Superseded Parent Defense
            boolean isParentOccurrence = store.parentOccurrenceId != null
                    && !store.parentOccurrenceId.isEmpty()
                    && occurrenceId.equals(store.parentOccurrenceId);
            if (isParentOccurrence) {
                store.duplicateTriggerCount++;
                Log.w(TAG, "DUPLICATE_TRIGGER_REJECTED: parent occurrence " + occurrenceId
                        + " already superseded by snooze child " + store.occurrenceId
                        + ", duplicate count=" + store.duplicateTriggerCount);
                store.save();
                return;
            }

            // 5. Occurrence ID Authority Validation
            if (!occurrenceId.equals(store.occurrenceId)) {
                store.wrongOccurrenceIdRejectionCount++;
                Log.w(TAG, "WRONG_OCCURRENCE_ID_REJECTED: received occurrence " + occurrenceId
                        + " != authoritative " + store.occurrenceId);
                store.save();
                return;
            }

            // 6. Duplicate Callback Defense on Authoritative Occurrence
            boolean alreadyTriggered = WakeConstants.STATE_TRIGGERED.equals(store.state)
                    || WakeConstants.STATE_SOFTWARE_AUDIO_STARTED.equals(store.state)
                    || WakeConstants.STATE_SOFTWARE_AUDIO_FAILED.equals(store.state)
                    || WakeConstants.STATE_DISMISSED.equals(store.state)
                    || WakeConstants.STATE_RECOVERED_LATE.equals(store.state);

            if (alreadyTriggered) {
                store.duplicateTriggerCount++;
                Log.w(TAG, "DUPLICATE_TRIGGER_REJECTED: occurrence " + occurrenceId
                        + " already in state " + store.state
                        + ", duplicate count=" + store.duplicateTriggerCount);
                store.save();
                return;
            }

            // 7. Verify Triggerable State (ARMED or SNOOZED)
            if (!WakeConstants.STATE_ARMED.equals(store.state) && !WakeConstants.STATE_SNOOZED.equals(store.state)) {
                Log.w(TAG, "INVALID_STATE_FOR_TRIGGER: state=" + store.state + ", occurrence=" + occurrenceId);
                return;
            }

            // 8. Legitimate Trigger Accepted - ONLY NOW mutate state
            Log.i(TAG, "VALID_TRIGGER_ACCEPTED for occurrence " + occurrenceId + " (gen " + generation + ")");
            store.state = WakeConstants.STATE_TRIGGERED;
            store.triggeredAtEpochMs = triggerWallMs;
            store.triggeredAtMonotonicMs = triggerMonotonicMs;
            store.wakeSessionCheckpoint = WakeConstants.CHECKPOINT_TRIGGERED;

            long scheduledTarget = (targetEpochMs > 0) ? targetEpochMs : store.targetEpochMs;
            if (scheduledTarget > 0) {
                store.deliveryDeltaMs = triggerWallMs - scheduledTarget;
            }

            // Checkpoint 2: WAKE_SESSION_REQUESTED
            store.wakeSessionRequestedAtEpochMs = System.currentTimeMillis();
            store.wakeSessionCheckpoint = WakeConstants.CHECKPOINT_WAKE_SESSION_REQUESTED;
            store.save();

            // 9. Enter Governed Wake Session Path (Lane B4)
            try {
                Intent sessionIntent = new Intent(context, WakeSessionService.class);
                sessionIntent.setAction(WakeConstants.ACTION_START_WAKE_SESSION);
                sessionIntent.putExtra("occurrence_id", occurrenceId);
                if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.O) {
                    context.startForegroundService(sessionIntent);
                } else {
                    context.startService(sessionIntent);
                }
            } catch (Exception e) {
                Log.e(TAG, "Failed to start WakeSessionService: " + e.getMessage(), e);
                // Fallback direct execution if service cannot start
                WakeAudioCheckpoint.executeAudioHandoff(store);
            }

        } finally {
            if (wakeLock != null && wakeLock.isHeld()) {
                wakeLock.release();
            }
        }
    }
}
