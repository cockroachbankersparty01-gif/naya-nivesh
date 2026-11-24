package in.nayanivesh.app;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.graphics.Color;
import android.os.Build;

/** Posts Naya Nivesh notifications; tapping one opens the related screen. */
final class Notify {
    static final String CH = "ipo_alerts";

    static void channel(Context c) {
        if (Build.VERSION.SDK_INT >= 26) {
            NotificationChannel ch = new NotificationChannel(CH, "IPO alerts", NotificationManager.IMPORTANCE_HIGH);
            ch.setDescription("New IPOs, opening and closing days, allotment and listing");
            ch.enableLights(true);
            ch.setLightColor(Color.parseColor("#14b8a6"));
            c.getSystemService(NotificationManager.class).createNotificationChannel(ch);
        }
    }

    static void post(Context c, int id, String title, String text, String hash) {
        channel(c);
        Intent open = new Intent(c, MainActivity.class).putExtra("hash", hash == null ? "" : hash)
                .addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        PendingIntent pi = PendingIntent.getActivity(c, id, open, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        Notification.Builder b = Build.VERSION.SDK_INT >= 26 ? new Notification.Builder(c, CH) : new Notification.Builder(c);
        b.setSmallIcon(R.drawable.ic_stat).setContentTitle(title).setContentText(text)
                .setStyle(new Notification.BigTextStyle().bigText(text))
                .setColor(Color.parseColor("#0f766e")).setAutoCancel(true).setContentIntent(pi);
        if (Build.VERSION.SDK_INT < 26) b.setPriority(Notification.PRIORITY_HIGH).setDefaults(Notification.DEFAULT_ALL);
        try { c.getSystemService(NotificationManager.class).notify(id, b.build()); } catch (SecurityException ignored) { }
    }
}
