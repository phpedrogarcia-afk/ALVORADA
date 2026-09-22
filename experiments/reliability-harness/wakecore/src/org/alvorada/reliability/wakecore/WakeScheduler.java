package org.alvorada.reliability.wakecore;

import android.app.AlarmManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.os.Build;
import android.util.Log;

public final class WakeScheduler {
    private static final String TAG = "WakeScheduler";

    private final Context context;
    private final AlarmManager alarmManager;
    private final WakeDeviceProtectedStore store;

    public WakeScheduler(Context context, WakeDeviceProtectedStore store) {
        this.context = context;
        this.alarmManager = (AlarmManager) context.getSystemService(Context.ALARM_SERVICE);
        this.store = store;
    }

    public boolean canScheduleExactAlarms() {
        if (alarmManager == null) return false;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            return alarmManager.canScheduleExactAlarms();
        }
        return true;
    }

    public boolean scheduleOccurrence(String alarmId, long generation, String occurrenceId,
                                      long targetEpochMs, String route) {
        if (alarmManager == null) {
            Log.e(TAG, "AlarmManager service unavailable");
            return false;
        }

        if (!canScheduleExactAlarms()) {
            Log.w(TAG, "canScheduleExactAlarms() is FALSE. Route cannot be safely ARMED.");
            // Record readiness decay
            store.state = "READINESS_DECAY_BLOCKED";
            store.save();
            return false;
        }

        // F-05: Strict Route Validation - fail closed on unknown or invalid route
        if (route == null || (!WakeConstants.ROUTE_ALARM_CLOCK.equals(route) && !WakeConstants.ROUTE_EXACT_ALLOW_IDLE.equals(route))) {
            Log.e(TAG, "INVALID_ROUTE_REJECTED: route must be strictly ALARM_CLOCK or EXACT_ALLOW_IDLE, got: " + route);
            return false;
        }

        // F-01: Harden PendingIntent identity with deterministic unique data URI
        Intent triggerIntent = new Intent(context, WakeAlarmReceiver.class);
        triggerIntent.setAction(WakeConstants.ACTION_ALARM_TRIGGER);
        triggerIntent.setData(android.net.Uri.parse("alvorada://alarm/" + alarmId + "/" + generation + "/" + occurrenceId));
        triggerIntent.putExtra("alarm_id", alarmId);
        triggerIntent.putExtra("generation", generation);
        triggerIntent.putExtra("occurrence_id", occurrenceId);
        triggerIntent.putExtra("route", route);
        triggerIntent.putExtra("target_epoch_ms", targetEpochMs);

        // Deterministic requestCode derived from occurrenceId
        int requestCode = Math.abs(occurrenceId.hashCode());

        int flags = PendingIntent.FLAG_UPDATE_CURRENT;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            flags |= PendingIntent.FLAG_IMMUTABLE;
        }

        PendingIntent pendingIntent = PendingIntent.getBroadcast(
                context, requestCode, triggerIntent, flags);

        try {
            if (WakeConstants.ROUTE_ALARM_CLOCK.equals(route)) {
                // ALARM_CLOCK Route
                Intent showIntent = new Intent(context, WakeControlReceiver.class);
                showIntent.setAction(WakeConstants.ACTION_COMMAND);
                showIntent.setData(android.net.Uri.parse("alvorada://show/" + alarmId + "/" + generation + "/" + occurrenceId));
                PendingIntent showPendingIntent = PendingIntent.getBroadcast(
                        context, requestCode + 1, showIntent, flags);

                AlarmManager.AlarmClockInfo info = new AlarmManager.AlarmClockInfo(
                        targetEpochMs, showPendingIntent);
                alarmManager.setAlarmClock(info, pendingIntent);
                Log.d(TAG, "Scheduled ALARM_CLOCK at " + targetEpochMs + " for occurrence " + occurrenceId);
            } else if (WakeConstants.ROUTE_EXACT_ALLOW_IDLE.equals(route)) {
                // EXACT_ALLOW_IDLE Route
                alarmManager.setExactAndAllowWhileIdle(
                        AlarmManager.RTC_WAKEUP, targetEpochMs, pendingIntent);
                Log.d(TAG, "Scheduled EXACT_ALLOW_IDLE at " + targetEpochMs + " for occurrence " + occurrenceId);
            } else {
                // Defense-in-depth: impossible due to route validation above
                return false;
            }

            // Record ARMED state only after successful system call
            store.alarmId = alarmId;
            store.generation = generation;
            store.occurrenceId = occurrenceId;
            store.targetEpochMs = targetEpochMs;
            store.route = route;
            store.state = WakeConstants.STATE_ARMED;
            store.armedAtEpochMs = System.currentTimeMillis();
            store.save();

            return true;
        } catch (SecurityException se) {
            Log.e(TAG, "SecurityException scheduling exact alarm", se);
            store.state = "SECURITY_EXCEPTION";
            store.save();
            return false;
        } catch (Exception e) {
            Log.e(TAG, "Unexpected error scheduling exact alarm", e);
            store.state = "SCHEDULE_FAILED";
            store.save();
            return false;
        }
    }

    public void cancelOccurrence(String alarmId, long generation, String occurrenceId) {
        if (alarmManager == null || occurrenceId == null) return;
        Intent triggerIntent = new Intent(context, WakeAlarmReceiver.class);
        triggerIntent.setAction(WakeConstants.ACTION_ALARM_TRIGGER);
        if (alarmId != null && !alarmId.isEmpty() && generation > 0) {
            triggerIntent.setData(android.net.Uri.parse("alvorada://alarm/" + alarmId + "/" + generation + "/" + occurrenceId));
        }
        int requestCode = Math.abs(occurrenceId.hashCode());
        int flags = PendingIntent.FLAG_NO_CREATE;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            flags |= PendingIntent.FLAG_IMMUTABLE;
        }
        PendingIntent existing = PendingIntent.getBroadcast(context, requestCode, triggerIntent, flags);
        if (existing != null) {
            alarmManager.cancel(existing);
            existing.cancel();
            Log.d(TAG, "Cancelled alarm for occurrence " + occurrenceId);
        }
    }

    public void cancelOccurrence(String occurrenceId) {
        cancelOccurrence(store.alarmId, store.generation, occurrenceId);
    }
}
