package org.alvorada.reliability.wakecore;

public final class WakeConstants {
    private WakeConstants() {}

    public static final String CONTRACT_VERSION = "ALVORADA_WAKECORE_E1_V1";
    public static final String PACKAGE_NAME = "org.alvorada.reliability.wakecore";

    // Intent Actions
    public static final String ACTION_ALARM_TRIGGER = "org.alvorada.reliability.wakecore.ALARM_TRIGGER";
    public static final String ACTION_COMMAND = "org.alvorada.reliability.wakecore.COMMAND";

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

    // Audio Checkpoints
    public static final String CHECKPOINT_NONE = "NONE";
    public static final String CHECKPOINT_SOFTWARE_AUDIO_REQUESTED = "SOFTWARE_AUDIO_REQUESTED";
    public static final String CHECKPOINT_SOFTWARE_AUDIO_ENGINE_INITIALIZED = "SOFTWARE_AUDIO_ENGINE_INITIALIZED";
    public static final String CHECKPOINT_SOFTWARE_AUDIO_WRITE_ACCEPTED = "SOFTWARE_AUDIO_WRITE_ACCEPTED";
    public static final String CHECKPOINT_SOFTWARE_AUDIO_STARTED = "SOFTWARE_AUDIO_STARTED";
    public static final String CHECKPOINT_SOFTWARE_AUDIO_FAILED = "SOFTWARE_AUDIO_FAILED";

    // Scheduling Routes
    public static final String ROUTE_ALARM_CLOCK = "ALARM_CLOCK";
    public static final String ROUTE_EXACT_ALLOW_IDLE = "EXACT_ALLOW_IDLE";

    // Thresholds
    public static final long LATE_RECOVERY_LIMIT_MS = 10 * 60 * 1000L; // 10 minutes
    public static final long SNOOZE_CONTRACT_MS = 5 * 60 * 1000L; // 5 minutes

    // File name in device-protected storage
    public static final String STATE_FILE_NAME = "wakecore_state.json";
}
