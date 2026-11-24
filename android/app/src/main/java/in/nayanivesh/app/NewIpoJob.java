package in.nayanivesh.app;

import android.app.job.JobInfo;
import android.app.job.JobParameters;
import android.app.job.JobScheduler;
import android.app.job.JobService;
import android.content.ComponentName;
import android.content.Context;
import android.content.SharedPreferences;

import java.util.HashSet;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Every few hours, even when the app is closed, checks the public IPO list and notifies about newly announced IPOs. */
public class NewIpoJob extends JobService {
    private static final int JOB_ID = 7101;
    private static final Pattern LINK = Pattern.compile("href=\"(?:https://www\\.gmpipowatch\\.in)?/ipo/([a-z0-9-]+)/?\"");

    static void ensure(Context c) {
        JobScheduler js = c.getSystemService(JobScheduler.class);
        if (js == null || js.getPendingJob(JOB_ID) != null) return;
        js.schedule(new JobInfo.Builder(JOB_ID, new ComponentName(c, NewIpoJob.class))
                .setRequiredNetworkType(JobInfo.NETWORK_TYPE_ANY)
                .setPeriodic(3 * 60 * 60 * 1000L)
                .setPersisted(true).build());
    }

    @Override
    public boolean onStartJob(final JobParameters p) {
        new Thread(() -> { try { check(getApplicationContext()); } catch (Exception ignored) { } jobFinished(p, false); }).start();
        return true;
    }

    @Override public boolean onStopJob(JobParameters p) { return true; }

    static void check(Context c) throws Exception {
        Set<String> now = new HashSet<>();
        for (String path : new String[]{"/", "/mainboard", "/sme"}) {
            String html = MainActivity.download("https://www.gmpipowatch.in" + path);
            if (html == null) continue;
            Matcher m = LINK.matcher(html);
            while (m.find()) now.add(m.group(1));
        }
        if (now.isEmpty()) return;
        SharedPreferences sp = Alerts.prefs(c);
        Set<String> known = sp.getStringSet("known", null);
        boolean wantNew = sp.getBoolean("notifyNew", true);
        if (known != null && wantNew) {
            int n = 0;
            for (String s : now) {
                if (known.contains(s) || n >= 3) continue;
                n++;
                String name = pretty(s);
                Notify.post(c, s.hashCode(), "New IPO: " + name, "A new IPO has been announced. Open Naya Nivesh for price band, dates and analysis.", "#upcoming");
            }
        }
        Set<String> merged = new HashSet<>(now);
        if (known != null) merged.addAll(known);
        sp.edit().putStringSet("known", merged).apply();
    }

    private static String pretty(String slug) {
        StringBuilder b = new StringBuilder();
        for (String w : slug.replaceAll("-(ipo|sme-ipo)$", "").split("-")) {
            if (w.isEmpty()) continue;
            if (b.length() > 0) b.append(' ');
            b.append(Character.toUpperCase(w.charAt(0))).append(w.substring(1));
        }
        return b.toString();
    }
}
