package in.nayanivesh.app;

import android.app.AlarmManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;

import org.json.JSONArray;
import org.json.JSONObject;

/** Keeps the IPO alert schedule (sent by the app page) as phone alarms, even when the app is closed. */
final class Alerts {
    static final String ACTION = "in.nayanivesh.app.ALERT";
    private static final int MAX = 120;

    static SharedPreferences prefs(Context c) { return c.getSharedPreferences("nn", Context.MODE_PRIVATE); }

    static void save(Context c, String json) {
        prefs(c).edit().putString("alerts", json).apply();
        schedule(c);
    }

    private static PendingIntent pi(Context c, int slot, JSONObject a) {
        Intent i = new Intent(c, AlertReceiver.class).setAction(ACTION);
        if (a != null) i.putExtra("title", a.optString("title")).putExtra("text", a.optString("text")).putExtra("hash", a.optString("hash"));
        int flags = PendingIntent.FLAG_IMMUTABLE | (a == null ? PendingIntent.FLAG_NO_CREATE : PendingIntent.FLAG_UPDATE_CURRENT);
        return PendingIntent.getBroadcast(c, 1000 + slot, i, flags);
    }

    static void schedule(Context c) {
        AlarmManager am = c.getSystemService(AlarmManager.class);
        for (int s = 0; s < MAX; s++) { PendingIntent old = pi(c, s, null); if (old != null) { am.cancel(old); old.cancel(); } }
        try {
            JSONArray arr = new JSONArray(prefs(c).getString("alerts", "[]"));
            long now = System.currentTimeMillis();
            int slot = 0;
            for (int k = 0; k < arr.length() && slot < MAX; k++) {
                JSONObject a = arr.getJSONObject(k);
                long ts = a.optLong("ts");
                if (ts <= now) continue;
                am.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, ts, pi(c, slot++, a));
            }
        } catch (Exception ignored) { }
    }
}
