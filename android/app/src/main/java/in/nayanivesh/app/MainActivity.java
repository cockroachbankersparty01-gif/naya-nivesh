package in.nayanivesh.app;

import android.Manifest;
import android.app.Activity;
import android.content.pm.PackageManager;
import android.os.Build;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.webkit.JavascriptInterface;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.HashSet;
import java.util.Set;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Naya Nivesh: the IPO app runs from assets/index.html in a full-screen WebView.
 * The page refreshes its own data: it asks this activity (through the "NayaNivesh"
 * bridge) to download public IPO pages, then parses them itself and saves the result
 * on the phone. No server, website or account is involved.
 */
public class MainActivity extends Activity {
    private static final String[] ALLOWED_HOSTS = {"www.gmpipowatch.in", "gmpipowatch.in", "ipowatch.in", "www.ipowatch.in"};
    private WebView web;
    private final ExecutorService pool = Executors.newFixedThreadPool(3);
    private String pendingHash = null;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        installCrashLog();
        pendingHash = hashOf(getIntent());
        try { Notify.channel(this); } catch (Throwable ignored) { }
        try { NewIpoJob.ensure(this); } catch (Throwable ignored) { }
        getWindow().setStatusBarColor(Color.parseColor("#0f1a2a"));
        web = new WebView(this);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);   // saved IPO data + your applications live here
        s.setAllowFileAccess(true);
        web.addJavascriptInterface(new Bridge(), "NayaNivesh");
        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView v, WebResourceRequest r) {
                Uri u = r.getUrl();
                if ("file".equals(u.getScheme())) return false;
                startActivity(new Intent(Intent.ACTION_VIEW, u)); // registrar / BSE / NSE links open in the browser
                return true;
            }
        });
        if (state != null) web.restoreState(state);
        else web.loadUrl("file:///android_asset/index.html");
        setContentView(web);
        showLastCrash();
    }

    /** If the app ever crashes, the error is saved and shown on the next start so it can be reported. */
    private void installCrashLog() {
        final Thread.UncaughtExceptionHandler prev = Thread.getDefaultUncaughtExceptionHandler();
        Thread.setDefaultUncaughtExceptionHandler((t, e) -> {
            try {
                java.io.StringWriter sw = new java.io.StringWriter();
                e.printStackTrace(new java.io.PrintWriter(sw));
                getSharedPreferences("nn", MODE_PRIVATE).edit().putString("crash", sw.toString()).commit();
            } catch (Throwable ignored) { }
            if (prev != null) prev.uncaughtException(t, e);
        });
    }

    private void showLastCrash() {
        final String c = getSharedPreferences("nn", MODE_PRIVATE).getString("crash", null);
        if (c == null) return;
        getSharedPreferences("nn", MODE_PRIVATE).edit().remove("crash").apply();
        final String txt = c.length() > 1500 ? c.substring(0, 1500) : c;
        new android.app.AlertDialog.Builder(this).setTitle("Naya Nivesh stopped last time")
                .setMessage("Please send a screenshot of this to the developer:\n\n" + txt)
                .setPositiveButton("Copy", (d, w) -> {
                    android.content.ClipboardManager cm = getSystemService(android.content.ClipboardManager.class);
                    if (cm != null) cm.setPrimaryClip(android.content.ClipData.newPlainText("crash", c));
                })
                .setNegativeButton("Close", null).show();
    }

    private static String hashOf(Intent i) {
        String h = i == null ? null : i.getStringExtra("hash");
        return h != null && h.startsWith("#") ? h : null;
    }

    @Override
    protected void onNewIntent(Intent i) {
        super.onNewIntent(i);
        String h = hashOf(i);
        if (h != null && web != null) web.evaluateJavascript("location.hash=" + JSONObject.quote(h), null);
    }

    @Override protected void onSaveInstanceState(Bundle out) { super.onSaveInstanceState(out); web.saveState(out); }

    @Override
    public void onBackPressed() {
        if (web.canGoBack()) web.goBack(); else super.onBackPressed();
    }

    @Override protected void onDestroy() { pool.shutdownNow(); super.onDestroy(); }

    private static boolean allowed(String url) {
        try {
            URL u = new URL(url);
            if (!"https".equals(u.getProtocol())) return false;
            for (String h : ALLOWED_HOSTS) if (h.equalsIgnoreCase(u.getHost())) return true;
        } catch (Exception ignored) { }
        return false;
    }

    static String download(String url) throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
        c.setConnectTimeout(15000);
        c.setReadTimeout(20000);
        c.setInstanceFollowRedirects(true);
        c.setRequestProperty("User-Agent", "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Mobile Safari/537.36");
        c.setRequestProperty("Accept-Language", "en-IN,en;q=0.9");
        try {
            if (c.getResponseCode() != 200) return null;
            try (InputStream in = c.getInputStream(); ByteArrayOutputStream out = new ByteArrayOutputStream()) {
                byte[] buf = new byte[16384];
                int n, total = 0;
                while ((n = in.read(buf)) > 0 && total < 4_000_000) { out.write(buf, 0, n); total += n; }
                return out.toString(StandardCharsets.UTF_8.name());
            }
        } finally { c.disconnect(); }
    }

    class Bridge {
        /** Downloads a public IPO page in the background and hands its HTML back to the page. */
        @JavascriptInterface
        public void fetch(final String id, final String url) {
            pool.execute(() -> {
                String body = null;
                if (allowed(url)) {
                    try { body = download(url); } catch (Exception ignored) { }
                }
                final String js = "window.__nnCb(" + JSONObject.quote(id) + "," + (body != null) + ","
                        + JSONObject.quote(body == null ? "" : body) + ")";
                web.post(() -> web.evaluateJavascript(js, null));
            });
        }

        /** Saves the alert schedule (opening, closing, allotment, listing) as phone alarms. */
        @JavascriptInterface
        public void setAlerts(String json) { try { Alerts.save(getApplicationContext(), json); } catch (Throwable ignored) { } }

        /** On/off for "new IPO announced" notifications that run in the background. */
        @JavascriptInterface
        public void setNotifyNew(boolean on) { try { Alerts.prefs(getApplicationContext()).edit().putBoolean("notifyNew", on).apply(); } catch (Throwable ignored) { } }

        /** Marks an IPO as already announced so the background check does not notify twice. */
        @JavascriptInterface
        public void markKnown(String slug) {
            if (slug == null || slug.isEmpty()) return;
            Set<String> k = new HashSet<>(Alerts.prefs(getApplicationContext()).getStringSet("known", new HashSet<>()));
            k.add(slug);
            Alerts.prefs(getApplicationContext()).edit().putStringSet("known", k).apply();
        }

        /** Shows a notification right away. */
        @JavascriptInterface
        public void notify(String title, String text, String hash) {
            try { Notify.post(getApplicationContext(), (title + hash).hashCode(), title, text, hash); } catch (Throwable ignored) { }
        }

        /** Asks for notification permission (Android 13+). */
        @JavascriptInterface
        public void requestNotify() {
            if (Build.VERSION.SDK_INT >= 33) runOnUiThread(() -> {
                try {
                    if (checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED)
                        requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, 11);
                } catch (Throwable ignored) { }
            });
        }

        /** The screen a tapped notification should open, if any (used once at start-up). */
        @JavascriptInterface
        public String openHash() { String h = pendingHash; pendingHash = null; return h == null ? "" : h; }
    }
}
