package org.alvorada.reliability.wakecore;

public final class WakeConstants {
    private WakeConstants() {}

    public static final String CONTRACT_VERSION = "ALVORADA_WAKECORE_E1_V1";
    public static final String PACKAGE_NAME = "org.alvorada.reliability.wakecore";

    // Intent Actions
    public static final String ACTION_ALARM_TRIGGER = "org.alvorada.reliability.wakecore.ALARM_TRIGGER";
    public static final String ACTION_COMMAND = "org.alvorada.reliability.wakecore.COMMAND";
    public static final String ACTION_START_WAKE_SESSION = "org.alvorada.reliability.wakecore.START_WAKE_SESSION";
    public static final String ACTION_STOP_WAKE_SESSION = "org.alvorada.reliability.wakecore.STOP_WAKE_SESSION";

    // Subcommands for ACTION_COMMAND
    public static final String CMD_CONFIGURE = "CONFIGURE";
    public static final String CMD_ARM = "ARM";
    public static final String CMD_TRIGGER_INJECT = "TRIGGER_INJECT";
    public static final String CMD_SNOOZE = "SNOOZE";
    public static final String CMD_DISMISS = "DISMISS";
    public static final String CMD_RECONCILE = "RECONCILE";
    public static final String CMD_DUMP_STATE = "DUMP_STATE";
    public static final String CMD_RESET = "RESET";
    public static final String CMD_SET_MOCK_TIME = "SET_MOCK_TIME";
    public static final String CMD_SET_AUDIO_FAULT = "SET_AUDIO_FAULT";
    public static final String CMD_SET_SESSION_FAULT = "SET_SESSION_FAULT";
    public static final String CMD_CHECK_READINESS = "CHECK_READINESS";
    public static final String CMD_CHECK_AUTHORITY_DIMENSIONS = "CHECK_AUTHORITY_DIMENSIONS";

    // States
    public static final String STATE_IDLE = "IDLE";
    public static final String STATE_CONFIGURED = "CONFIGURED";
    public static final String STATE_ARMED = "ARMED";
    public static final String STATE_TRIGGERED = "TRIGGERED";
    public static final String STATE_SOFTWARE_AUDIO_STARTED = "SOFTWARE_AUDIO_STARTED";
    public static final String STATE_SOFTWARE_AUDIO_FAILED = "SOFTWARE_AUDIO_FAILED";
    public static final String STATE_SNOOZED = "SNOOZED";
    public static final String STATE_DISMISSED = "DISMISSED";
    public static final String STATE_RECOVERED_LATE = "RECOVERED_LATE";
    public static final String STATE_OUTCOME_UNKNOWN = "OUTCOME_UNKNOWN";
    public static final String STATE_CONFIGURED_NOT_ARMED = "CONFIGURED_NOT_ARMED";

    // Audio & Session Checkpoints (Lane B4 - 8 distinct checkpoints)
    public static final String CHECKPOINT_NONE = "NONE";
    public static final String CHECKPOINT_TRIGGERED = "TRIGGERED";
    public static final String CHECKPOINT_WAKE_SESSION_REQUESTED = "WAKE_SESSION_REQUESTED";
    public static final String CHECKPOINT_WAKE_SESSION_STARTED = "WAKE_SESSION_STARTED";
    public static final String CHECKPOINT_NOTIFICATION_POSTED = "NOTIFICATION_POSTED";
    public static final String CHECKPOINT_SOFTWARE_AUDIO_STARTED = "SOFTWARE_AUDIO_STARTED";
    public static final String CHECKPOINT_SOFTWARE_AUDIO_CONTINUING = "SOFTWARE_AUDIO_CONTINUING";
    public static final String CHECKPOINT_WAKE_SESSION_DISMISSED = "WAKE_SESSION_DISMISSED";
    public static final String CHECKPOINT_WAKE_SESSION_SNOOZED = "WAKE_SESSION_SNOOZED";
    public static final String CHECKPOINT_WAKE_SESSION_STOPPED = "WAKE_SESSION_STOPPED";

    // Legacy Audio Checkpoints
    public static final String CHECKPOINT_SOFTWARE_AUDIO_REQUESTED = "SOFTWARE_AUDIO_REQUESTED";
    public static final String CHECKPOINT_SOFTWARE_AUDIO_ENGINE_INITIALIZED = "SOFTWARE_AUDIO_ENGINE_INITIALIZED";
    public static final String CHECKPOINT_SOFTWARE_AUDIO_WRITE_ACCEPTED = "SOFTWARE_AUDIO_WRITE_ACCEPTED";
    public static final String CHECKPOINT_SOFTWARE_AUDIO_FAILED = "SOFTWARE_AUDIO_FAILED";

    // Scheduling Routes
    public static final String ROUTE_ALARM_CLOCK = "ALARM_CLOCK";
    public static final String ROUTE_EXACT_ALLOW_IDLE = "EXACT_ALLOW_IDLE";

    // Notification Channel & IDs
    public static final String NOTIFICATION_CHANNEL_ID = "alvorada_wake_session_channel";
    public static final int NOTIFICATION_ID = 42001;

    // Thresholds
    public static final long LATE_RECOVERY_LIMIT_MS = 10 * 60 * 1000L; // 10 minutes
    public static final long SNOOZE_CONTRACT_MS = 5 * 60 * 1000L; // 5 minutes

    // File name in device-protected storage
    public static final String STATE_FILE_NAME = "wakecore_state.json";
}
