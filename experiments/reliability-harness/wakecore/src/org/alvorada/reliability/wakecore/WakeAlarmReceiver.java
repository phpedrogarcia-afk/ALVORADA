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

            // 1. Stale Generation Defense
            if (generation > 0 && store.generation > 0 && generation < store.generation) {
                store.staleGenerationRejectionCount++;
                Log.w(TAG, "STALE_GENERATION_REJECTED: received gen " + generation
                        + " < active gen " + store.generation
                        + ", rejection count=" + store.staleGenerationRejectionCount);
                store.save();
                return;
            }

            // 2. Duplicate Trigger Defense
            boolean isParentOccurrence = occurrenceId != null
                    && store.parentOccurrenceId != null
                    && occurrenceId.equals(store.parentOccurrenceId);
            if (isParentOccurrence) {
                store.duplicateTriggerCount++;
                Log.w(TAG, "DUPLICATE_TRIGGER_REJECTED: parent occurrence " + occurrenceId
                        + " already superseded by snooze child " + store.occurrenceId
                        + ", duplicate count=" + store.duplicateTriggerCount);
                store.save();
                return;
            }

            boolean isSameOccurrence = occurrenceId != null && occurrenceId.equals(store.occurrenceId);
            boolean alreadyTriggered = WakeConstants.STATE_TRIGGERED.equals(store.state)
                    || WakeConstants.STATE_SOFTWARE_AUDIO_STARTED.equals(store.state)
                    || WakeConstants.STATE_DISMISSED.equals(store.state)
                    || WakeConstants.STATE_RECOVERED_LATE.equals(store.state);

            if (isSameOccurrence && alreadyTriggered) {
                store.duplicateTriggerCount++;
                Log.w(TAG, "DUPLICATE_TRIGGER_REJECTED: occurrence " + occurrenceId
                        + " already in state " + store.state
                        + ", duplicate count=" + store.duplicateTriggerCount);
                store.save();
                return;
            }

            // 3. Valid Trigger Accepted
            Log.i(TAG, "VALID_TRIGGER_ACCEPTED for occurrence " + occurrenceId + " (gen " + generation + ")");
            store.alarmId = (alarmId != null) ? alarmId : store.alarmId;
            store.generation = (generation > 0) ? generation : store.generation;
            store.occurrenceId = (occurrenceId != null) ? occurrenceId : store.occurrenceId;
            store.state = WakeConstants.STATE_TRIGGERED;
            store.triggeredAtEpochMs = triggerWallMs;
            store.triggeredAtMonotonicMs = triggerMonotonicMs;

            long scheduledTarget = (targetEpochMs > 0) ? targetEpochMs : store.targetEpochMs;
            if (scheduledTarget > 0) {
                store.deliveryDeltaMs = triggerWallMs - scheduledTarget;
            }

            store.save();

            // 4. Enter Software Audio Checkpoint Path
            WakeAudioCheckpoint.executeAudioHandoff(store);

        } finally {
            if (wakeLock != null && wakeLock.isHeld()) {
                wakeLock.release();
            }
        }
    }
}
