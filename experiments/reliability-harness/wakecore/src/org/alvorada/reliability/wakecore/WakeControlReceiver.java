package org.alvorada.reliability.wakecore;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.util.Log;

import java.util.UUID;

public final class WakeControlReceiver extends BroadcastReceiver {
    private static final String TAG = "WakeControlReceiver";

    @Override
    public void onReceive(Context context, Intent intent) {
        if (intent == null) {
            setResultCode(1);
            setResultData("ERROR: null intent");
            return;
        }

        String cmd = intent.getStringExtra("cmd");
        if (cmd == null) {
            cmd = intent.getAction();
        }

        Log.i(TAG, "Command received: " + cmd);
        WakeDeviceProtectedStore store = new WakeDeviceProtectedStore(context);
        WakeScheduler scheduler = new WakeScheduler(context, store);

        if (WakeConstants.CMD_CONFIGURE.equalsIgnoreCase(cmd)) {
            store.alarmId = intent.getStringExtra("alarm_id") != null
                    ? intent.getStringExtra("alarm_id") : "alarm_test_001";
            store.generation = intent.getLongExtra("generation", 1L);
            store.civilSchedule = intent.getStringExtra("civil_schedule") != null
                    ? intent.getStringExtra("civil_schedule") : "07:00";
            store.timezoneId = intent.getStringExtra("timezone_id") != null
                    ? intent.getStringExtra("timezone_id") : "UTC";
            store.state = WakeConstants.STATE_CONFIGURED;
            store.configuredAtEpochMs = System.currentTimeMillis();
            store.save();

            setResultCode(0);
            setResultData(store.toJsonString());

        } else if (WakeConstants.CMD_ARM.equalsIgnoreCase(cmd)) {
            String alarmId = intent.getStringExtra("alarm_id") != null
                    ? intent.getStringExtra("alarm_id") : store.alarmId;
            long generation = intent.getLongExtra("generation", store.generation > 0 ? store.generation : 1L);
            String occurrenceId = intent.getStringExtra("occurrence_id") != null
                    ? intent.getStringExtra("occurrence_id") : ("occ_" + UUID.randomUUID().toString().substring(0, 8));

            long targetEpochMs = intent.getLongExtra("target_epoch_ms", 0L);
            if (targetEpochMs <= 0) {
                long delayMs = intent.getLongExtra("delay_ms", 3000L); // default 3s
                targetEpochMs = System.currentTimeMillis() + delayMs;
            }

            String route = intent.getStringExtra("route") != null
                    ? intent.getStringExtra("route") : WakeConstants.ROUTE_ALARM_CLOCK;

            boolean ok = scheduler.scheduleOccurrence(alarmId, generation, occurrenceId, targetEpochMs, route);
            setResultCode(ok ? 0 : 2);
            setResultData(store.toJsonString());

        } else if (WakeConstants.CMD_TRIGGER_INJECT.equalsIgnoreCase(cmd)) {
            Intent triggerIntent = new Intent(context, WakeAlarmReceiver.class);
            triggerIntent.setAction(WakeConstants.ACTION_ALARM_TRIGGER);
            triggerIntent.putExtra("alarm_id", intent.getStringExtra("alarm_id"));
            triggerIntent.putExtra("generation", intent.getLongExtra("generation", 0L));
            triggerIntent.putExtra("occurrence_id", intent.getStringExtra("occurrence_id"));
            triggerIntent.putExtra("target_epoch_ms", intent.getLongExtra("target_epoch_ms", 0L));
            context.sendBroadcast(triggerIntent);

            setResultCode(0);
            setResultData("TRIGGER_INJECTED");

        } else if (WakeConstants.CMD_SNOOZE.equalsIgnoreCase(cmd)) {
            // A5 Snooze semantics
            if (WakeConstants.STATE_TRIGGERED.equals(store.state)
                    || WakeConstants.STATE_SOFTWARE_AUDIO_STARTED.equals(store.state)) {

                long snoozeDelayMs = intent.getLongExtra("snooze_delay_ms", WakeConstants.SNOOZE_CONTRACT_MS);
                long targetEpoch = System.currentTimeMillis() + snoozeDelayMs;

                String parentOccId = store.occurrenceId;
                String childOccId = "snooze_" + UUID.randomUUID().toString().substring(0, 8);

                // Schedule snooze child occurrence
                boolean ok = scheduler.scheduleOccurrence(
                        store.alarmId,
                        store.generation,
                        childOccId,
                        targetEpoch,
                        store.route.isEmpty() ? WakeConstants.ROUTE_ALARM_CLOCK : store.route);

                if (ok) {
                    store.parentOccurrenceId = parentOccId;
                    store.occurrenceId = childOccId;
                    store.state = WakeConstants.STATE_SNOOZED;
                    store.snoozedAtEpochMs = System.currentTimeMillis();
                    store.save();
                    setResultCode(0);
                    setResultData(store.toJsonString());
                } else {
                    setResultCode(3);
                    setResultData("ERROR: failed to schedule snooze child");
                }
            } else {
                setResultCode(4);
                setResultData("ERROR: cannot snooze from state " + store.state);
            }

        } else if (WakeConstants.CMD_DISMISS.equalsIgnoreCase(cmd)) {
            // A6 Dismiss semantics: cancels active occurrence without erasing recurring rule
            scheduler.cancelOccurrence(store.occurrenceId);
            store.state = WakeConstants.STATE_DISMISSED;
            store.dismissedAtEpochMs = System.currentTimeMillis();
            store.save();

            setResultCode(0);
            setResultData(store.toJsonString());

        } else if (WakeConstants.CMD_RECONCILE.equalsIgnoreCase(cmd)) {
            long mockNow = intent.getLongExtra("mock_now_epoch_ms", 0L);
            WakeBootReceiver.reconcile(context, mockNow > 0, mockNow);
            store.load();

            setResultCode(0);
            setResultData(store.toJsonString());

        } else if (WakeConstants.CMD_DUMP_STATE.equalsIgnoreCase(cmd) || "GET_STATE".equalsIgnoreCase(cmd)) {
            setResultCode(0);
            setResultData(store.toJsonString());

        } else if (WakeConstants.CMD_RESET.equalsIgnoreCase(cmd)) {
            scheduler.cancelOccurrence(store.occurrenceId);
            store.reset();
            setResultCode(0);
            setResultData(store.toJsonString());

        } else {
            setResultCode(1);
            setResultData("ERROR: unknown command " + cmd);
        }
    }
}
