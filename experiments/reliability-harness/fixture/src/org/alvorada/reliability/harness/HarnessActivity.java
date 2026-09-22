package org.alvorada.reliability.harness;

import android.app.Activity;
import android.os.Bundle;
import android.util.Log;

public class HarnessActivity extends Activity {
    private static final String TAG = "AlvoradaHarness";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        Log.i(TAG, "HARNESS_ACTIVITY_CREATED: API36_PASS");
    }
}
