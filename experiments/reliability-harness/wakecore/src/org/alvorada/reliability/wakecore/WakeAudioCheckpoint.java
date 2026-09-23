package org.alvorada.reliability.wakecore;

import android.media.AudioAttributes;
import android.media.AudioFormat;
import android.media.AudioTrack;
import android.os.SystemClock;
import android.util.Log;

public final class WakeAudioCheckpoint {
    private static final String TAG = "WakeAudioCheckpoint";

    private WakeAudioCheckpoint() {}

    public static volatile String sFaultInjection = "NONE";

    public static void setFaultInjection(String fault) {
        sFaultInjection = (fault != null) ? fault : "NONE";
    }

    public static void executeAudioHandoff(WakeDeviceProtectedStore store) {
        long requestedWallMs = System.currentTimeMillis();
        long requestedMonotonicMs = SystemClock.elapsedRealtime();

        store.softwareAudioRequestedAtEpochMs = requestedWallMs;
        store.softwareAudioCheckpoint = WakeConstants.CHECKPOINT_SOFTWARE_AUDIO_REQUESTED;
        store.save();

        Log.i(TAG, "SOFTWARE_AUDIO_REQUESTED_AT=" + requestedWallMs + " (monotonic=" + requestedMonotonicMs + ")");

        byte[] wavBytes = AudioMarker.wavBytes();
        String sha256 = AudioMarker.sha256Hex(wavBytes);
        store.audioMarkerSha256 = sha256;

        String fault = (sFaultInjection != null && !"NONE".equals(sFaultInjection))
                ? sFaultInjection : store.audioFaultInjection;

        // Check simulated fault: INIT_FAIL
        if ("INIT_FAIL".equalsIgnoreCase(fault)) {
            recordAudioFailure(store, "INJECTED_FAULT: simulated AudioTrack initialization failure");
            return;
        }

        // Execute deterministic software audio playback via AudioTrack
        AudioTrack track = null;
        try {
            int sampleRate = AudioMarker.SAMPLE_RATE;
            int pcmOffset = 44;
            int pcmLength = wavBytes.length - pcmOffset;
            if (pcmLength <= 0) {
                recordAudioFailure(store, "Invalid PCM length: " + pcmLength);
                return;
            }

            int bufferSize = pcmLength;

            AudioAttributes attrs = new AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_ALARM)
                    .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                    .build();

            AudioFormat format = new AudioFormat.Builder()
                    .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                    .setSampleRate(sampleRate)
                    .setChannelMask(AudioFormat.CHANNEL_OUT_MONO)
                    .build();

            track = new AudioTrack(
                    attrs,
                    format,
                    bufferSize,
                    AudioTrack.MODE_STATIC,
                    android.media.AudioManager.AUDIO_SESSION_ID_GENERATE);

            // Verify AudioTrack successfully acquired native resources (not STATE_UNINITIALIZED)
            if (track.getState() == AudioTrack.STATE_UNINITIALIZED) {
                recordAudioFailure(store, "AudioTrack failed to initialize, state=" + track.getState());
                return;
            }

            store.softwareAudioCheckpoint = WakeConstants.CHECKPOINT_SOFTWARE_AUDIO_ENGINE_INITIALIZED;
            store.save();

            // Check simulated fault: WRITE_FAIL
            if ("WRITE_FAIL".equalsIgnoreCase(fault)) {
                recordAudioFailure(store, "INJECTED_FAULT: simulated PCM write failure");
                return;
            }

            int written = track.write(wavBytes, pcmOffset, pcmLength);
            if (written <= 0 || written != pcmLength) {
                recordAudioFailure(store, "PCM write rejected: expected " + pcmLength + " bytes, written=" + written);
                return;
            }

            // In MODE_STATIC, writing audio transitions the track to STATE_INITIALIZED
            if (track.getState() != AudioTrack.STATE_INITIALIZED) {
                recordAudioFailure(store, "AudioTrack not STATE_INITIALIZED after write, state=" + track.getState());
                return;
            }

            store.softwareAudioCheckpoint = WakeConstants.CHECKPOINT_SOFTWARE_AUDIO_WRITE_ACCEPTED;
            store.save();

            // Check simulated fault: PLAY_FAIL
            if ("PLAY_FAIL".equalsIgnoreCase(fault)) {
                recordAudioFailure(store, "INJECTED_FAULT: simulated play failure");
                return;
            }

            track.play();

            // Verify AudioTrack reports PLAYSTATE_PLAYING
            if (track.getPlayState() != AudioTrack.PLAYSTATE_PLAYING) {
                recordAudioFailure(store, "AudioTrack playState not PLAYSTATE_PLAYING, state=" + track.getPlayState());
                return;
            }

            // Bounded playback progress verification
            SystemClock.sleep(50L);
            int headPosition = track.getPlaybackHeadPosition();
            Log.d(TAG, "AudioTrack playback head position=" + headPosition);
            if (headPosition > 0) {
                store.softwareAudioPlaybackHeadAdvanced = true;
            }

            long startedWallMs = System.currentTimeMillis();
            long startedMonotonicMs = SystemClock.elapsedRealtime();

            store.softwareAudioStartedAtEpochMs = startedWallMs;
            store.softwareAudioStarted = true;
            store.softwareAudioFailed = false;
            store.audioFailureReason = "";
            store.softwareAudioCheckpoint = WakeConstants.CHECKPOINT_SOFTWARE_AUDIO_STARTED;
            if (!WakeConstants.STATE_RECOVERED_LATE.equals(store.state)) {
                store.state = WakeConstants.STATE_SOFTWARE_AUDIO_STARTED;
            }

            if (store.triggeredAtEpochMs > 0) {
                store.triggerToSoftwareAudioMs = startedWallMs - store.triggeredAtEpochMs;
            }

            store.save();

            // EPISTEMIC INVARIANT: Log explicit boundary
            Log.i(TAG, "SOFTWARE_AUDIO_STARTED_AT=" + startedWallMs + " (monotonic=" + startedMonotonicMs + ")");
            Log.i(TAG, "EPISTEMIC_INVARIANT: SOFTWARE_AUDIO_STARTED=TRUE; HEAD_ADVANCED=" + store.softwareAudioPlaybackHeadAdvanced + "; AUDIBLE=UNPROVEN; HUMAN_AWAKE=UNPROVEN; SHA256=" + sha256);

        } catch (Throwable t) {
            recordAudioFailure(store, "AudioTrack exception: " + t.getMessage());
        } finally {
            if (track != null) {
                try {
                    track.stop();
                    track.release();
                } catch (Exception ignored) {}
            }
        }
    }

    private static void recordAudioFailure(WakeDeviceProtectedStore store, String reason) {
        Log.e(TAG, "SOFTWARE_AUDIO_FAILED: " + reason);
        store.softwareAudioStarted = false;
        store.softwareAudioFailed = true;
        store.audioFailureReason = (reason != null) ? reason : "UNKNOWN";
        store.softwareAudioCheckpoint = WakeConstants.CHECKPOINT_SOFTWARE_AUDIO_FAILED;
        store.state = WakeConstants.STATE_SOFTWARE_AUDIO_FAILED;
        store.save();
    }
}
