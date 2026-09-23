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

            // Do not override invalid route with default; preserve caller's route string
            String route = intent.hasExtra("route")
                    ? intent.getStringExtra("route")
                    : (store.route.isEmpty() ? WakeConstants.ROUTE_ALARM_CLOCK : store.route);

            boolean ok = scheduler.scheduleOccurrence(alarmId, generation, occurrenceId, targetEpochMs, route);
            setResultCode(ok ? 0 : 2);
            setResultData(store.toJsonString());

        } else if (WakeConstants.CMD_TRIGGER_INJECT.equalsIgnoreCase(cmd)) {
            String injAlarmId = intent.getStringExtra("alarm_id");
            long injGen = intent.getLongExtra("generation", 0L);
            String injOccId = intent.getStringExtra("occurrence_id");
            long injTarget = intent.getLongExtra("target_epoch_ms", 0L);

            Intent triggerIntent = new Intent(context, WakeAlarmReceiver.class);
            triggerIntent.setAction(WakeConstants.ACTION_ALARM_TRIGGER);
            if (injAlarmId != null && injOccId != null) {
                triggerIntent.setData(android.net.Uri.parse("alvorada://alarm/" + injAlarmId + "/" + injGen + "/" + injOccId));
            }
            triggerIntent.putExtra("alarm_id", injAlarmId);
            triggerIntent.putExtra("generation", injGen);
            triggerIntent.putExtra("occurrence_id", injOccId);
            triggerIntent.putExtra("target_epoch_ms", injTarget);
            context.sendBroadcast(triggerIntent);

            setResultCode(0);
            setResultData("TRIGGER_INJECTED");

        } else if (WakeConstants.CMD_SET_AUDIO_FAULT.equalsIgnoreCase(cmd)) {
            String fault = intent.getStringExtra("fault");
            if (fault == null) {
                fault = intent.getStringExtra("fault_mode");
            }
            store.audioFaultInjection = (fault != null) ? fault : "NONE";
            WakeAudioCheckpoint.setFaultInjection(store.audioFaultInjection);
            store.save();

            setResultCode(0);
            setResultData(store.toJsonString());

        } else if (WakeConstants.CMD_SET_SESSION_FAULT.equalsIgnoreCase(cmd)) {
            String fault = intent.getStringExtra("fault");
            store.sessionFaultInjection = (fault != null) ? fault : "NONE";
            store.save();
            setResultCode(0);
            setResultData(store.toJsonString());

        } else if (WakeConstants.CMD_CHECK_READINESS.equalsIgnoreCase(cmd)) {
            boolean canSchedule = scheduler.canScheduleExactAlarms();
            store.canScheduleExactAlarms = canSchedule;
            if (!canSchedule && WakeConstants.STATE_ARMED.equals(store.state)) {
                store.state = WakeConstants.STATE_CONFIGURED_NOT_ARMED;
                store.readinessDecayDetected = true;
            }
            store.save();
            setResultCode(0);
            setResultData(store.toJsonString());

        } else if (WakeConstants.CMD_CHECK_AUTHORITY_DIMENSIONS.equalsIgnoreCase(cmd)) {
            android.app.NotificationManager nm = (android.app.NotificationManager) context.getSystemService(Context.NOTIFICATION_SERVICE);
            if (nm != null) {
                store.notificationPermissionGranted = nm.areNotificationsEnabled();
                if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.O) {
                    android.app.NotificationChannel ch = nm.getNotificationChannel(WakeConstants.NOTIFICATION_CHANNEL_ID);
                    store.notificationChannelEnabled = (ch == null || ch.getImportance() != android.app.NotificationManager.IMPORTANCE_NONE);
                } else {
                    store.notificationChannelEnabled = true;
                }
                if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
                    store.fullScreenIntentCapable = nm.canUseFullScreenIntent();
                } else {
                    store.fullScreenIntentCapable = true;
                }
            }
            store.audioCapable = true;
            store.save();
            setResultCode(0);
            setResultData(store.toJsonString());

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
                    store.wakeSessionCheckpoint = WakeConstants.CHECKPOINT_WAKE_SESSION_SNOOZED;
                    store.wakeSessionContinuing = false;
                    store.save();

                    try {
                        Intent stopIntent = new Intent(context, WakeSessionService.class);
                        stopIntent.setAction(WakeConstants.ACTION_STOP_WAKE_SESSION);
                        context.startService(stopIntent);
                    } catch (Exception ignored) {}

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
            store.wakeSessionCheckpoint = WakeConstants.CHECKPOINT_WAKE_SESSION_DISMISSED;
            store.wakeSessionContinuing = false;
            store.save();

            try {
                Intent stopIntent = new Intent(context, WakeSessionService.class);
                stopIntent.setAction(WakeConstants.ACTION_STOP_WAKE_SESSION);
                context.startService(stopIntent);
            } catch (Exception ignored) {}

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
