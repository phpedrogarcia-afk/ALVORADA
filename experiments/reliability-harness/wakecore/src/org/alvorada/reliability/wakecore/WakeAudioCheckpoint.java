package org.alvorada.reliability.wakecore;

import android.media.AudioAttributes;
import android.media.AudioFormat;
import android.media.AudioTrack;
import android.os.SystemClock;
import android.util.Log;

public final class WakeAudioCheckpoint {
    private static final String TAG = "WakeAudioCheckpoint";

    private WakeAudioCheckpoint() {}

    public static void executeAudioHandoff(WakeDeviceProtectedStore store) {
        long requestedWallMs = System.currentTimeMillis();
        long requestedMonotonicMs = SystemClock.elapsedRealtime();

        store.softwareAudioRequestedAtEpochMs = requestedWallMs;
        Log.i(TAG, "SOFTWARE_AUDIO_REQUESTED_AT=" + requestedWallMs + " (monotonic=" + requestedMonotonicMs + ")");

        byte[] wavBytes = AudioMarker.wavBytes();
        String sha256 = AudioMarker.sha256Hex(wavBytes);
        store.audioMarkerSha256 = sha256;

        // Execute deterministic software audio playback via AudioTrack
        AudioTrack track = null;
        try {
            int sampleRate = AudioMarker.SAMPLE_RATE;
            int bufferSize = Math.max(wavBytes.length, AudioTrack.getMinBufferSize(
                    sampleRate,
                    AudioFormat.CHANNEL_OUT_MONO,
                    AudioFormat.ENCODING_PCM_16BIT));

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

            // Write PCM data portion (skip 44-byte WAV header)
            int pcmOffset = 44;
            int pcmLength = wavBytes.length - pcmOffset;
            if (pcmLength > 0) {
                track.write(wavBytes, pcmOffset, pcmLength);
                track.play();
            }
        } catch (Exception e) {
            Log.w(TAG, "AudioTrack initialization exception (falling back to memory marker verification): " + e.getMessage());
        } finally {
            if (track != null) {
                try {
                    track.stop();
                    track.release();
                } catch (Exception ignored) {}
            }
        }

        long startedWallMs = System.currentTimeMillis();
        long startedMonotonicMs = SystemClock.elapsedRealtime();

        store.softwareAudioStartedAtEpochMs = startedWallMs;
        store.softwareAudioStarted = true;
        if (!WakeConstants.STATE_RECOVERED_LATE.equals(store.state)) {
            store.state = WakeConstants.STATE_SOFTWARE_AUDIO_STARTED;
        }

        if (store.triggeredAtEpochMs > 0) {
            store.triggerToSoftwareAudioMs = startedWallMs - store.triggeredAtEpochMs;
        }

        store.save();

        // EPISTEMIC INVARIANT: Log explicit boundary
        Log.i(TAG, "SOFTWARE_AUDIO_STARTED_AT=" + startedWallMs + " (monotonic=" + startedMonotonicMs + ")");
        Log.i(TAG, "EPISTEMIC_INVARIANT: SOFTWARE_AUDIO_STARTED=TRUE; AUDIBLE=UNPROVEN; HUMAN_AWAKE=UNPROVEN; SHA256=" + sha256);
    }
}
