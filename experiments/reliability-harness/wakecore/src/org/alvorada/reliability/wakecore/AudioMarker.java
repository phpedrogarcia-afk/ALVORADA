package org.alvorada.reliability.wakecore;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;

public final class AudioMarker {
    public static final int SAMPLE_RATE = 8_000;
    public static final int SAMPLE_COUNT = 6_000;
    public static final int PCM_BITS = 16;
    public static final int CHANNELS = 1;

    private AudioMarker() {}

    public static byte[] wavBytes() {
        byte[] pcm = new byte[SAMPLE_COUNT * 2];
        double[] frequencies = {659.2551138257, 783.9908719635, 987.7666025122};
        int segmentLength = SAMPLE_COUNT / frequencies.length;
        int rampSamples = 80;
        for (int sample = 0; sample < SAMPLE_COUNT; sample++) {
            int segment = Math.min(sample / segmentLength, frequencies.length - 1);
            int within = sample - (segment * segmentLength);
            double envelope = 1.0;
            if (within < rampSamples) envelope = within / (double) rampSamples;
            if (segmentLength - within <= rampSamples) {
                envelope = Math.min(envelope, (segmentLength - within - 1) / (double) rampSamples);
            }
            envelope = Math.max(0.0, envelope);
            double angle = 2.0 * StrictMath.PI * frequencies[segment] * sample / SAMPLE_RATE;
            short value = (short) StrictMath.round(StrictMath.sin(angle) * envelope * 12_000.0);
            pcm[sample * 2] = (byte) (value & 0xff);
            pcm[sample * 2 + 1] = (byte) ((value >>> 8) & 0xff);
        }

        try {
            ByteArrayOutputStream bytes = new ByteArrayOutputStream(44 + pcm.length);
            writeAscii(bytes, "RIFF");
            writeLittleEndianInt(bytes, 36 + pcm.length);
            writeAscii(bytes, "WAVE");
            writeAscii(bytes, "fmt ");
            writeLittleEndianInt(bytes, 16);
            writeLittleEndianShort(bytes, 1);
            writeLittleEndianShort(bytes, CHANNELS);
            writeLittleEndianInt(bytes, SAMPLE_RATE);
            writeLittleEndianInt(bytes, SAMPLE_RATE * CHANNELS * PCM_BITS / 8);
            writeLittleEndianShort(bytes, CHANNELS * PCM_BITS / 8);
            writeLittleEndianShort(bytes, PCM_BITS);
            writeAscii(bytes, "data");
            writeLittleEndianInt(bytes, pcm.length);
            bytes.write(pcm);
            return bytes.toByteArray();
        } catch (IOException impossible) {
            throw new IllegalStateException("in-memory WAV construction failed", impossible);
        }
    }

    public static String sha256Hex(byte[] data) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] hash = digest.digest(data);
            StringBuilder hex = new StringBuilder(hash.length * 2);
            for (byte b : hash) {
                int val = b & 0xff;
                if (val < 16) hex.append('0');
                hex.append(Integer.toHexString(val));
            }
            return hex.toString();
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("SHA-256 not available", e);
        }
    }

    private static void writeAscii(ByteArrayOutputStream output, String value) throws IOException {
        output.write(value.getBytes(java.nio.charset.StandardCharsets.US_ASCII));
    }

    private static void writeLittleEndianInt(ByteArrayOutputStream output, int value) {
        output.write(value & 0xff);
        output.write((value >>> 8) & 0xff);
        output.write((value >>> 16) & 0xff);
        output.write((value >>> 24) & 0xff);
    }

    private static void writeLittleEndianShort(ByteArrayOutputStream output, int value) {
        output.write(value & 0xff);
        output.write((value >>> 8) & 0xff);
    }
}
