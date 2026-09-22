package org.alvorada.reliability.harness;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.util.Log;

public class HarnessReceiver extends BroadcastReceiver {
    private static final String TAG = "AlvoradaHarness";

    @Override
    public void onReceive(Context context, Intent intent) {
        String action = intent != null ? intent.getAction() : "null";
        Log.i(TAG, "HARNESS_PING_RECEIVED: action=" + action);
        setResultCode(42);
        setResultData("ALVORADA_P8_PASS");
    }
}
