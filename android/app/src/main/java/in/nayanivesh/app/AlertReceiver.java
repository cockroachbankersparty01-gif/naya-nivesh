package in.nayanivesh.app;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

/** Fires scheduled IPO alerts, and shows them as notifications. */
public class AlertReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context c, Intent i) {
        String a = i.getAction();
        if (Alerts.ACTION.equals(a)) {
            String title = i.getStringExtra("title");
            if (title == null || title.isEmpty()) return;
            Notify.post(c, (title + i.getStringExtra("hash")).hashCode(), title, i.getStringExtra("text"), i.getStringExtra("hash"));
        }
    }
}
