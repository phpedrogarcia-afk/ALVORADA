package org.alvorada.reliability.wakecore;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.util.Log;

public final class WakeBootReceiver extends BroadcastReceiver {
    private static final String TAG = "WakeBootReceiver";

    @Override
    public void onReceive(Context context, Intent intent) {
        String action = intent != null ? intent.getAction() : "UNKNOWN";
        long invocationEpochMs = System.currentTimeMillis();
        Log.i(TAG, "BOOT/RECONCILIATION intent received: action=" + action + " at " + invocationEpochMs);

        reconcile(context, false, 0L, action, invocationEpochMs);
    }

    public static synchronized void reconcile(Context context, boolean forceMockTime, long mockNowEpochMs) {
        reconcile(context, forceMockTime, mockNowEpochMs, "MANUAL_RECONCILE", System.currentTimeMillis());
    }

    public static synchronized void reconcile(Context context, boolean forceMockTime, long mockNowEpochMs,
                                              String triggerAction, long invocationEpochMs) {
        WakeDeviceProtectedStore store = new WakeDeviceProtectedStore(context);
        store.reconciliationCount++;
        long startTime = System.currentTimeMillis();

        store.bootReceiverInvocationEpochMs = invocationEpochMs;
        store.bootReceivedAction = (triggerAction != null) ? triggerAction : "UNKNOWN";
        store.reconciliationStartEpochMs = startTime;
        store.preReconciliationState = store.state;

        Log.i(TAG, "Reconciliation invocation #" + store.reconciliationCount
                + " [action=" + store.bootReceivedAction + ", state=" + store.state + ", occurrence=" + store.occurrenceId + "]");

        if (!WakeConstants.STATE_ARMED.equals(store.state)) {
            store.reconciliationResult = "NOOP_NOT_ARMED";
            store.postReconciliationResult = "NOOP_NOT_ARMED";
            store.reconciliationEndEpochMs = System.currentTimeMillis();
            Log.d(TAG, "Reconciliation: state is " + store.state + ", no action required");
            store.save();
            return;
        }

        long now = forceMockTime ? mockNowEpochMs : System.currentTimeMillis();
        long target = store.targetEpochMs;

        if (target <= 0) {
            store.reconciliationResult = "NOOP_NO_TARGET";
            store.postReconciliationResult = "NOOP_NO_TARGET";
            store.reconciliationEndEpochMs = System.currentTimeMillis();
            store.save();
            return;
        }

        if (target > now) {
            // Alarm is still in the future: reschedule with platform AlarmManager
            WakeScheduler scheduler = new WakeScheduler(context, store);
            boolean ok = scheduler.scheduleOccurrence(
                    store.alarmId,
                    store.generation,
                    store.occurrenceId,
                    target,
                    store.route.isEmpty() ? WakeConstants.ROUTE_ALARM_CLOCK : store.route);

            store.reconciliationResult = ok ? "RESCHEDULED_FUTURE" : "RESCHEDULE_FAILED";
            store.postReconciliationResult = store.reconciliationResult;
            store.reconciliationEndEpochMs = System.currentTimeMillis();
            Log.i(TAG, "Reconciliation: rescheduled future alarm for " + target + " (ok=" + ok + ")");
            store.save();
        } else {
            // Target is in the past: evaluate Late Recovery Policy
            long overdueMs = now - target;
            Log.i(TAG, "Reconciliation: target in the past by " + overdueMs + " ms");

            if (overdueMs <= WakeConstants.LATE_RECOVERY_LIMIT_MS) {
                // <= T+10 minutes: RECOVERED_LATE
                Log.i(TAG, "Reconciliation: <= 10 min (" + overdueMs + " ms) -> RECOVERED_LATE");
                store.state = WakeConstants.STATE_RECOVERED_LATE;
                store.recoveredLateAtEpochMs = now;
                store.reconciliationResult = "RECOVERED_LATE";
                store.postReconciliationResult = "RECOVERED_LATE";
                store.deliveryDeltaMs = overdueMs;
                store.reconciliationEndEpochMs = System.currentTimeMillis();
                store.save();

                // Fire software audio for the late-recovered occurrence
                WakeAudioCheckpoint.executeAudioHandoff(store);
            } else {
                // > T+10 minutes: NO SURPRISE ALARM -> OUTCOME_UNKNOWN
                Log.i(TAG, "Reconciliation: > 10 min (" + overdueMs + " ms) -> NO SURPRISE ALARM -> OUTCOME_UNKNOWN");
                store.state = WakeConstants.STATE_OUTCOME_UNKNOWN;
                store.reconciliationResult = "SUPPRESSED_OVERDUE_PAST_LIMIT";
                store.postReconciliationResult = "SUPPRESSED_OVERDUE_PAST_LIMIT";
                store.reconciliationEndEpochMs = System.currentTimeMillis();
                store.save();
            }
        }
    }
}
